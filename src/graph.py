from __future__ import annotations
from enum import Enum
from typing import Optional


class ZoneType(Enum):
    """Enumeration of possible zone types with different traversal costs."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


class HubRole(Enum):
    """Enumeration of zone roles in the graph topology."""

    START = "start_hub"
    END = "end_hub"
    INTERMEDIATE = "hub"


class Zone:
    """Represent a node in the drone flight graph."""

    def __init__(
        self,
        name: str,
        role: HubRole,
        x: int = 0,
        y: int = 0,
        zone_type: ZoneType = ZoneType.NORMAL,
        max_drones: int = 1,
        color: Optional[str] = None,
    ) -> None:
        """Initialize a zone with its properties.

        Args:
            name: Unique identifier for the zone.
            role: Role of the zone (start, end, or intermediate).
            x: X coordinate for visualization.
            y: Y coordinate for visualization.
            zone_type: Type affecting traversal cost.
            max_drones: Maximum simultaneous drone occupancy.
            color: Hex color for visualization.
        """
        self.name: str = name
        self.role: HubRole = role
        self.x: int = x
        self.y: int = y
        self.zone_type: ZoneType = zone_type
        self.max_drones: int = max_drones
        self.color: Optional[str] = color

    @property
    def move_cost(self) -> int:
        """Return the number of turns needed to traverse this zone.

        Returns:
            2 for restricted zones, 1 otherwise.
        """
        if self.zone_type == ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_accessible(self) -> bool:
        """Check if drones can enter this zone.

        Returns:
            False if the zone is blocked, True otherwise.
        """
        return self.zone_type != ZoneType.BLOCKED

    def __repr__(self) -> str:
        """Return a string representation of the zone."""
        return f"Zone({self.name}, {self.role.value}, {self.zone_type.value})"


class Connection:
    """Represent a bidirectional link between two zones."""

    def __init__(
        self,
        zone_a: str,
        zone_b: str,
        max_link_capacity: int = 1,
    ) -> None:
        """Initialize a connection between two zones.

        Args:
            zone_a: Name of the first zone.
            zone_b: Name of the second zone.
            max_link_capacity: Max drones traversing simultaneously.
        """
        self.zone_a: str = zone_a
        self.zone_b: str = zone_b
        self.max_link_capacity: int = max_link_capacity

    def connects(self, zone_name: str) -> Optional[str]:
        """Return the other zone name if this connection involves zone_name.

        Args:
            zone_name: The zone to check against.

        Returns:
            The other zone's name, or None if not part.
        """
        if self.zone_a == zone_name:
            return self.zone_b
        if self.zone_b == zone_name:
            return self.zone_a
        return None

    def __repr__(self) -> str:
        """Return a string representation of the connection."""
        return (
            f"Connection({self.zone_a}-{self.zone_b},"
            f" cap={self.max_link_capacity})"
        )


class Graph:
    """Represent the drone flight network as an adjacency list graph."""

    def __init__(self) -> None:
        """Initialize an empty graph."""
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.adjacency: dict[str, list[str]] = {}

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the graph.

        Args:
            zone: The Zone object to add.
        """
        self.zones[zone.name] = zone
        if zone.name not in self.adjacency:
            self.adjacency[zone.name] = []

    def add_connection(self, connection: Connection) -> None:
        """Add a connection and update the adjacency list.

        Args:
            connection: The Connection object to add.
        """
        self.connections.append(connection)
        if connection.zone_a not in self.adjacency:
            self.adjacency[connection.zone_a] = []
        if connection.zone_b not in self.adjacency:
            self.adjacency[connection.zone_b] = []
        self.adjacency[connection.zone_a].append(connection.zone_b)
        self.adjacency[connection.zone_b].append(connection.zone_a)

    def get_neighbors(self, zone_name: str) -> list[str]:
        """Return the list of adjacent zone names.

        Args:
            zone_name: The zone to get neighbors for.

        Returns:
            List of neighboring zone names.
        """
        return self.adjacency.get(zone_name, [])

    def get_connection(self, zone_a: str, zone_b: str) -> Optional[Connection]:
        """Return the connection between two zones.

        Args:
            zone_a: Name of the first zone.
            zone_b: Name of the second zone.

        Returns:
            The Connection object, or None if not found.
        """
        for conn in self.connections:
            if (conn.zone_a == zone_a and conn.zone_b == zone_b) or \
               (conn.zone_a == zone_b and conn.zone_b == zone_a):
                return conn
        return None

    @property
    def start_zone(self) -> Optional[Zone]:
        """Return the start hub zone.

        Returns:
            The Zone with START role, or None.
        """
        for zone in self.zones.values():
            if zone.role == HubRole.START:
                return zone
        return None

    @property
    def end_zone(self) -> Optional[Zone]:
        """Return the end hub zone.

        Returns:
            The Zone with END role, or None.
        """
        for zone in self.zones.values():
            if zone.role == HubRole.END:
                return zone
        return None

    def __repr__(self) -> str:
        """Return a string representation of the graph."""
        return (
            f"Graph(zones={len(self.zones)}, "
            f"connections={len(self.connections)})"
        )
