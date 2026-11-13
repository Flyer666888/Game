"""Pure-Python metre-space audit for the V06 blockout; does not import Unreal.

This is a conservative draft model, not a measurement of an existing UE level.
X is right, +Y is forward/uphill, Z is elevation. Building facades face -Y.
Default mode reads the current builder LayoutSpec.json without executing UE.
--mode both compares the earlier draft and a shifted counterfactual layout;
--include-structures adds approximate pavilion/furnace.
The corrected variant keeps all elevations and D fixed, moves B 25 m west and
C 45 m west, turns the first/BC stair runs westward, and delays +132 m until
the bridge reaches D's near rim. Import the helpers or replace make_layout()
with actual exported actor bounds for a subsequent audit.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

Vec3 = tuple[float, float, float]
EPS = 1e-8
EYE_HEIGHTS = (1.1, 1.7)
EYE_OFFSETS = (-0.032, 0.032)


def add(a: Vec3, b: Vec3) -> Vec3:
    return tuple(a[i] + b[i] for i in range(3))


def sub(a: Vec3, b: Vec3) -> Vec3:
    return tuple(a[i] - b[i] for i in range(3))


def dot(a: Vec3, b: Vec3) -> float:
    return sum(a[i] * b[i] for i in range(3))


def lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def segment_halfspaces(a: Vec3, b: Vec3,
                       planes: Iterable[tuple[Vec3, float]]):
    """Return [enter, exit] for n dot p <= limit, or None. t is in [0,1]."""
    lo, hi = 0.0, 1.0
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    ax, ay, az = a
    for n, limit in planes:
        value = n[0] * ax + n[1] * ay + n[2] * az - limit
        rate = n[0] * dx + n[1] * dy + n[2] * dz
        if abs(rate) < EPS:
            if value > EPS:
                return None
            continue
        t = -value / rate
        if rate < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi + EPS:
            return None
    return (max(0.0, lo), min(1.0, hi)) if hi >= 0 and lo <= 1 else None


@dataclass(frozen=True)
class Box:
    name: str
    minimum: Vec3
    maximum: Vec3

    def intersect(self, a: Vec3, b: Vec3):
        lo, hi = 0.0, 1.0
        for i in range(3):
            delta = b[i] - a[i]
            if abs(delta) < EPS:
                if a[i] < self.minimum[i] or a[i] > self.maximum[i]:
                    return None
                continue
            p, q = (self.minimum[i] - a[i]) / delta, (self.maximum[i] - a[i]) / delta
            if p > q:
                p, q = q, p
            lo, hi = max(lo, p), min(hi, q)
            if lo > hi + EPS:
                return None
        return (lo, hi)


@dataclass(frozen=True)
class Cylinder:
    name: str
    x: float
    y: float
    radius: float
    z_min: float
    z_max: float

    def intersect(self, a: Vec3, b: Vec3):
        interval = segment_halfspaces(a, b, (((0, 0, -1), -self.z_min),
                                             ((0, 0, 1), self.z_max)))
        if interval is None:
            return None
        dx, dy = b[0] - a[0], b[1] - a[1]
        ox, oy = a[0] - self.x, a[1] - self.y
        qa = dx * dx + dy * dy
        qc = ox * ox + oy * oy - self.radius ** 2
        if qa < EPS:
            return interval if qc <= EPS else None
        qb = 2 * (ox * dx + oy * dy)
        disc = qb * qb - 4 * qa * qc
        if disc < -EPS:
            return None
        root = math.sqrt(max(0, disc))
        lo = max(interval[0], (-qb - root) / (2 * qa))
        hi = min(interval[1], (-qb + root) / (2 * qa))
        return (lo, hi) if lo <= hi + EPS else None


@dataclass(frozen=True)
class Ramp:
    """Oriented sloping deck; thickness=None makes a solid terrain wedge.

    top_allowance conservatively includes a 0.16 m stair-riser envelope. This
    model does not certify actual step collision, tread geometry or headroom.
    """
    name: str
    start: Vec3
    end: Vec3
    width: float = 4.0
    thickness: float | None = None
    top_allowance: float = 0.16

    @cached_property
    def halfspaces(self):
        dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        length = math.hypot(dx, dy)
        if length < EPS:
            raise ValueError("ramp needs nonzero horizontal run")
        u = (dx / length, dy / length, 0.0)
        v = (-u[1], u[0], 0.0)
        slope = (self.end[2] - self.start[2]) / length
        top_n = (-slope * u[0], -slope * u[1], 1.0)
        top_c = self.start[2] - slope * dot(u, self.start)
        planes = [(u, dot(u, self.start) + length),
                  (tuple(-x for x in u), -dot(u, self.start)),
                  (v, dot(v, self.start) + self.width / 2),
                  (tuple(-x for x in v), -dot(v, self.start) + self.width / 2),
                  (top_n, top_c + self.top_allowance)]
        if self.thickness is None:
            planes.append(((0, 0, -1), 40.0))
        else:
            planes.append((tuple(-x for x in top_n),
                           -top_c + self.thickness))
        return tuple(planes)

    def intersect(self, a: Vec3, b: Vec3):
        return segment_halfspaces(a, b, self.halfspaces)


def nearest_hit(a: Vec3, b: Vec3, obstacles: Sequence):
    hits = []
    for shape in obstacles:
        interval = shape.intersect(a, b)
        if interval and interval[1] > EPS and interval[0] < 1.0 - EPS:
            hits.append((interval[0], shape.name))
    return min(hits) if hits else None


def sample_polyline(points: Sequence[Vec3], spacing: float = 1.0):
    """Include all corners and endpoints, with 3-D sample gaps <= spacing."""
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    if not points:
        return
    yield points[0]
    for a, b in zip(points, points[1:]):
        steps = max(1, math.ceil(math.dist(a, b) / spacing))
        for i in range(1, steps + 1):
            yield lerp(a, b, i / steps)


def grid(x0, x1, y0, y1, z, spacing=1.0):
    for xi in range(math.floor((x1 - x0) / spacing) + 1):
        for yi in range(math.floor((y1 - y0) / spacing) + 1):
            yield (x0 + xi * spacing, y0 + yi * spacing, z)


def point_in_polygon(x, y, polygon):
    """Even/odd test including boundary, useful for permitted floor masks."""
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (x-a[0])*(b[1]-a[1]) - (y-a[1])*(b[0]-a[0])
        if (abs(cross) < EPS and min(a[0],b[0])-EPS <= x <= max(a[0],b[0])+EPS
                and min(a[1],b[1])-EPS <= y <= max(a[1],b[1])+EPS):
            return True
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (b[0]-a[0])*(y-a[1])/(b[1]-a[1]):
                inside = not inside
    return inside


def orthogonal_polygon_rectangles(polygon):
    """Exact union of rectangles for a non-self-intersecting rectilinear floor."""
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(a[0]-b[0]) > EPS and abs(a[1]-b[1]) > EPS:
            raise ValueError("Only axis-aligned polygon edges are supported")
    xs, ys = sorted({p[0] for p in polygon}), sorted({p[1] for p in polygon})
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            if point_in_polygon((x0+x1)/2, (y0+y1)/2, polygon):
                yield x0, x1, y0, y1


def target_points():
    # True near rim, not the hidden centre of the top face of a 30 m cylinder.
    rim = [(220 + x, 580 - math.sqrt(30 ** 2 - x ** 2), 132.25)
           for x in (-24.0, -18.0, -12.0, -6.0, 0.0, 6.0, 12.0, 18.0, 24.0)]
    return rim, (220.0, 590.0, 158.0)


def make_layout(corrected=False, include_structures=False):
    bx, cx = (-25.0, -45.0) if corrected else (0.0, 0.0)
    solids = [
        Box("A_forecourt", (-30, -35, -40), (30, -5, -0.1)),
        Box("A_rear_terrain", (-30, 45, -40), (30, 85, 11.9)),
        Box("B_terrain", (bx - 30, 118, -40), (bx + 30, 162, 27.9)),
        Box("C_terrain", (cx - 32, 270, -40), (cx + 32, 330, 71.9)),
        Cylinder("D_summit_terrain", 220, 580, 30, -40, 131.9),
    ]
    if corrected:
        route = [(0, -20, 0), (0, -5, 0), (-24, 19, 12), (0, 65, 12),
                 (-15, 86, 12), (bx, 118, 28), (bx, 140, 28),
                 (bx, 162, 28), (-39.54545, 194, 44), (-85, 230, 72),
                 (cx, 279, 72), (cx + 32, 300, 72), (130, 440, 104),
                 (220, 550, 132), (220, 564, 132)]
    else:
        route = [(0, -20, 0), (0, -5, 0), (0, 19, 12), (0, 65, 12),
                 (0, 86, 12), (0, 118, 28), (0, 140, 28), (0, 162, 28),
                 (0, 194, 44), (0, 250, 72), (0, 279, 72), (32, 300, 72),
                 (130, 440, 104), (200, 534, 132), (220, 550, 132),
                 (220, 564, 132)]
    for i, (a, b) in enumerate(zip(route, route[1:])):
        ascending = abs(b[2] - a[2]) > EPS
        bridge = i >= len(route) - 5
        solids.append(Ramp(f"route_{i:02d}", a, b, 4.0,
                           0.6 if bridge or not ascending else None,
                           0.16 if ascending else 0.0))
    courts = {
        "A_low": list(grid(-15, 15, -30, -10, 0)),
        "A_rear": list(grid(-15, 15, 50, 75, 12)),
        "B": list(grid(bx - 20, bx + 20, 122, 154, 28)),
        "C": list(grid(cx - 20, cx + 20, 275, 300, 72)),
    }
    if include_structures:
        solids.extend([
            Cylinder("C_furnace", cx, 310, 4, 72, 82),
            Box("C_roof", (cx - 20, 304, 86), (cx + 20, 330, 87)),
        ])
        for x in (-17, 17):
            for y in (306, 326):
                solids.append(Cylinder(f"C_column_{x}_{y}", cx + x, y,
                                       0.45, 72, 86))
    return {"obstacles": solids, "courts": courts, "route": route,
            "centres_m": {"A_low": [0, -20, 0], "A_rear": [0, 65, 12],
                          "B": [bx, 140, 28], "C": [cx, 300, 72],
                          "D": [220, 580, 132]}}


def layout_from_spec(path: Path, include_structures=False):
    """Read builder output without importing/executing the Unreal builder.

    Floors are exact axis-aligned bounds; crags are radius-based approximations.
    Each stair is a conservative ramp envelope, not a physical step simulation.
    Ridge radii/centres are taken from build_blockout.py V06 first implementation.
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    solids, courts, centres = [], {}, {}
    radii = {"A_Shanmen": 28, "B_MartialCourt": 29, "C_AlchemyCourt": 31}
    for p in spec["platforms"]:
        x, y, z = p["center"]
        name = p["name"]
        centres[name] = p["center"]
        if p.get("shape") == "circle":
            solids.append(Cylinder(name,x,y,p["radius"],z-1.2,z))
            continue
        polygon = p.get("points") if p.get("shape") == "polygon" else None
        if polygon:
            for i, (x0,x1,y0,y1) in enumerate(orthogonal_polygon_rectangles(polygon)):
                solids.append(Box(f"{name}_floor_{i}",(x0,y0,z-1.2),(x1,y1,z)))
            # Current builder's explicit B cut shoulder: lower original crag
            # six metres; retain solid support below both remaining floor parts.
            solids.extend([Cylinder(name+"_crag", x,y,radii[name],-40,z-7.5),
                           Box("B_front_rock",(-28,118,19),(14,140,27)),
                           Box("B_rear_rock",(-28,138,19),(28,162,27))])
        else:
            w, d = p["size"]
            solids.append(Box(name + "_floor", (x - w/2, y - d/2, z - 1.2),
                              (x + w/2, y + d/2, z)))
            solids.append(Cylinder(name + "_crag", x,y,radii[name],-40,z-1.5))
        if name.startswith("A_"):
            courts["A"] = list(grid(x - 20, x + 20, y - 22, y + 24, z))
        elif name.startswith("B_"):
            courts["B"] = [p for p in grid(x-20,x+20,y-18,y+18,z)
                           if not polygon or point_in_polygon(p[0],p[1],polygon)]
        else:
            courts["C"] = list(grid(x - 20, x + 20, y - 25, y, z))
    if not any(s.name == "D_SummitFloor" for s in solids):
        solids.append(Cylinder("D_SummitFloor", 220, 580, 30, 130.8, 132))
    solids.append(Cylinder("D_crag", 220, 580, 29.5, -63, 130.5))
    for i, (x, y, z, r) in enumerate(((80,360,88,12), (130,440,104,13),
                                      (190,520,122,13))):
        solids.append(Cylinder(f"RidgePillar_{i}", x, y, r, -65, z - 1.5))
    for stair in spec["stairs"]:
        solids.append(Ramp(stair["name"], tuple(stair["a"]), tuple(stair["b"]),
                           stair["width"], 0.7, stair["riser"]))
        solids.append(Ramp(stair["name"] + "_spine",
                           add(tuple(stair["a"]), (0,0,-.25)),
                           add(tuple(stair["b"]), (0,0,-.25)),
                           stair["width"] * .82, 3.5, 0.0))
    nodes = {str(n["index"]): tuple(n["ground"]) for n in spec["nodes"]}
    for n in (2, 4, 6):
        x, y, z = nodes[str(n)]
        w, d = (8,5) if n in (2,4) else (9,8)
        solids.append(Box(f"Node{n}_landing", (x-w/2,y-d/2,z-1),
                          (x+w/2,y+d/2,z)))
    for rest in spec.get("rests", []):
        x,y,z = rest["center"]
        w,d = rest["size"]
        solids.append(Box(rest["name"],(x-w/2,y-d/2,z-1),
                          (x+w/2,y+d/2,z)))
    if include_structures:
        fx, fy, fz = spec.get("furnace", [0,310,72])
        solids.extend([Cylinder("C_furnace", fx, fy, 4.3, fz, fz+12.1),
                       Box("C_roof", (-22,305,85.0), (22,325,88.0))])
        for x in (-17.22,17.22):
            for y in (309.56,320.44):
                solids.append(Cylinder("C_pavilion_column", x, y, .55,72,85.2))
    route = [nodes["1"]] + [tuple(p) for p in spec["route"]] + [nodes["7"]]
    return {"obstacles": solids, "courts": courts, "route": route,
            "centres_m": centres, "nodes": nodes, "source": str(path)}


def audit_points(points, obstacles):
    rim, crown = target_points()
    bad = Counter()
    blockers = Counter()
    examples = []
    tested = 0
    rim_failures = crown_failures = 0
    for foot in points:
        # Once on D, endpoint identity is local; distant-rim tests no longer
        # apply. Do not count "looking down the reached summit" as a failure.
        if foot[2] >= 131.5:
            continue
        for height in EYE_HEIGHTS:
            for offset in EYE_OFFSETS:
                tested += 1
                eye = add(foot, (offset, 0, height))
                rim_hits = [nearest_hit(eye, point, obstacles) for point in rim]
                crown_hit = nearest_hit(eye, crown, obstacles)
                visible_rim = sum(hit is None for hit in rim_hits)
                # A bridge may hide the central rim without hiding the peak.
                # Require two adjacent arc samples: a recognisable solid edge.
                adjacent_rim = any(a is None and b is None
                                   for a, b in zip(rim_hits, rim_hits[1:]))
                rim_failures += int(not adjacent_rim)
                crown_failures += int(crown_hit is not None)
                if not adjacent_rim or crown_hit is not None:
                    key = f"eye_{height:.1f}m"
                    bad[key] += 1
                    for hit in rim_hits + [crown_hit]:
                        if hit:
                            blockers[hit[1]] += 1
                    if len(examples) < 6:
                        examples.append({"foot_m": [round(v, 3) for v in foot],
                                         "eye_height_m": height,
                                         "eye_offset_m": offset,
                                         "rim_visible_of_9": visible_rim,
                                         "rim_segment_visible": adjacent_rim,
                                         "rim_blockers": [h[1] if h else None
                                                          for h in rim_hits],
                                         "crown_blocker": crown_hit[1]
                                         if crown_hit else None})
    return {"eye_samples": tested, "failed_eye_samples": sum(bad.values()),
            "rim_failed_eye_samples": rim_failures,
            "crown_failed_eye_samples": crown_failures,
            "rim_visible_fraction": round(1 - rim_failures / tested, 5)
            if tested else None,
            "failures_by_eye_height": dict(bad),
            "blockers": dict(blockers.most_common()), "examples": examples}


def audit_layout(corrected=False, include_structures=False, spec_path=None):
    layout = (layout_from_spec(Path(spec_path), include_structures) if spec_path
              else make_layout(corrected, include_structures))
    result = {"mode": "spec" if spec_path else "corrected" if corrected else "baseline",
              "model": "terrain + 4m route envelopes" +
                       (" + approximate C structures" if include_structures else ""),
              "centres_m": layout["centres_m"], "courts": {}}
    for name, points in layout["courts"].items():
        result["courts"][name] = audit_points(points, layout["obstacles"])
    result["route_1m"] = audit_points(sample_polyline(layout["route"]),
                                        layout["obstacles"])
    result["route_waypoints_m"] = layout["route"]
    if "nodes" in layout:
        result["nodes"] = {name: audit_points([point], layout["obstacles"])
                           for name, point in layout["nodes"].items()
                           if float(name) < 7}
        result["source"] = layout["source"]
    result["limits"] = [
        "Analytic draft only; replace shapes with actual UE bounds/traces.",
        "1m court/path sampling is discrete, not a continuous visibility proof.",
        "No tree canopy, railings, VFX, doors or terrain between supplied solids.",
        "Path is a mathematical 4m corridor; physical collision/landings untested.",
        "Rim requires 2 adjacent of 9 arc points AND crown; centre is not rim.",
    ]
    return result


def self_test():
    box = Box("test", (0, 0, 0), (1, 1, 1))
    assert box.intersect((-1, .5, .5), (2, .5, .5)) is not None
    assert box.intersect((-1, 2, .5), (2, 2, .5)) is None
    cylinder = Cylinder("test", 0, 0, 1, 0, 2)
    assert cylinder.intersect((-2, 0, 1), (2, 0, 1)) is not None
    assert cylinder.intersect((-2, 0, 3), (2, 0, 3)) is None
    ramp = Ramp("test", (0, 0, 0), (0, 10, 5), 2, None, 0)
    assert ramp.intersect((0, 5, 1), (0, 5, 4)) is not None
    assert ramp.intersect((-2, 5, 4), (2, 5, 4)) is None
    points = list(sample_polyline([(0, 0, 0), (2.5, 0, 0)], 1))
    assert points[-1] == (2.5, 0, 0)
    assert all(math.dist(a, b) <= 1.0 + EPS for a, b in zip(points, points[1:]))
    polygon = [[-30,116],[15,116],[15,138],[30,138],[30,164],[-30,164]]
    assert not point_in_polygon(20,127,polygon)
    assert point_in_polygon(20,150,polygon)
    assert math.isclose(sum((x1-x0)*(y1-y0) for x0,x1,y0,y1
                            in orthogonal_polygon_rectangles(polygon)),2550)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("spec", "baseline", "corrected", "both"),
                        default="spec")
    parser.add_argument("--spec", type=Path,
                        default=Path(__file__).resolve().parents[3] / "Docs" /
                        "LevelDesign" / "Blockout_v01" / "LayoutSpec.json")
    parser.add_argument("--include-structures", action="store_true")
    parser.add_argument("--json", type=Path,
                        help="Optional report path. Otherwise prints JSON only.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if args.mode == "spec":
        report = [audit_layout(include_structures=args.include_structures,
                               spec_path=args.spec)]
    else:
        modes = [False, True] if args.mode == "both" else [args.mode == "corrected"]
        report = [audit_layout(mode, args.include_structures) for mode in modes]
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
