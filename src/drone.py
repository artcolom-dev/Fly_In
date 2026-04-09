"""Drone module representing individual drones in the simulation."""

from __future__ import annotations

from typing import Optional


class Drone:
    """Represent a single drone navigating through the zone graph.

    A drone has an ID, a current position, and tracks whether
    it is in transit (on a connection toward a restricted zone)
    or has arrived at the end zone.

    Attributes:
        id: Unique drone identifier (1-based).
        position: Name of the zone the drone is currently in.
        path: Assigned route as a list of zone names.
        path_idx: Current index in the path (0 = start zone).
        arrived: Whether the drone has reached the end zone.
        in_transit: Whether the drone is on a connection (restricted move).
        transit_dest: Destination zone name during transit.
        transit_conn: Connection label for output during transit.
    """

    def __init__(self, drone_id: int, start_zone: str) -> None:
        """Initialize a drone at the start zone.

        Args:
            drone_id: Unique identifier for this drone.
            start_zone: Name of the starting zone.
        """
        self.id: int = drone_id
        self.position: str = start_zone
        self.path: list[str] = []
        self.path_idx: int = 0
        self.arrived: bool = False
        self.in_transit: bool = False
        self.transit_dest: Optional[str] = None
        self.transit_conn: Optional[str] = None

    @property
    def next_zone(self) -> Optional[str]:
        """Return the next zone in the drone's assigned path.

        Returns:
            Name of the next zone, or None if at end of path.
        """
        next_idx = self.path_idx + 1
        if next_idx < len(self.path):
            return self.path[next_idx]
        return None

    @property
    def remaining_steps(self) -> int:
        """Return how many steps remain to reach the end of the path.

        Returns:
            Number of zones left to visit.
        """
        return len(self.path) - 1 - self.path_idx

    def start_transit(self, dest: str, conn_label: str) -> None:
        """Begin a 2-turn move toward a restricted zone.

        The drone leaves its current zone and occupies the connection
        for one turn. It MUST arrive at dest on the next turn.

        Args:
            dest: Name of the destination restricted zone.
            conn_label: Connection label (e.g. "zoneA-zoneB") for output.
        """
        self.in_transit = True
        self.transit_dest = dest
        self.transit_conn = conn_label
        self.position = ""

    def finish_transit(self) -> None:
        """Complete the 2-turn move by arriving at the restricted zone."""
        if self.transit_dest is not None:
            self.position = self.transit_dest
        self.in_transit = False
        self.transit_dest = None
        self.transit_conn = None

    def move_to(self, zone_name: str) -> None:
        """Move the drone to a normal zone in one turn.

        Args:
            zone_name: Name of the destination zone.
        """
        self.position = zone_name

    def __repr__(self) -> str:
        """Return a string representation of the drone."""
        if self.arrived:
            return f"Drone(D{self.id}, arrived)"
        if self.in_transit:
            return f"Drone(D{self.id}, transit->{self.transit_dest})"
        return f"Drone(D{self.id}, {self.position})"
