"""Visualizer module for animating the drone simulation with Pygame."""

from __future__ import annotations

import math
from typing import Optional

import pygame

from src.graph import Graph, HubRole, Zone, ZoneType

# ── Visualizer color code ──────────────────────────────────────
# Zones (circles):
#   Green      = start hub (S)
#   Red        = end hub (E)
#   Blue       = normal zone
#   Yellow     = priority zone (P)
#   Orange     = restricted zone (R), costs 2 turns
#   Dark gray  = blocked zone (X), impassable
#
# Drones (small numbered circles):
#   Light slate = idle, waiting for its turn
#   Bright blue = moving this turn
#   Amber       = in transit toward a restricted zone
#   Green       = arrived at destination
#
# Controls:
#   Space = pause/resume | Arrows = step | +/- = speed
#   Scroll = zoom | Click+drag = pan | F = fit | Esc = quit
# ───────────────────────────────────────────────────────────────

_BG = (30, 30, 40)
_PANEL_BG = (40, 40, 55)
_EDGE_COLOR = (70, 70, 90)
_TEXT_COLOR = (200, 200, 210)
_TEXT_DIM = (120, 120, 140)

_ZONE_COLORS: dict[str, tuple[int, int, int]] = {
    "start": (46, 204, 113),       # green
    "end": (231, 76, 60),          # red
    "normal": (100, 149, 237),     # cornflower blue
    "priority": (241, 196, 15),    # yellow
    "restricted": (230, 126, 34),  # orange
    "blocked": (80, 80, 80),       # dark gray
}

_DRONE_COLORS: dict[str, tuple[int, int, int]] = {
    "idle": (149, 165, 196),       # light slate
    "moving": (52, 152, 219),      # bright blue
    "transit": (243, 156, 18),     # amber
    "arrived": (46, 204, 113),     # green
}

_DRONE_RADIUS = 8
_ZONE_RADIUS = 20
_FPS = 60
_HUD_HEIGHT = 50


class Visualizer:

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        output_lines: list[str],
        capacity_info: bool = False,
    ) -> None:
        self.graph = graph
        self.nb_drones = nb_drones
        self.capacity_info = capacity_info

        start = graph.start_zone
        end = graph.end_zone
        assert start is not None and end is not None
        self.start_name: str = start.name
        self.end_name: str = end.name

        self.node_pos: dict[str, tuple[float, float]] = {
            name: (float(z.x), float(z.y))
            for name, z in graph.zones.items()
        }

        self.frames = self._build_frames(output_lines)

        self._cam_x: float = 0.0
        self._cam_y: float = 0.0
        self._zoom: float = 80.0
        self._width: int = 0
        self._height: int = 0

    def _build_frames(
        self, output_lines: list[str],
    ) -> list[dict[int, tuple[float, float, str]]]:
        positions: dict[int, str] = {
            i + 1: self.start_name
            for i in range(self.nb_drones)
        }
        transit: dict[int, Optional[tuple[str, str]]] = {
            i + 1: None for i in range(self.nb_drones)
        }
        arrived: set[int] = set()

        frames: list[dict[int, tuple[float, float, str]]] = []
        frames.append(
            self._snap(positions, transit, arrived, set())
        )

        self._zone_maps: list[dict[int, str]] = [
            dict(positions),
        ]
        self._arrived_maps: list[set[int]] = [set()]
        self._transit_maps: list[set[int]] = [set()]
        self._conn_usage_maps: list[
            dict[tuple[str, str], int]
        ] = [{}]

        for line in output_lines:
            move_line = line.split('\n')[0].strip()
            if not move_line:
                continue

            moved: set[int] = set()
            turn_conn: dict[tuple[str, str], int] = {}

            for token in move_line.split():
                first_dash = token.index("-")
                drone_id = int(token[1:first_dash])
                rest = token[first_dash + 1:]
                moved.add(drone_id)

                if rest in self.graph.zones:
                    old = positions[drone_id]
                    pair = (min(old, rest), max(old, rest))
                    turn_conn[pair] = (
                        turn_conn.get(pair, 0) + 1
                    )
                    positions[drone_id] = rest
                    transit[drone_id] = None
                    if rest == self.end_name:
                        arrived.add(drone_id)
                else:
                    src = positions[drone_id]
                    dest = rest[len(src) + 1:]
                    pair = (min(src, dest), max(src, dest))
                    turn_conn[pair] = (
                        turn_conn.get(pair, 0) + 1
                    )
                    transit[drone_id] = (src, dest)

            frames.append(
                self._snap(positions, transit, arrived, moved)
            )
            self._zone_maps.append(dict(positions))
            self._arrived_maps.append(set(arrived))
            self._transit_maps.append(
                {d for d, t in transit.items() if t is not None}
            )
            self._conn_usage_maps.append(turn_conn)

        return frames

    def _snap(
        self,
        positions: dict[int, str],
        transit: dict[int, Optional[tuple[str, str]]],
        arrived: set[int],
        moved: set[int],
    ) -> dict[int, tuple[float, float, str]]:
        raw: dict[int, tuple[float, float]] = {}
        status: dict[int, str] = {}

        for did in range(1, self.nb_drones + 1):
            if did in arrived:
                raw[did] = self.node_pos[self.end_name]
                status[did] = "arrived"
            elif transit[did] is not None:
                t = transit[did]
                assert t is not None
                src, dest = t
                sx, sy = self.node_pos[src]
                dx, dy = self.node_pos[dest]
                raw[did] = ((sx + dx) / 2, (sy + dy) / 2)
                status[did] = "transit"
            else:
                raw[did] = self.node_pos[positions[did]]
                status[did] = (
                    "moving" if did in moved else "idle"
                )

        groups: dict[tuple[float, float], list[int]] = {}
        for did, (x, y) in raw.items():
            key = (round(x, 3), round(y, 3))
            groups.setdefault(key, []).append(did)

        result: dict[int, tuple[float, float, str]] = {}
        radius = 0.15
        for (bx, by), dids in groups.items():
            n = len(dids)
            for i, did in enumerate(dids):
                if n == 1:
                    result[did] = (bx, by, status[did])
                else:
                    angle = 2 * math.pi * i / n
                    result[did] = (
                        bx + radius * math.cos(angle),
                        by + radius * math.sin(angle),
                        status[did],
                    )

        return result

    def _to_screen(self, gx: float, gy: float) -> tuple[int, int]:
        sx = int((gx - self._cam_x) * self._zoom + self._width / 2)
        sy = int(-(gy - self._cam_y) * self._zoom
                 + (self._height + _HUD_HEIGHT) / 2)
        return (sx, sy)

    def _fit_to_screen(self) -> None:
        if not self.node_pos:
            return

        xs = [p[0] for p in self.node_pos.values()]
        ys = [p[1] for p in self.node_pos.values()]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        self._cam_x = (min_x + max_x) / 2
        self._cam_y = (min_y + max_y) / 2

        range_x = max_x - min_x if max_x != min_x else 1.0
        range_y = max_y - min_y if max_y != min_y else 1.0

        pad = 120
        avail_w = self._width - pad
        avail_h = self._height - _HUD_HEIGHT - pad

        self._zoom = min(avail_w / range_x, avail_h / range_y)

    def _zoom_at(self, mx: int, my: int, factor: float) -> None:
        gx = (mx - self._width / 2) / self._zoom + self._cam_x
        gy = -((my - (self._height + _HUD_HEIGHT) / 2)
               / self._zoom) + self._cam_y

        self._zoom *= factor
        self._zoom = max(10.0, min(self._zoom, 800.0))

        self._cam_x = gx - (mx - self._width / 2) / self._zoom
        self._cam_y = gy + ((my - (self._height + _HUD_HEIGHT) / 2)
                            / self._zoom)

    @staticmethod
    def _zone_color(zone: Zone) -> tuple[int, int, int]:
        if zone.role == HubRole.START:
            return _ZONE_COLORS["start"]
        if zone.role == HubRole.END:
            return _ZONE_COLORS["end"]
        if zone.zone_type == ZoneType.RESTRICTED:
            return _ZONE_COLORS["restricted"]
        if zone.zone_type == ZoneType.PRIORITY:
            return _ZONE_COLORS["priority"]
        if zone.zone_type == ZoneType.BLOCKED:
            return _ZONE_COLORS["blocked"]
        return _ZONE_COLORS["normal"]

    @staticmethod
    def _lerp_color(
        a: tuple[int, int, int],
        b: tuple[int, int, int],
        t: float,
    ) -> tuple[int, int, int]:
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    def _draw_edges(self, surface: pygame.Surface) -> None:
        for conn in self.graph.connections:
            a = self._to_screen(*self.node_pos[conn.zone_a])
            b = self._to_screen(*self.node_pos[conn.zone_b])
            pygame.draw.aaline(surface, _EDGE_COLOR, a, b)

    def _draw_zones(
        self,
        surface: pygame.Surface,
        font_name: pygame.font.Font,
        font_info: pygame.font.Font,
    ) -> None:
        for name, zone in self.graph.zones.items():
            cx, cy = self._to_screen(*self.node_pos[name])
            color = self._zone_color(zone)

            glow = self._lerp_color(color, _BG, 0.6)
            pygame.draw.circle(
                surface, glow, (cx, cy), _ZONE_RADIUS + 4,
            )

            pygame.draw.circle(
                surface, color, (cx, cy), _ZONE_RADIUS,
            )

            pygame.draw.circle(
                surface, (255, 255, 255), (cx, cy),
                _ZONE_RADIUS, 2,
            )

            txt = font_name.render(name, True, _TEXT_COLOR)
            surface.blit(
                txt,
                (cx - txt.get_width() // 2,
                 cy - _ZONE_RADIUS - 18),
            )

            label = ""
            if zone.role == HubRole.START:
                label = "S"
            elif zone.role == HubRole.END:
                label = "E"
            elif zone.zone_type == ZoneType.RESTRICTED:
                label = "R"
            elif zone.zone_type == ZoneType.PRIORITY:
                label = "P"
            elif zone.zone_type == ZoneType.BLOCKED:
                label = "X"

            if label:
                lt = font_info.render(label, True, (255, 255, 255))
                surface.blit(
                    lt,
                    (cx - lt.get_width() // 2,
                     cy - lt.get_height() // 2),
                )

    def _draw_drones(
        self,
        surface: pygame.Surface,
        frame: dict[int, tuple[float, float, str]],
        font: pygame.font.Font,
        anim_t: float,
        prev_frame: Optional[dict[int, tuple[float, float, str]]],
    ) -> None:
        for did in range(1, self.nb_drones + 1):
            gx, gy, status = frame[did]

            if prev_frame is not None and anim_t < 1.0:
                pgx, pgy, _ = prev_frame[did]
                gx = pgx + (gx - pgx) * anim_t
                gy = pgy + (gy - pgy) * anim_t

            sx, sy = self._to_screen(gx, gy)
            color = _DRONE_COLORS[status]

            glow = self._lerp_color(color, _BG, 0.5)
            pygame.draw.circle(
                surface, glow, (sx, sy), _DRONE_RADIUS + 3,
            )

            pygame.draw.circle(
                surface, color, (sx, sy), _DRONE_RADIUS,
            )

            pygame.draw.circle(
                surface, (255, 255, 255), (sx, sy),
                _DRONE_RADIUS, 1,
            )

            id_txt = font.render(str(did), True, (255, 255, 255))
            surface.blit(
                id_txt,
                (sx - id_txt.get_width() // 2,
                 sy - id_txt.get_height() // 2),
            )

    def _draw_capacity_overlay(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        frame_idx: int,
    ) -> None:
        zone_map = self._zone_maps[frame_idx]
        arrived = self._arrived_maps[frame_idx]
        transit_set = self._transit_maps[frame_idx]

        counts: dict[str, int] = {}
        for did in range(1, self.nb_drones + 1):
            if did in arrived or did in transit_set:
                continue
            z = zone_map[did]
            counts[z] = counts.get(z, 0) + 1

        for name, zone in self.graph.zones.items():
            if zone.role in (HubRole.START, HubRole.END):
                continue
            if zone.zone_type == ZoneType.BLOCKED:
                continue

            cx, cy = self._to_screen(*self.node_pos[name])
            n = counts.get(name, 0)
            cap = zone.max_drones
            label = f"{n}/{cap}"

            if n >= cap:
                color = (231, 76, 60)
            elif n >= cap - 1 and cap > 1:
                color = (241, 196, 15)
            else:
                color = (46, 204, 113)

            txt = font.render(label, True, color)
            surface.blit(
                txt,
                (cx - txt.get_width() // 2,
                 cy + _ZONE_RADIUS + 4),
            )

        conn_usage = self._conn_usage_maps[frame_idx]
        for conn in self.graph.connections:
            za = self.graph.zones[conn.zone_a]
            zb = self.graph.zones[conn.zone_b]
            if not za.is_accessible or not zb.is_accessible:
                continue

            ax, ay = self._to_screen(*self.node_pos[conn.zone_a])
            bx, by = self._to_screen(*self.node_pos[conn.zone_b])
            mx, my = (ax + bx) // 2, (ay + by) // 2

            pair = (
                min(conn.zone_a, conn.zone_b),
                max(conn.zone_a, conn.zone_b),
            )
            used = conn_usage.get(pair, 0)
            cap = conn.max_link_capacity

            if used > 0:
                label = f"{used}/{cap}"
                if used >= cap:
                    color = (231, 76, 60)
                else:
                    color = (46, 204, 113)
            else:
                if cap <= 2:
                    label = f"0/{cap}"
                    color = _TEXT_DIM
                else:
                    continue

            txt = font.render(label, True, color)
            surface.blit(
                txt,
                (mx - txt.get_width() // 2,
                 my - txt.get_height() // 2 - 10),
            )

    def _draw_hud(
        self,
        surface: pygame.Surface,
        width: int,
        frame_idx: int,
        total: int,
        paused: bool,
        speed: int,
        font_hud: pygame.font.Font,
        font_small: pygame.font.Font,
        frame: dict[int, tuple[float, float, str]],
    ) -> None:
        bar = pygame.Surface((width, _HUD_HEIGHT), pygame.SRCALPHA)
        bar.fill((*_PANEL_BG, 220))
        surface.blit(bar, (0, 0))

        n_arrived = sum(
            1 for did in range(1, self.nb_drones + 1)
            if frame[did][2] == "arrived"
        )

        turn_txt = font_hud.render(
            f"Turn {frame_idx} / {total}", True, _TEXT_COLOR,
        )
        surface.blit(turn_txt, (15, 12))

        arr_txt = font_hud.render(
            f"Arrived: {n_arrived} / {self.nb_drones}",
            True, _DRONE_COLORS["arrived"],
        )
        surface.blit(arr_txt, (220, 12))

        status = "PAUSED" if paused else "PLAYING"
        st_color = (231, 76, 60) if paused else (46, 204, 113)
        st_txt = font_hud.render(status, True, st_color)
        surface.blit(st_txt, (450, 12))

        spd_txt = font_hud.render(
            f"Speed: {speed}ms", True, _TEXT_DIM,
        )
        surface.blit(spd_txt, (570, 12))

        legend_x = width - 15
        for label, color in _DRONE_COLORS.items():
            txt = font_small.render(label.capitalize(), True, color)
            legend_x -= txt.get_width() + 8
            pygame.draw.circle(
                surface, color, (legend_x - 6, 25), 5,
            )
            surface.blit(txt, (legend_x, 16))
            legend_x -= 14

        ctrl_txt = font_small.render(
            "Space: pause | \u2190/\u2192: step | +/-: speed"
            " | Scroll: zoom | Drag: pan | F: fit",
            True, _TEXT_DIM,
        )
        surface.blit(
            ctrl_txt,
            ((width - ctrl_txt.get_width()) // 2,
             surface.get_height() - 22),
        )

    def run(self) -> None:
        pygame.init()

        info = pygame.display.Info()
        self._width = min(info.current_w - 100, 1200)
        self._height = min(info.current_h - 100, 800)

        screen = pygame.display.set_mode(
            (self._width, self._height),
        )
        pygame.display.set_caption("Fly-In Drone Simulation")
        clock = pygame.time.Clock()

        font_name = pygame.font.SysFont("monospace", 13)
        font_info = pygame.font.SysFont("monospace", 14, bold=True)
        font_hud = pygame.font.SysFont("monospace", 16, bold=True)
        font_small = pygame.font.SysFont("monospace", 12)
        font_drone = pygame.font.SysFont("monospace", 11, bold=True)

        self._fit_to_screen()

        total = len(self.frames) - 1
        frame_idx = 0
        paused = False
        speed = 400
        timer = 0.0
        anim_t = 1.0

        dragging = False
        drag_start: tuple[int, int] = (0, 0)

        running = True
        while running:
            dt = clock.tick(_FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_RIGHT:
                        frame_idx = min(frame_idx + 1, total)
                        anim_t = 1.0
                    elif event.key == pygame.K_LEFT:
                        frame_idx = max(frame_idx - 1, 0)
                        anim_t = 1.0
                    elif event.key in (
                        pygame.K_PLUS, pygame.K_EQUALS,
                        pygame.K_KP_PLUS,
                    ):
                        speed = max(50, speed - 50)
                    elif event.key in (
                        pygame.K_MINUS, pygame.K_KP_MINUS,
                    ):
                        speed = min(2000, speed + 50)
                    elif event.key == pygame.K_f:
                        self._fit_to_screen()
                    elif event.key == pygame.K_ESCAPE:
                        running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        dragging = True
                        drag_start = event.pos

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        dragging = False

                elif event.type == pygame.MOUSEMOTION:
                    if dragging:
                        dx = event.pos[0] - drag_start[0]
                        dy = event.pos[1] - drag_start[1]
                        self._cam_x -= dx / self._zoom
                        self._cam_y += dy / self._zoom
                        drag_start = event.pos

                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if event.y > 0:
                        self._zoom_at(mx, my, 1.15)
                    elif event.y < 0:
                        self._zoom_at(mx, my, 1 / 1.15)

            if not paused:
                timer += dt
                anim_t = min(timer / speed, 1.0)
                if timer >= speed:
                    timer = 0.0
                    anim_t = 0.0
                    frame_idx = (frame_idx + 1) % (total + 1)

            screen.fill(_BG)

            self._draw_edges(screen)
            self._draw_zones(screen, font_name, font_info)

            prev = (
                self.frames[frame_idx - 1]
                if frame_idx > 0
                else None
            )
            self._draw_drones(
                screen,
                self.frames[frame_idx],
                font_drone, anim_t, prev,
            )

            if self.capacity_info:
                self._draw_capacity_overlay(
                    screen, font_small, frame_idx,
                )

            self._draw_hud(
                screen, self._width, frame_idx, total,
                paused, speed, font_hud, font_small,
                self.frames[frame_idx],
            )

            pygame.display.flip()

        pygame.quit()
