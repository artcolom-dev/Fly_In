#!/usr/bin/env python3
"""Entry point for the Fly-in drone simulation."""

import argparse
import sys

from src.parser import ParseError, Parser
from src.simulator import Simulator


def main() -> None:
    """Parse a map file and run the drone simulation."""
    ap = argparse.ArgumentParser(description="Fly-in drone simulation")
    ap.add_argument("map_file", help="Path to the map file")
    ap.add_argument("--visual", action="store_true",
                    help="Launch Pygame visualizer")
    ap.add_argument("--capacity_info", action="store_true"
    , help="Show Capacity")

    args = ap.parse_args()

    parser = Parser()

    try:
        nb_drones, graph = parser.parse_file(args.map_file)
    except ParseError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    sim = Simulator(graph, nb_drones, capacity_info=args.capacity_info)  # LIVE CODING: Simulator(graph, nb_drones, capacity_info=args.capacity_info)
    output = sim.run()

    if args.visual:
        from src.visualizer import Visualizer
        viz = Visualizer(graph, nb_drones, output, capacity_info=args.capacity_info)  # LIVE CODING: Visualizer(graph, nb_drones, output, capacity_info=args.capacity_info)
        viz.run()
    else:
        for line in output:
            print(line)


if __name__ == "__main__":
    main()
