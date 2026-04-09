"""Parser module for reading and validating drone simulation map files."""

from __future__ import annotations
import re

from src.graph import Connection, Graph, HubRole, Zone, ZoneType


class ParseError(Exception):
    """Raised when a map file contains invalid or malformed data."""


class Parser:
    """Parse a map file into a Graph and drone count.

    Handles the file format:
        nb_drones: <number>
        start_hub: <name> <x> <y> [zone=<type> max_drones=<n> color=<hex>]
        end_hub: <name> <x> <y> [...]
        hub: <name> <x> <y> [...]
        connection: <zone1>-<zone2> [max_link_capacity=<n>]
    """

    VALID_ZONE_TYPES: set[str] = {
        "normal", "restricted", "priority", "blocked",
    }
    VALID_ROLES: dict[str, HubRole] = {
        "start_hub": HubRole.START,
        "end_hub": HubRole.END,
        "hub": HubRole.INTERMEDIATE,
    }

    def __init__(self) -> None:
        """Initialize the parser with empty state."""
        self.nb_drones: int = 0
        self.graph: Graph = Graph()
        self._has_start: bool = False
        self._has_end: bool = False
        self._zone_names: set[str] = set()
        self._connection_pairs: set[tuple[str, str]] = set()

    def parse_file(self, filepath: str) -> tuple[int, Graph]:
        """Parse a map file and return the drone count and graph.

        Args:
            filepath: Path to the map file to parse.

        Returns:
            A tuple of (nb_drones, graph).

        Raises:
            ParseError: If the file is missing, malformed, or invalid.
        """
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise ParseError(f"Error: file '{filepath}' not found")
        except PermissionError:
            raise ParseError(f"Error: permission denied for '{filepath}'")

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                self._parse_line(line)
            except ParseError as e:
                raise ParseError(f"Line {line_num}: {e}")

        self._validate()
        return self.nb_drones, self.graph

    def _parse_line(self, line: str) -> None:
        """Dispatch a line to the appropriate handler based on its prefix.

        Args:
            line: A stripped, non-empty, non-comment line.

        Raises:
            ParseError: If the line has an unknown directive.
        """
        if line.startswith("nb_drones:"):
            self._parse_nb_drones(line)
        elif line.startswith("connection:"):
            self._parse_connection(line)
        elif any(line.startswith(f"{role}:") for role in self.VALID_ROLES):
            self._parse_zone(line)
        else:
            raise ParseError(f"Error: unknown directive '{line}'")

    def _parse_nb_drones(self, line: str) -> None:
        """Parse the nb_drones directive.

        Args:
            line: The full line starting with 'nb_drones:'.

        Raises:
            ParseError: If value is missing or not positive.
        """
        if self.nb_drones != 0:
            raise ParseError("Error: duplicate nb_drones definition")
        value = line.split(":", 1)[1].strip()
        if not value:
            raise ParseError("Error: missing value for nb_drones")
        try:
            nb = int(value)
        except ValueError:
            raise ParseError(
                f"Error: nb_drones must be integer,"
                f" got '{value}'"
            )
        if nb <= 0:
            raise ParseError(f"Error: nb_drones must be positive, got {nb}")
        self.nb_drones = nb

    def _parse_zone(self, line: str) -> None:
        """Parse a zone directive (start_hub, end_hub, hub).

        Expected: <role>: <name> <x> <y> [key=val ...]

        Args:
            line: The full line with a valid role prefix.

        Raises:
            ParseError: If zone is malformed or invalid.
        """
        colon_idx = line.index(":")
        role_str = line[:colon_idx].strip()
        rest = line[colon_idx + 1:].strip()

        role = self.VALID_ROLES[role_str]

        if role == HubRole.START and self._has_start:
            raise ParseError("Error: duplicate start_hub definition")
        if role == HubRole.END and self._has_end:
            raise ParseError("Error: duplicate end_hub definition")

        bracket_metadata = self._extract_bracket_metadata(rest)
        rest_no_brackets = re.sub(r'\[.*?\]', '', rest).strip()

        parts = rest_no_brackets.split()
        if not parts:
            raise ParseError(f"Error: missing zone name for {role_str}")

        name = parts[0]
        if name in self._zone_names:
            raise ParseError(f"Error: duplicate zone name '{name}'")

        x: int = 0
        y: int = 0
        if len(parts) >= 3:
            try:
                x = int(parts[1])
                y = int(parts[2])
            except ValueError:
                raise ParseError(
                    f"Error: invalid coordinates for zone '{name}'"
                )

        zone_type_str = bracket_metadata.get("zone", "normal")
        if zone_type_str not in self.VALID_ZONE_TYPES:
            raise ParseError(
                f"Error: invalid zone type '{zone_type_str}' "
                f"(valid: {', '.join(sorted(self.VALID_ZONE_TYPES))})"
            )
        zone_type = ZoneType(zone_type_str)

        max_drones = self._parse_positive_int(
            bracket_metadata.get("max_drones", "1"), "max_drones"
        )
        color = bracket_metadata.get("color", None)

        zone = Zone(
            name=name,
            role=role,
            x=x,
            y=y,
            zone_type=zone_type,
            max_drones=max_drones,
            color=color,
        )

        self.graph.add_zone(zone)
        self._zone_names.add(name)

        if role == HubRole.START:
            self._has_start = True
        elif role == HubRole.END:
            self._has_end = True

    def _parse_connection(self, line: str) -> None:
        """Parse a connection directive.

        Expected: connection: <zone1>-<zone2> [metadata]

        Args:
            line: The full line starting with 'connection:'.

        Raises:
            ParseError: If connection is malformed or invalid.
        """
        rest = line.split(":", 1)[1].strip()

        bracket_metadata = self._extract_bracket_metadata(rest)
        rest_no_brackets = re.sub(r'\[.*?\]', '', rest).strip()

        parts = rest_no_brackets.split()
        if not parts:
            raise ParseError("Error: missing connection definition")

        link = parts[0]
        if "-" not in link:
            raise ParseError(
                f"Error: invalid connection format '{link}' "
                f"(expected zone1-zone2)"
            )

        segments = link.split("-", 1)
        zone_a = segments[0].strip()
        zone_b = segments[1].strip()

        if not zone_a or not zone_b:
            raise ParseError(f"Error: empty zone name in connection '{link}'")
        if zone_a == zone_b:
            raise ParseError(f"Error: self-connection not allowed '{link}'")

        pair = (min(zone_a, zone_b), max(zone_a, zone_b))
        if pair in self._connection_pairs:
            raise ParseError(
                f"Error: duplicate connection '{zone_a}-{zone_b}'"
            )

        cap_str = bracket_metadata.get(
            "max_link_capacity", "1"
        )
        capacity = self._parse_positive_int(
            cap_str, "max_link_capacity"
        )

        connection = Connection(
            zone_a=zone_a,
            zone_b=zone_b,
            max_link_capacity=capacity,
        )

        self.graph.add_connection(connection)
        self._connection_pairs.add(pair)

    def _extract_bracket_metadata(self, text: str) -> dict[str, str]:
        """Extract key=value pairs from bracketed metadata.

        Args:
            text: The text potentially containing [...] metadata.

        Returns:
            A dict of metadata key-value pairs.

        Raises:
            ParseError: If a metadata item is not in key=value format.
        """
        metadata: dict[str, str] = {}
        bracket_match = re.search(r'\[(.+?)\]', text)
        if bracket_match:
            for item in bracket_match.group(1).split():
                if "=" not in item:
                    raise ParseError(
                        f"Error: invalid metadata"
                        f" '{item}' (expected key=value)"
                    )
                key, value = item.split("=", 1)
                metadata[key.strip()] = value.strip()
        return metadata

    def _parse_positive_int(self, value: str, field: str) -> int:
        """Parse a string as a positive integer.

        Args:
            value: The string to parse.
            field: The field name for error messages.

        Returns:
            The parsed positive integer.

        Raises:
            ParseError: If the value is not a positive integer.
        """
        try:
            n = int(value)
        except ValueError:
            raise ParseError(
                f"Error: {field} must be integer,"
                f" got '{value}'"
            )
        if n <= 0:
            raise ParseError(f"Error: {field} must be positive, got {n}")
        return n

    def _validate(self) -> None:
        """Validate the parsed graph for completeness and consistency.

        Raises:
            ParseError: If nb_drones, start_hub, or end_hub is missing,
                if connections reference unknown zones, or if no path exists.
        """
        if self.nb_drones == 0:
            raise ParseError("Error: missing nb_drones definition")
        if not self._has_start:
            raise ParseError("Error: missing start_hub definition")
        if not self._has_end:
            raise ParseError("Error: missing end_hub definition")

        for conn in self.graph.connections:
            if conn.zone_a not in self._zone_names:
                raise ParseError(
                    "Error: connection references"
                    f" unknown zone '{conn.zone_a}'"
                )
            if conn.zone_b not in self._zone_names:
                raise ParseError(
                    "Error: connection references"
                    f" unknown zone '{conn.zone_b}'"
                )

        start = self.graph.start_zone
        end = self.graph.end_zone
        if start and end and not self._path_exists(start.name, end.name):
            raise ParseError(
                f"Error: no path exists from '{start.name}' to '{end.name}'"
            )

    def _path_exists(self, source: str, target: str) -> bool:
        """Check if a path exists between two zones using BFS.

        Args:
            source: Name of the starting zone.
            target: Name of the target zone.

        Returns:
            True if a path exists, False otherwise.
        """
        visited: set[str] = set()
        queue: list[str] = [source]
        while queue:
            current = queue.pop(0)
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            zone = self.graph.zones.get(current)
            if zone and not zone.is_accessible and current != source:
                continue
            for neighbor in self.graph.get_neighbors(current):
                if neighbor not in visited:
                    queue.append(neighbor)
        return False
