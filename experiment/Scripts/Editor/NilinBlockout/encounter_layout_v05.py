"""V10 encounter-space layout, in metres, without importing Unreal.

The three existing courts are copied from the delivered V09 specification.
Only the upper ascent and summit are replaced.  Transition strips deliberately
extend from each terrace centre to its support plane: a stair cannot terminate
at a rectangle's diagonal corner with only half its width supported.
"""
from __future__ import annotations

import copy
import datetime
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "Docs/LevelDesign/Blockout_v04/LayoutSpec.json"
OUT = ROOT / "Docs/LevelDesign/Blockout_v05"
OLD_UPPER = {"C_to_Ridge", "Ridge_to_Node06", "Node06_to_Upper", "Upper_to_Summit"}
OLD_RESTS = {"RidgeLanding", "Node06_BridgeLanding", "Node06_Overlook", "UpperLanding"}
BRIDGE_WIDTH = 8.0
SUMMIT_CENTER = [-208.0, 620.0, 132.0]
SUMMIT_RADIUS = 46.0


def unit_xy(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise ValueError("A connection must have a nonzero horizontal run")
    return [dx / length, dy / length]


def rectangle_points(center, size):
    x, y = center[:2]
    w, h = size
    return [[x - w / 2, y - h / 2], [x + w / 2, y - h / 2],
            [x + w / 2, y + h / 2], [x - w / 2, y + h / 2]]


def strip_points(a, b, width, end_overlap=0.0):
    """Counterclockwise plan polygon, suitable for rail clipping and flooring."""
    u = unit_xy(a, b)
    n = [-u[1], u[0]]
    first = [a[i] - u[i] * end_overlap for i in range(2)]
    last = [b[i] + u[i] * end_overlap for i in range(2)]
    return [[p[i] + n[i] * side for i in range(2)]
            for p, side in ((first, width / 2), (first, -width / 2),
                            (last, -width / 2), (last, width / 2))]


def flat_record(name, a, b, width=BRIDGE_WIDTH, associated_rest=None):
    """A flush strip; endpoints describe its centreline, not mesh bounds."""
    if abs(a[2] - b[2]) > 1e-8:
        raise ValueError("Flat connector endpoints must share their height")
    u = unit_xy(a, b)
    length = math.dist(a[:2], b[:2])
    record = {"name": name, "a": list(a), "b": list(b), "start": list(a),
              "center": [(a[i] + b[i]) / 2 for i in range(3)],
              "size": [length + 0.5, width], "width": width,
              "rotation_yaw": math.degrees(math.atan2(u[1], u[0])),
              "points": strip_points(a, b, width, end_overlap=0.25),
              "inward": u, "kind": "transition", "height": a[2],
              "endpoint_overlap": 0.25}
    if associated_rest:
        record["associated_rest"] = associated_rest
    return record


def landing_portal(landing, toward, width=BRIDGE_WIDTH, suffix="Exit"):
    """Return an outside support-plane point and its full-width flat bridgehead.

    The last 25 cm overlap the first/last tread, while the long inner end
    overlaps the arena floor.  Terrace vertices do not create vertical lips.
    """
    center = landing["center"]
    u = unit_xy(center, toward)
    hx, hy = [s / 2 for s in landing["size"]]
    support = abs(u[0]) * hx + abs(u[1]) * hy + 0.35
    endpoint = [center[i] + u[i] * support for i in range(2)] + [center[2]]
    a, b = (center, endpoint) if suffix == "Exit" else (endpoint, center)
    connector = flat_record(landing["name"] + "_" + suffix + "Bridgehead",
                            a, b, width, landing["name"])
    return endpoint, connector


def stair_samples(a, b, width, name):
    """Match the existing whitebox stairs: <=16 cm rise, rests every20steps."""
    dx, dy, dz = [b[i] - a[i] for i in range(3)]
    run = math.hypot(dx, dy)
    if dz <= 0:
        raise ValueError("Stairs must ascend: " + name)
    count = math.ceil(dz / 0.16)
    landings = (count - 1) // 20
    rise = dz / count
    tread = (run - landings * 1.25) / count
    if tread < 0.30:
        raise ValueError("Stair treads are too short: " + name)
    points, progress = [], 0.0
    for index in range(count):
        z = a[2] + (index + 1) * rise
        middle = progress + tread / 2
        points.append([a[0] + dx / run * middle, a[1] + dy / run * middle, z])
        progress += tread
        if (index + 1) % 20 == 0 and index < count - 1:
            middle = progress + 0.625
            points.append([a[0] + dx / run * middle, a[1] + dy / run * middle, z])
            progress += 1.25
    return {"name": name, "a": list(a), "b": list(b), "width": width,
            "riser": rise, "tread": tread, "steps": count,
            "landings": landings}, points


def line_samples(a, b, spacing=1.5):
    count = max(1, math.ceil(math.dist(a, b) / spacing))
    return [[a[i] + (b[i] - a[i]) * j / count for i in range(3)]
            for j in range(count + 1)]


def make_layout():
    with SOURCE.open(encoding="utf-8") as handle:
        previous = json.load(handle)
    result = copy.deepcopy(previous)
    result.update(map="/Game/ReversedScale/Maps/L_NilinBlockoutV10", version="v05",
                  optimized_at=datetime.datetime.now().isoformat())

    identities = [("GM01", "Sword", [-46, 332, 72], "SwordSeal", "问剑宗师"),
                  ("GM02", "Talisman", [-82, 397, 90], "TalismanSeal", "镇符宗师"),
                  ("GM03", "Alchemy", [-130, 466, 106], "AlchemySeal", "丹火宗师"),
                  ("GM04", "Wind", [-180, 535, 122], "WindSeal", "御风宗师")]
    arenas = [{"id": identity, "name": "Yufeng_" + title + "Arena",
               "display_name": chinese, "center": list(center), "size": [24, 22],
               "shape": "rectangle", "clear_size": [18, 16],
               "clear_center": list(center), "role": "grandmaster",
               "stage": "YufengBridge", "drop": seal, "enemy_count": 1,
               "enemy_spawn": [center[0], center[1] + 4, center[2]],
               "clearance_rule": "No props or columns inside the18x16m core",
               "progression": "One duel at a time; clear before next encounter",
               "recovery_after_duel": True}
              for identity, title, center, seal, chinese in identities]
    result["grandmaster_arenas"] = arenas
    result["rests"] = [r for r in result["rests"] if r["name"] not in OLD_RESTS]
    result["rests"].extend(copy.deepcopy(arenas))

    for platform in result["platforms"]:
        if platform["name"] == "D_SummitFloor":
            platform.update(center=list(SUMMIT_CENTER), radius=SUMMIT_RADIUS)
    result["boss"] = [SUMMIT_CENTER[0], SUMMIT_CENTER[1] + 6, SUMMIT_CENTER[2]]
    result["boss_arena"] = {
        "name": "D_SummitFloor", "shape": "circle", "center": list(SUMMIT_CENTER),
        "radius": SUMMIT_RADIUS, "diameter": 2 * SUMMIT_RADIUS,
        "clear_center": list(SUMMIT_CENTER), "clear_radius": 30,
        "boss_spawn": list(result["boss"]), "old_radius": 30,
        "area_multiplier": (SUMMIT_RADIUS / 30) ** 2,
        "monument_center": [SUMMIT_CENTER[0], SUMMIT_CENTER[1] + 38, SUMMIT_CENTER[2]],
        "monument_width": 62, "monument_height": 35,
        "front_facing_yaw": -90,
        "clearance_rule": "Keep the central60m combat circle unobstructed; background lies north ofy+30"}

    lower = [s for s in previous["stairs"] if s["name"] not in OLD_UPPER]
    flights, route = [], []
    for old in lower:
        stair, samples = stair_samples(old["a"], old["b"], old["width"], old["name"])
        stair["route_samples"] = samples
        flights.append(stair)
        route.extend(samples)

    c_exit = next(r for r in result["rests"] if r["name"] == "C_EastExit")
    approach = flat_record("C_to_Master1_Flat", c_exit["center"], arenas[0]["center"])
    result["flat_links"] = [approach]
    result["bridgeheads"] = [copy.deepcopy(head) for head in previous.get("bridgeheads", [])
                             if head.get("associated_rest") not in OLD_RESTS
                             and head["name"] != "SummitEntryBridgehead"]
    route.extend(line_samples(approach["a"], approach["b"]))
    segments = [dict(kind="flat", name=approach["name"], a=approach["a"],
                     b=approach["b"], width=BRIDGE_WIDTH,
                     source_arena=None, target_arena=arenas[0]["id"])]
    arenas[0]["entry_stair"] = None
    arenas[0]["entry_link"] = approach["name"]

    for index, first in enumerate(arenas):
        following = arenas[index + 1] if index + 1 < len(arenas) else None
        target = following["center"] if following else SUMMIT_CENTER
        a, leave = landing_portal(first, target, suffix="Exit")
        result["bridgeheads"].append(leave)
        if following:
            b, enter = landing_portal(following, first["center"], suffix="Entry")
            name = "Yufeng_Master%d_to_Master%d" % (index + 1, index + 2)
            following["entry_stair"] = name
        else:
            u = unit_xy(first["center"], SUMMIT_CENTER)
            b = [SUMMIT_CENTER[i] - u[i] * SUMMIT_RADIUS for i in range(2)] + [132.0]
            inner = [b[i] + u[i] * 4 for i in range(2)] + [132.0]
            enter = flat_record("SummitEntryBridgehead", b, inner,
                                associated_rest="D_SummitFloor")
            name = "Yufeng_Master4_to_Summit"
        result["bridgeheads"].append(enter)
        stair, samples = stair_samples(a, b, BRIDGE_WIDTH, name)
        stair.update(stage="YufengBridge", combat=False,
                     source_arena=first["id"],
                     target_arena=following["id"] if following else "BOSS")
        stair["route_samples"] = samples
        flights.append(stair)
        first["next_stair"] = name
        first["exit_ground"] = list(a)
        if following:
            following["entry_ground"] = list(b)
        route.extend(line_samples(first["center"], a))
        route.extend(samples)
        route.extend(line_samples(b, target))
        segments.append(dict(stair, kind="stairs"))

    result["stairs"], result["route"] = flights, route
    result["upper_route_segments"] = segments
    # Refresh the rest copies now that route entry/exit names have been resolved.
    by_name = {arena["name"]: arena for arena in arenas}
    result["rests"] = [copy.deepcopy(by_name.get(r["name"], r)) for r in result["rests"]]
    result["nodes"][5].update(ground=list(arenas[2]["center"]), yaw=125)
    result["nodes"][6].update(ground=[-208, 590, 132], yaw=90)
    result["nodes"][7].update(ground=[-208, 658, 132], yaw=-90)
    result["route_approaches"] = {"6": [arenas[2]["center"][0],
                                               arenas[2]["center"][1] - 6, 106]}

    for footprint in result["footprints"]:
        if footprint["name"] == "SealWall":
            footprint.update(center=[-208, 658, 132], size=[62, 8], height=35)
    notes = result["gameplay_notes"]
    notes.update(transition_only_nodes=[2, 4], bridge_duel_node=6,
                 triangle_eye=[-214, 619, 132],
                 victory_route=[[-224, 644, 132], [-224, 658, 132], [-208, 658, 132]],
                 markers="Whitebox encounter reservations; AI and item drops require gameplay integration")
    objective = [-208, 620, 152]
    for camera in result["cameras"]:
        name = camera["name"]
        if name == "CAM_00_Overview":
            camera.update(position=[-80, -590, 510], target=[-95, 260, 74], fov=60)
        elif name == "CAM_04_Ridge":
            camera.update(position=[-102, 440, 115], target=objective, fov=72)
        elif name == "CAM_05_Boss":
            camera.update(position=[-208, 584, 133.7], target=[-208, 641, 146], fov=80)
        elif name == "CAM_06_Top":
            camera.update(position=[-95, 310, 1180], target=[-95, 310, 0], fov=60)
        elif name in {"CAM_07_LowObjective", "CAM_08_AlchemyObjective"}:
            camera["target"] = list(objective)
        elif name == "CAM_09_AlternateOverview":
            camera.update(position=[-280, -550, 490], target=[-95, 260, 74], fov=60)
    result["cameras"].extend([
        {"name": "CAM_15_FourGrandmasters", "position": [-345, 350, 235],
         "target": [-125, 460, 104], "fov": 65},
        {"name": "CAM_16_SummitScale", "position": [-281, 543, 189],
         "target": [-208, 631, 145], "fov": 68}])

    old_centers = [[-34, 310, 72], [-69, 347.5, 88], [-106.5, 407.5, 104],
                   [-151.5, 459.5, 122], [-174, 512.5, 132]]
    new_centers = [c_exit["center"]] + [a["center"] for a in arenas] + [SUMMIT_CENTER]
    old_length = sum(math.dist(a[:2], b[:2]) for a, b in zip(old_centers, old_centers[1:]))
    new_length = sum(math.dist(a[:2], b[:2]) for a, b in zip(new_centers, new_centers[1:]))
    result["upper_ascent_change"] = {
        "original_summit": [-174, 512.5, 132], "summit": list(SUMMIT_CENTER),
        "original_centerline_length_m": old_length, "centerline_length_m": new_length,
        "length_multiplier": new_length / old_length, "combat_courts_resized": False,
        "bridge_width_m": BRIDGE_WIDTH, "grandmaster_arenas": 4,
        "terrace_size_m": [24, 22], "clear_core_m": [18, 16],
        "min_interarena_unpressured_link_m": min(math.dist(s["a"][:2], s["b"][:2])
                                                    for s in flights[-4:-1]),
        "boss_floor_diameter_m": 92, "boss_clear_diameter_m": 60,
        "max_riser_m": max(s["riser"] for s in flights),
        "min_upper_tread_m": min(s["tread"] for s in flights[-4:]),
        "junction_refinement": "8m flush entry/exit strips overlap stair ends; all four masters stand on the bridge"}
    result["encounter_design"] = {
        "bridge_sequence": [a["id"] for a in arenas],
        "master_count": 4, "lower_ascent_ranged_encounters": "Added by the scene encounter module",
        "rest_links": "No ranged crossfire between master duels",
        "seal_rule": "Collect4distinct master seals before the boss barrier opens",
        "persistent_rewards_on_retry": True,
        "boss_readability": "60m open combat circle;35m monumental seal architecture behind the boss"}
    return result


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "LayoutSpec_working.json").open("w", encoding="utf-8") as handle:
        json.dump(make_layout(), handle, ensure_ascii=False, indent=2)
