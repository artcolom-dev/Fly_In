"""Pathfinding module for computing drone routes through the graph."""

from __future__ import annotations

import heapq
from collections import deque
from typing import Optional

from src.graph import Graph


class PathFinder:
    """Find paths through the zone graph using BFS.

    Accounts for zone movement costs:
    - normal/priority: 1 turn
    - restricted: 2 turns
    - blocked: inaccessible

    Attributes:
        graph: The zone/connection graph to search.
    """

    def __init__(self, graph: Graph) -> None:
        """Initialize the pathfinder with a graph.

        Args:
            graph: The parsed graph with zones and connections.
        """
        self.graph: Graph = graph

    def find_shortest_path(
        self,
        start: str,
        end: str,
        blocked_edges: Optional[set[tuple[str, str]]] = None,
    ) -> Optional[list[str]]:
        """Find the shortest path from start to end using BFS.

        Priority zones are preferred: when two paths have the same
        length, the one using more priority zones wins.

        Args:
            start: Name of the starting zone.
            end: Name of the destination zone.
            blocked_edges: Optional set of (from, to) edges to avoid.

        Returns:
            List of zone names from start to end (inclusive),
            or None if no path exists.
        """
        if blocked_edges is None:
            blocked_edges = set()

        # BFS: queue holds (current_zone, path_so_far)
        queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
        visited: set[str] = {start}

        while queue:
            current, path = queue.popleft()

            if current == end:
                return path

            for neighbor in self.graph.get_neighbors(current):
                if neighbor in visited:
                    continue
                if (current, neighbor) in blocked_edges:
                    continue

                zone = self.graph.zones.get(neighbor)
                if zone is None or not zone.is_accessible:
                    continue

                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

        return None

    def find_paths(self, start: str, end: str, k: int) -> list[list[str]]:
        """Find up to k shortest paths using Yen's algorithm.

        For each confirmed path, tries every node as a spur point:
        blocks the edge used by previous paths at that point and
        blocks earlier nodes, then searches for an alternative.

        Args:
            start: Name of the starting zone.
            end: Name of the destination zone.
            k: Maximum number of paths to find.

        Returns:
            List of paths sorted by length.
        """
        best = self.find_shortest_path(start, end)
        if best is None:
            return []

        confirmed: list[list[str]] = [best]
        candidates: list[tuple[int, int, list[str]]] = []
        seen: set[tuple[str, ...]] = {tuple(best)}
        counter: int = 0

        for i in range(1, k):
            prev_path = confirmed[i - 1]

            for j in range(len(prev_path) - 1):
                spur_node = prev_path[j]
                root = prev_path[:j + 1]

                blocked: set[tuple[str, str]] = set()

                # Block the edge at spur point for each confirmed path
                for p in confirmed:
                    if p[:j + 1] == root and j + 1 < len(p):
                        blocked.add((p[j], p[j + 1]))
                        blocked.add((p[j + 1], p[j]))

                # Block root nodes (except spur) so we don't loop back
                for node in root[:-1]:
                    for nb in self.graph.get_neighbors(node):
                        blocked.add((node, nb))
                        blocked.add((nb, node))

                spur = self.find_shortest_path(spur_node, end, blocked)
                if spur is not None:
                    full = root[:-1] + spur
                    key = tuple(full)
                    if key not in seen:
                        seen.add(key)
                        counter += 1
                        heapq.heappush(
                            candidates, (len(full), counter, full)
                        )

            if not candidates:
                break

            _, _, next_path = heapq.heappop(candidates)
            confirmed.append(next_path)

        return confirmed

    def path_cost(self, path: list[str]) -> int:
        """Calculate the total movement cost of a path in turns.

        Args:
            path: List of zone names in order.

        Returns:
            Total cost in turns.
        """
        cost: int = 0
        for zone_name in path[1:]:  # skip start zone
            zone = self.graph.zones.get(zone_name)
            if zone is None:
                continue
            cost += zone.move_cost
        return cost
