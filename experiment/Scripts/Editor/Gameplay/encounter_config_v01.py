"""Pure encounter authoring data for the independent V10 gameplay map.

Coordinates are WORLD METRES and represent the foot of an actor, not capsule centres.
The caller must perform actual UE floor/capsule/navigation checks before admission.
This module deliberately imports no Unreal package and changes no files or assets.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LAYOUT_PATH = PROJECT_ROOT / "Docs/LevelDesign/Blockout_v05/LayoutSpec.json"


def _yaw_toward(origin, target):
    return math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0]))


def _point(stage_id, suffix, ground, facing_target):
    return {
        "id": f"{stage_id}_{suffix}",
        "ground_m": [float(value) for value in ground],
        "yaw": _yaw_toward(ground, facing_target),
    }


def _wave(stage_id, index, class_key, count, points, max_alive=4, intermission=2.5):
    return {
        "id": f"{stage_id}_W{index:02d}",
        "entry_class_key": class_key,
        "count": count,
        "point_ids": [point["id"] for point in points],
        # The encounter director must defer when all candidate points are occupied;
        # MaxAlive is a concurrency ceiling, not an instruction to ignore collisions.
        "spawn_interval": 0.65 if count > 1 else 0.0,
        "intermission": intermission,
        "max_alive": max_alive,
    }


def _stage(stage_id, label, entry, trigger_center, trigger_extent, points, wave_specs, entry_yaw=90.0):
    return {
        "id": stage_id,
        "label": label,
        "required": "",  # Filled from the final strict stage order below.
        "trigger_center_m": list(trigger_center),
        "trigger_extent_m": list(trigger_extent),
        "entry_ground_m": list(entry),
        "entry_yaw": entry_yaw,
        "spawn_points": points,
        "waves": [
            _wave(stage_id, index, class_key, count, points, cap, pause)
            for index, (class_key, count, cap, pause) in enumerate(wave_specs, start=1)
        ],
    }


def make_config(layout_path=None):
    """Return a fresh 16-stage/109-enemy configuration derived from saved V10 geometry."""
    path = Path(layout_path) if layout_path is not None else DEFAULT_LAYOUT_PATH
    layout = json.loads(path.read_text(encoding="utf-8-sig"))
    if layout.get("units") != "metres":
        raise ValueError("LayoutSpec must use metres; refusing an implicit unit conversion")

    stages = []

    def add_plain(stage_id, label, entry, trigger, extent, positions, waves, yaw=90.0):
        points = [_point(stage_id, f"P{index:02d}", position, entry)
                  for index, position in enumerate(positions, start=1)]
        stage = _stage(stage_id, label, entry, trigger, extent, points, waves, yaw)
        stages.append(stage)
        return stage

    add_plain("Aoutside", "山门外 · 初次交锋", (0, -21, 0), (0, -19, 0), (14, 8, 3),
              [(-8, -11, 0), (8, -11, 0)], [("sword", 2, 4, 2.5)])
    add_plain("Ainside", "山门内 · 清理守卫", (0, 6, 0), (0, 12, 0), (18, 10, 3),
              [(-8, 10, 0), (8, 10, 0), (-12, 15, 0), (12, 15, 0), (-6, 21, 0), (6, 21, 0)],
              [("sword", 6, 4, 2.5)])

    stations = {station["id"]: station for station in layout["ranged_encounters"]["stations"]}

    def add_ranged(station_id):
        station = stations[station_id]
        entry = station["approach_foot"]
        points = [_point(station_id, f"P{index:02d}", enemy["foot"], entry)
                  for index, enemy in enumerate(station["enemies"], start=1)]
        if len(points) != 2:
            raise ValueError(f"{station_id} requires exactly two saved sentry feet")
        stage = _stage(station_id, f"{station_id} · 岩台持符弟子", entry, station["route_rest"],
                       (5, 4, 3), points, [("talisman", 2, 2, 2.5)])
        stage["stationary_ranged"] = True
        stage["preserve_saved_spawn_ground"] = True
        stage["design_note"] = "Keep both sentries on the saved raised rock feet; alternate telegraphed shots."
        stages.append(stage)

    add_ranged("R01")
    add_plain("Bcourt", "演武场 · 六波守阵", (0, 126, 28), (0, 126, 28), (14, 9, 3),
              [(-8, 140, 28), (8, 140, 28), (0, 148, 28), (-8, 154, 28), (8, 154, 28), (0, 157, 28)],
              [("sword", 6, 4, 2.5)] * 6)
    add_plain("Bexit", "演武场出口 · 断后守卫", (0, 155, 28), (0, 157.5, 28), (14, 6, 3),
              [(-8, 159, 28), (8, 159, 28), (-12, 153, 28), (12, 153, 28), (-5, 161, 28), (5, 161, 28)],
              [("sword", 6, 4, 2.5)])
    add_ranged("R02")
    add_ranged("R03")

    # One common courtyard trigger supports consecutive phases without requiring
    # the player to walk back to the entrance after every completed encounter.
    # x=+/-12 avoids the central furnace (0,310), r=4.25m, and its axial approach.
    c_positions = [(-12, 290, 72), (12, 290, 72), (-12, 298, 72), (12, 298, 72),
                   (-12, 306, 72), (12, 306, 72), (-18, 294, 72), (18, 294, 72)]
    c_phases = [
        ("Cestablish", "炼丹院 · 建立战线", [("sword", 4, 4, 2.5), ("sword", 4, 4, 2.5)]),
        ("Cinterrupt", "炼丹院 · 打断施法", [("talisman", 5, 4, 2.5), ("sword", 5, 4, 2.5)]),
        ("Csiege", "炼丹院 · 阵地围攻", [("sword", 6, 4, 2.5), ("talisman", 6, 4, 2.5)]),
        ("Cunseal", "炼丹院 · 解封守阵", [("sword", 7, 4, 2.5), ("talisman", 7, 4, 3.0)]),
    ]
    for stage_id, label, waves in c_phases:
        stage = add_plain(stage_id, label, (0, 279, 72), (0, 300, 72), (29, 28, 3), c_positions, waves)
        stage["design_note"] = "Shared courtyard trigger; advance when predecessor clears and player remains inside."

    arenas = {arena["id"]: arena for arena in layout["grandmaster_arenas"]}
    for master_id in ("GM01", "GM02", "GM03", "GM04"):
        arena = arenas[master_id]
        center = arena["center"]
        entry = arena.get("entry_ground")
        if entry is None:
            # The first arena is connected by a level bridge, not an entry stair.
            links = layout["flat_links"]
            link = links if isinstance(links, dict) else next(item for item in links if item["name"] == arena["entry_link"])
            start, end = link["a"], link["b"]
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            entry = [center[0] - 8 * (end[0] - start[0]) / length,
                     center[1] - 8 * (end[1] - start[1]) / length, center[2]]
        facing = _yaw_toward(entry, arena["enemy_spawn"])
        master_point = _point(master_id, "Master", arena["enemy_spawn"], entry)
        points = [master_point]
        waves = []
        if master_id in ("GM02", "GM03"):
            prep_points = [_point(master_id, f"Guard{index:02d}", (center[0] + offset, center[1] - 1, center[2]), entry)
                           for index, offset in enumerate((-6, 6), start=1)]
            points = prep_points + points
            waves.append(_wave(master_id, 1, "sword" if master_id == "GM02" else "talisman",
                               2, prep_points, 4, 3.0))
        waves.append(_wave(master_id, len(waves) + 1, master_id, 1, [master_point], 1, 3.0))
        stage = _stage(master_id, f"御风桥 · {arena['display_name']}", entry, center, (10, 9, 3), points, [], facing)
        stage["waves"] = waves
        stage["master_id"] = master_id
        stage["seal_id"] = arena["drop"]
        stage["first_clear_health_reward"] = 25.0
        stages.append(stage)

    boss = layout["boss_arena"]
    add_plain("Boss", "山顶 · 最终决战", (-208, 590, 132), (-208, 590, 132), (20, 12, 3),
              [boss["boss_spawn"]], [("boss", 1, 1, 0.0)])
    stages[-1]["required_seal_ids"] = [arenas[master_id]["drop"] for master_id in ("GM01", "GM02", "GM03", "GM04")]

    previous_id = ""
    for stage in stages:
        stage["required"] = previous_id
        stage["enemy_budget"] = sum(wave["count"] for wave in stage["waves"])
        previous_id = stage["id"]
    total = sum(stage["enemy_budget"] for stage in stages)
    if len(stages) != 16 or total != 109:
        raise ValueError(f"Encounter budget mismatch: {len(stages)} stages, {total} enemies")

    return {
        "schema_version": 1,
        "source_map": layout["map"],
        "map": "/Game/ReversedScale/Maps/L_NilinGameplayV01",
        "units": "metres",
        "total_enemy_budget": total,
        "baseline_enemy_budget": 103,
        "new_rock_sentry_budget": 6,
        "stage_count": len(stages),
        "safe_rest_node_indices": [2, 4],
        "validation_required": "UE floor traces, spawn capsule sweeps, reachable NavMesh and ranged firing lanes",
        "stages": stages,
    }
