*This project has been created as part of the 42 curriculum by artcolom.*

# Fly-in

## Description

Fly-in is a drone routing simulator that navigates a fleet of drones from a start zone to an end zone through a network of connected zones, minimizing the total number of simulation turns. The program parses a map file describing zones (with types, capacities, and coordinates) and connections, then computes optimal paths and simulates turn-by-turn drone movements respecting all constraints (zone capacity, connection capacity, movement costs).

## Instructions

### Requirements

- Python 3.10+
- pygame (for visualization)

### Installation

```bash
make install
```

### Running

```bash
# Basic run (text output)
python3 main.py maps/easy/01_linear_path.txt

# With graphical visualization
python3 main.py --visual maps/hard/01_maze_nightmare.txt

# Using Makefile
make run MAP=maps/medium/02_circular_loop.txt
```

### Linting

```bash
make lint       # flake8 + mypy
make lint-strict # flake8 + mypy --strict
```

### Debug mode

```bash
make debug MAP=maps/easy/01_linear_path.txt
```

### Clean

```bash
make clean
```

## Algorithm Explanation

### Pathfinding: BFS + Yen's K-Shortest Paths

The algorithm uses a two-phase approach:

1. **Weighted BFS** finds the shortest path from start to end, taking into account zone movement costs (restricted zones cost 2 turns, priority zones cost 1 but are preferred). Blocked zones are excluded entirely.

2. **Yen's K-Shortest Paths** algorithm discovers up to K alternative paths by systematically deviating from previously found paths at each intermediate node. This provides multiple routing options for distributing drones.

### Path Selection and Drone Distribution

- **Conflict filtering**: Paths that traverse the same connection in opposite directions at bottleneck zones (capacity <= 2) are removed to prevent deadlocks.
- **Cost filtering**: Only minimum-cost paths are kept to avoid slower detours.
- **Greedy assignment**: Drones are assigned to paths one by one, always choosing the path that minimizes the drone's expected arrival time. The arrival time accounts for both path cost and pipeline delay (how long the drone must wait before departing due to zone constraints).

### Simulation Engine

The simulation proceeds turn by turn:

1. **Phase 1 (mandatory transits)**: Drones in transit toward restricted zones must complete their movement.
2. **Phase 2 (normal moves)**: Remaining drones advance along their paths, processed closest-to-end first so drones ahead free up space for those behind.

Capacity constraints (zone `max_drones` and connection `max_link_capacity`) are enforced in real-time. Drones leaving a zone free capacity for that same turn.

### Complexity

- **Pathfinding**: O(K * V * (V + E) * log V) where K is the number of paths, V is zones, E is connections.
- **Simulation**: O(T * D) where T is turns and D is drones per turn.
- Paths are computed once and cached; the simulation only evaluates movement constraints per turn.

## Visual Representation

The `--visual` flag opens an interactive Pygame window:

- **Zone colors**: Green = start, Red = end, Orange = restricted, Yellow = priority, Dark gray = blocked, Blue = normal
- **Zone labels**: S = start, E = end, R = restricted, P = priority, X = blocked
- **Drone colors**: Light slate = idle, Bright blue = moving, Amber = in transit (restricted), Green = arrived
- **Controls**: Space = pause/resume, Left/Right arrows = step through turns, +/- = adjust speed, Escape = quit
- Drones at the same position are spread in a circle for visibility
- Smooth animation with interpolation between turns at 60 FPS
- HUD panel at the top with turn counter, arrival counter, play/pause status, speed, and color legend

The visualization helps understand drone flow, identify bottlenecks, and verify that capacity constraints are respected.

## Example

### Input (`maps/easy/01_linear_path.txt`)

```
nb_drones: 2
start_hub: start 0 0
end_hub: end 3 0
hub: A 1 0
hub: B 2 0
connection: start-A
connection: A-B
connection: B-end
```

### Output

```
D1-A
D1-B D2-A
D1-end D2-B
D2-end
```

4 turns to route 2 drones through a linear 4-zone path.

### Performance Benchmarks

| Map | Drones | Target | Result |
|-----|--------|--------|--------|
| Linear path | 2 | <= 6 | 4 |
| Simple fork | 3 | <= 6 | 5 |
| Basic capacity | 4 | <= 8 | 6 |
| Dead end trap | 5 | <= 15 | 8 |
| Circular loop | 6 | <= 20 | 16 |
| Priority puzzle | 4 | <= 12 | 7 |
| Maze nightmare | 8 | <= 45 | 14 |
| Capacity hell | 12 | <= 60 | 18 |
| Ultimate challenge | 15 | <= 35 | 26 |
| Impossible dream | 25 | <= 45 | 43 |

## Testing & Validation

### Parser error handling

```bash
# Missing file
python3 main.py nonexistent.txt
# Error: file 'nonexistent.txt' not found

# Missing nb_drones
echo -e "start_hub: s 0 0\nend_hub: e 1 0\nconnection: s-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Error: missing nb_drones definition

# Invalid zone type
echo -e "nb_drones: 1\nstart_hub: s 0 0 [zone=invalid]\nend_hub: e 1 0\nconnection: s-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Line 2: Error: invalid zone type 'invalid_type' (valid: blocked, normal, priority, restricted)

# Missing start_hub
echo -e "nb_drones: 1\nend_hub: e 1 0\nhub: a 0 0\nconnection: a-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Error: missing start_hub definition

# Duplicate zone names
echo -e "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 1 0\nhub: s 2 0\nconnection: s-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Line 4: Error: duplicate zone name 's'

# Disconnected graph (no path)
echo -e "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 5 0\nhub: island 3 3\nconnection: s-island" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Error: no path exists from 's' to 'e'

# Invalid capacity (zero)
echo -e "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 1 0\nhub: m 0 1 [max_drones=0]\nconnection: s-m\nconnection: m-e\nconnection: s-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# Line 4: Error: max_drones must be positive, got 0
```

### Zone mechanics verification

```bash
# Restricted zone costs 2 turns (transit visible in output)
echo -e "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 2 0\nhub: r 1 0 [zone=restricted]\nconnection: s-r\nconnection: r-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# D1-s-r      <- drone enters transit on connection
# D1-r        <- drone arrives at restricted zone (2 turns total)
# D1-e

# Blocked zone is avoided
echo -e "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 3 0\nhub: blocked 1 0 [zone=blocked]\nhub: alt 1 1\nconnection: s-blocked\nconnection: blocked-e\nconnection: s-alt\nconnection: alt-e" > /tmp/test.txt
python3 main.py /tmp/test.txt
# D1-alt      <- avoids blocked zone
# D1-e

# Connection capacity enforced (2 drones max per link)
echo -e "nb_drones: 4\nstart_hub: s 0 0\nend_hub: e 2 0\nhub: m 1 0 [max_drones=4]\nconnection: s-m [max_link_capacity=2]\nconnection: m-e [max_link_capacity=2]" > /tmp/test.txt
python3 main.py /tmp/test.txt
# D1-m D2-m           <- 2 drones max per turn on s-m
# D1-e D2-e D3-m D4-m <- 2 on m-e, 2 on s-m
# D3-e D4-e
```

### Run all benchmarks

```bash
for f in maps/easy/*.txt maps/medium/*.txt maps/hard/*.txt maps/challenger/*.txt; do
    turns=$(python3 main.py "$f" | wc -l)
    echo "$(basename $f): $turns turns"
done
```

### Simulation validity check (all drones arrive)

```bash
python3 -c "
import os
from src.parser import Parser
from src.simulator import Simulator
for root, dirs, files in sorted(os.walk('maps')):
    for f in sorted(files):
        if not f.endswith('.txt'): continue
        path = os.path.join(root, f)
        p = Parser()
        nd, g = p.parse_file(path)
        end = g.end_zone.name
        output = Simulator(g, nd).run()
        arrived = set()
        for line in output:
            for t in line.split():
                if t.endswith('-' + end):
                    arrived.add(t[:t.index('-')])
        ok = 'OK' if len(arrived) == nd else 'FAIL'
        print(f'{f}: {len(arrived)}/{nd} arrived - {ok}')
"
```

### Linting

```bash
make lint
# flake8: 0 errors
# mypy: Success: no issues found in 8 source files
```

## Resources

- [Yen's algorithm (Wikipedia)](https://en.wikipedia.org/wiki/Yen%27s_algorithm) - K-shortest paths algorithm
- [BFS (Wikipedia)](https://en.wikipedia.org/wiki/Breadth-first_search) - Graph traversal for shortest path
- AI (Claude) was used to assist with code structure, debugging, and documentation. It was also used for algorithm research (Yen's K-shortest paths, BFS strategies), the Pygame visualizer rewrite, the Makefile, and this README. All code was reviewed, understood, and adapted manually.
