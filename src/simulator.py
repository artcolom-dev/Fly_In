"""Simulator module for running the drone simulation turn by turn."""

from __future__ import annotations

from src.drone import Drone
from src.graph import Graph, HubRole, Zone, ZoneType
from src.pathfinding import PathFinder


class Simulator:
    """Run the drone simulation on a graph.

    Finds paths for each drone, then executes the simulation
    turn by turn, respecting all capacity constraints.

    Attributes:
        graph: The zone/connection graph.
        drones: List of all drones.
        start_zone: Name of the start zone.
        end_zone: Name of the end zone.
    """

    def __init__(
        self, graph: Graph, nb_drones: int,
        capacity_info: bool = False,
    ) -> None:
        """Initialize the simulator and assign paths to drones.

        Args:
            graph: The parsed graph with zones and connections.
            nb_drones: Number of drones to simulate.
            capacity_info: If True, append capacity usage to output.
        """
        self.graph: Graph = graph
        self.capacity_info: bool = capacity_info

        start = graph.start_zone
        end = graph.end_zone
        assert start is not None and end is not None

        self.start_zone: str = start.name
        self.end_zone: str = end.name

        self.drones: list[Drone] = [
            Drone(i + 1, self.start_zone) for i in range(nb_drones)
        ]

        self._assign_paths()

    def _assign_paths(self) -> None:
        """Find paths and distribute drones across them.

        Uses PathFinder to find multiple paths, filters out
        conflicting paths (those that traverse the same edge
        in opposite directions at bottleneck zones), keeps
        only minimum-cost paths, then assigns drones greedily.
        """
        finder = PathFinder(self.graph)
        paths = finder.find_paths(
            self.start_zone, self.end_zone, len(self.drones)
        )

        if not paths:
            return

        paths = self._filter_conflicting(paths)

        # Keep only minimum-cost paths to avoid spreading
        # drones across longer detours that slow the pipeline.
        all_costs = [finder.path_cost(p) for p in paths]
        min_cost = min(all_costs)
        paths = [
            p for p, c in zip(paths, all_costs) if c == min_cost
        ]

        counts: list[int] = [0] * len(paths)
        costs: list[int] = [finder.path_cost(p) for p in paths]
        delays: list[int] = [
            self._pipeline_delay(p) for p in paths
        ]

        for drone in self.drones:
            best_idx = 0
            best_time = costs[0] + counts[0] * delays[0]
            for i in range(1, len(paths)):
                t = costs[i] + counts[i] * delays[i]
                if t < best_time:
                    best_time = t
                    best_idx = i

            drone.path = paths[best_idx]
            counts[best_idx] += 1

    def _filter_conflicting(
        self, paths: list[list[str]]
    ) -> list[list[str]]:
        """Remove paths that use edges in opposite directions at bottlenecks.

        Two paths conflict if they traverse the same connection
        in opposite directions and at least one endpoint is a
        bottleneck zone (capacity <= 2, not start/end).

        Paths are processed in order (shortest first from Yen's),
        so cheaper paths are kept and expensive conflicting ones
        are dropped.

        Args:
            paths: List of paths sorted by cost.

        Returns:
            Filtered list of non-conflicting paths.
        """
        result: list[list[str]] = []
        used_edges: set[tuple[str, str]] = set()

        for path in paths:
            conflict = False
            path_edges: list[tuple[str, str]] = []

            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                reverse = (path[i + 1], path[i])

                if reverse in used_edges:
                    zone_a = self.graph.zones.get(edge[0])
                    zone_b = self.graph.zones.get(edge[1])
                    if self._is_bottleneck(zone_a) or \
                            self._is_bottleneck(zone_b):
                        conflict = True
                        break

                path_edges.append(edge)

            if not conflict:
                for edge in path_edges:
                    used_edges.add(edge)
                result.append(path)

        return result

    def _is_bottleneck(self, zone: Zone | None) -> bool:
        """Check if a zone is a capacity bottleneck.

        Args:
            zone: The zone to check.

        Returns:
            True if the zone has limited capacity (not start/end).
        """
        if zone is None:
            return False
        if zone.role in (HubRole.START, HubRole.END):
            return False
        return zone.max_drones <= 2

    def _pipeline_delay(self, path: list[str]) -> int:
        """Return the pipeline throughput delay for a path.

        If the path contains restricted zones, drones can only
        pass through every 2 turns, so the delay is 2.

        Args:
            path: List of zone names.

        Returns:
            1 for normal paths, 2 if restricted zones are present.
        """
        for zone_name in path[1:-1]:
            zone = self.graph.zones.get(zone_name)
            if zone and zone.move_cost > 1:
                return 2
        return 1

    def run(self) -> list[str]:
        """Run the simulation until all drones arrive.

        Returns:
            List of output lines, one per turn.
        """
        output: list[str] = []
        max_turns = 1000

        for _ in range(max_turns):
            if self._all_arrived():
                break
            line = self._execute_turn()
            if line:
                output.append(line)

        return output

    def _all_arrived(self) -> bool:
        """Check if every drone has reached the end zone.

        Returns:
            True if all drones have arrived.
        """
        return all(d.arrived for d in self.drones)

    def _execute_turn(self) -> str:
        """Execute one simulation turn.

        Phase 1: Drones in transit MUST finish (restricted arrival).
        Phase 2: Other drones advance along their path if possible.

        Drones are processed closest-to-end first so that drones
        ahead move out and free up space for those behind.

        Returns:
            Output line for this turn.
        """
        movements: list[str] = []

        # Track capacity changes for this turn
        # zone_name -> number of drones entering
        entering: dict[str, int] = {}
        # zone_name -> number of drones leaving
        leaving: dict[str, int] = {}
        # (zone_a, zone_b) normalized -> number of drones using it
        conn_used: dict[tuple[str, str], int] = {}

        # Phase 1: finish all mandatory transits
        moved: set[int] = set()
        for drone in self.drones:
            if not drone.in_transit:
                continue

            dest = drone.transit_dest
            assert dest is not None

            drone.finish_transit()
            drone.path_idx += 1
            movements.append(f"D{drone.id}-{drone.position}")
            moved.add(drone.id)

            entering[dest] = entering.get(dest, 0) + 1

            if drone.position == self.end_zone:
                drone.arrived = True

        # Phase 2: move drones along their paths
        # Exclude drones that already moved in phase 1
        # Sort: drones closest to end first (fewest remaining steps)
        active = [
            d for d in self.drones
            if not d.arrived and d.id not in moved
            and not d.in_transit and d.next_zone is not None
        ]
        active.sort(key=lambda d: d.remaining_steps)

        for drone in active:
            target = drone.next_zone
            if target is None:
                continue

            if not self._can_move(
                drone, target, leaving, entering, conn_used
            ):
                continue

            # Record capacity changes
            leaving[drone.position] = (
                leaving.get(drone.position, 0) + 1
            )

            pair = self._conn_pair(drone.position, target)
            conn_used[pair] = conn_used.get(pair, 0) + 1

            # Check if target is a restricted zone
            zone = self.graph.zones[target]
            if zone.zone_type == ZoneType.RESTRICTED:
                conn_label = f"{drone.position}-{target}"
                drone.start_transit(target, conn_label)
                movements.append(f"D{drone.id}-{conn_label}")
            else:
                drone.move_to(target)
                drone.path_idx += 1
                entering[target] = entering.get(target, 0) + 1
                movements.append(f"D{drone.id}-{target}")

                if target == self.end_zone:
                    drone.arrived = True

        result = " ".join(movements)

        if self.capacity_info and movements:
            zone_info: list[str] = []
            for d in self.drones:
                if d.position and not d.arrived and not d.in_transit:
                    z = self.graph.zones[d.position]
                    if z.role not in (HubRole.START, HubRole.END):
                        zone_info.append(
                            f"Zone {d.position}: {z.max_drones} max"
                        )
            if zone_info:
                result += "\n  " + ", ".join(sorted(set(zone_info)))
            conn_info: list[str] = []
            for (a, b), used in sorted(conn_used.items()):
                conn = self.graph.get_connection(a, b)
                if conn:
                    conn_info.append(
                        f"Connection {a}-{b}: "
                        f"{used}/{conn.max_link_capacity} used"
                    )
            if conn_info:
                result += "\n  " + ", ".join(conn_info)

        return result

    def _can_move(
        self,
        drone: Drone,
        target: str,
        leaving: dict[str, int],
        entering: dict[str, int],
        conn_used: dict[tuple[str, str], int],
    ) -> bool:
        """Check if a drone can move to target this turn.

        Args:
            drone: The drone that wants to move.
            target: Destination zone name.
            leaving: Zones being vacated this turn and count.
            entering: Zones being entered this turn and count.
            conn_used: Connection usage this turn.

        Returns:
            True if the move respects all constraints.
        """
        zone = self.graph.zones.get(target)
        if zone is None or not zone.is_accessible:
            return False

        # Check connection capacity
        conn = self.graph.get_connection(drone.position, target)
        if conn is None:
            return False

        pair = self._conn_pair(drone.position, target)
        if conn_used.get(pair, 0) >= conn.max_link_capacity:
            return False

        # Start and end zones: unlimited capacity
        if zone.role in (HubRole.START, HubRole.END):
            return True

        # Zone capacity check:
        # current occupants - those leaving + those entering + 1
        current = sum(
            1 for d in self.drones
            if d.position == target and not d.arrived and not d.in_transit
        )
        will_leave = leaving.get(target, 0)
        will_enter = entering.get(target, 0)

        future = current - will_leave + will_enter + 1
        return future <= zone.max_drones

    @staticmethod
    def _conn_pair(zone_a: str, zone_b: str) -> tuple[str, str]:
        """Normalize a connection pair for consistent dict keys.

        Args:
            zone_a: First zone name.
            zone_b: Second zone name.

        Returns:
            Tuple with names in sorted order.
        """
        if zone_a < zone_b:
            return (zone_a, zone_b)
        return (zone_b, zone_a)
