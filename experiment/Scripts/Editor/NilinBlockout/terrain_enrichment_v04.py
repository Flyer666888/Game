"""Twelve closed rock shoulders and distant peaks for the V09 blockout.

Standard library only; all points are metres in the existing mirrored world.
Call build(api), where api.part accepts name, vertices, triangles, mat, collision.
Original V08 terrain, paths and architecture are deliberately not regenerated.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import terrain_v02 as terrain

ROOT = Path(__file__).resolve().parents[3]

# name, centre XY, footprint radii, lower/upper Z, yaw, seed, kind.
# High rings shrink and drift: the shapes read as sloping crags, never cylinders.
ROCKS = (
    ('A_ForeShoulder', (24, -7), (31, 27), -73, -7, -22, 1.1, 'shoulder'),
    ('B_PineShoulder', (27, 144), (29, 24), -78, 20, 18, 2.2, 'shoulder'),
    ('B_WestShoulder', (-22, 163), (24, 25), -74, 20, -32, 3.3, 'shoulder'),
    ('Threshold_SlantRidge', (21, 226), (20, 46), -76, 36, -9, 4.1, 'shoulder'),
    ('C_RearShoulder', (26, 302), (31, 30), -79, 63, 27, 5.2, 'shoulder'),
    ('C_EntryShoulder', (-27, 292), (24, 27), -72, 61, -24, 6.4, 'shoulder'),
    ('Upper_LowerRib', (-85, 361), (33, 39), -78, 79, 29, 7.1, 'shoulder'),
    ('Upper_HigherRib', (-134, 428), (32, 37), -80, 98, 31, 8.4, 'shoulder'),
    ('Summit_SpreadRoot', (-194, 493), (44, 37), -85, 119, -26, 9.3, 'shoulder'),
    ('Far_LowCrag', (68, 217), (18, 22), -68, 57, -16, 10.1, 'distant_peak'),
    ('Far_SplitCrag', (89, 282), (24, 29), -76, 96, 21, 11.7, 'distant_peak'),
    ('Far_LeaningCrag', (86, 367), (27, 35), -77, 113, -28, 12.4, 'distant_peak'),
)


def _rock(spec):
    name, centre, radii, bottom, top, yaw, seed, kind = spec
    # Nine irregular corners, five broadly inclined strata, a small uneven crown.
    n = 9
    strata = ((0.0, .80), (.18, 1.0), (.48, .73), (.76, .46), (1.0, .13))
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    rings = []
    for level, (h, scale) in enumerate(strata):
        ring = []
        drift_x = radii[0] * .28 * h * math.sin(seed)
        drift_y = radii[1] * .23 * h * math.cos(seed * .7)
        for i in range(n):
            theta = 2 * math.pi * i / n + .055 * math.sin(seed + i * 1.7)
            irregular = 1 + .15 * math.sin(3 * theta + seed) + .075 * math.cos(2 * theta - seed)
            lx = radii[0] * scale * irregular * math.cos(theta) + drift_x
            ly = radii[1] * scale * irregular * math.sin(theta) + drift_y
            z = bottom + (top - bottom) * h
            if level not in (0, len(strata)-1):
                z += (top-bottom) * .035 * math.sin(theta * 2 + seed + level)
            elif level == len(strata)-1:
                z -= 1.2 * (1 + math.sin(theta + seed))
            ring.append((centre[0] + lx*c - ly*s,
                         centre[1] + lx*s + ly*c, z))
        rings.append(ring)
    mesh = terrain.mesh_from_rings('V09_Terrain_' + name, rings,
                                  [[p[:2] for p in rings[0]], [p[:2] for p in rings[-1]]])
    mesh.update(kind=kind, bounds_m=terrain.bounds(mesh['vertices']),
                material='Cliff', collision=True)
    mesh['validation'] = terrain.validate_mesh(mesh)
    return mesh


def meshes():
    """Return deterministic closed meshes without creating assets or writing files."""
    return [_rock(s) for s in ROCKS]


def build(api):
    """Emit twelve closed, colliding terrain meshes and return a compact manifest."""
    generated = meshes()
    for m in generated:
        api.part(m['name'], m['vertices'], m['triangles'], mat='Cliff', collision=True)
    return {'module': 'terrain_enrichment_v04', 'units': 'metres',
            'coordinate_system': 'UE world XYZ, already mirrored X',
            'original_terrain_preserved': True, 'mesh_count': len(generated),
            'meshes': [{k: m[k] for k in ('name', 'kind', 'bounds_m', 'validation',
                                         'material', 'collision')} for m in generated]}


def _in_polygon(x, y, points):
    inside = False
    for a, b in zip(points, points[1:] + points[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                inside = not inside
    return inside


def _walking_samples(layout):
    """One-metre stair and court grid, including width, rests and bridgeheads."""
    samples = []
    for stair in layout['stairs']:
        a, b = stair['a'], stair['b']
        run = math.hypot(b[0]-a[0], b[1]-a[1])
        nx, ny = -(b[1]-a[1])/run, (b[0]-a[0])/run
        for i in range(math.ceil(run)+1):
            t = i/math.ceil(run)
            p = [a[k]+(b[k]-a[k])*t for k in range(3)]
            sides = math.ceil(stair['width'])
            for j in range(sides+1):
                lateral = stair['width']*(j/sides-.5)
                samples.append((p[0]+nx*lateral, p[1]+ny*lateral, p[2]))
    for p in layout['platforms']+layout['rests']+layout.get('bridgeheads', []):
        cx, cy, z = p['center']
        points = p.get('points')
        if points:
            xmin, xmax = min(t[0] for t in points), max(t[0] for t in points)
            ymin, ymax = min(t[1] for t in points), max(t[1] for t in points)
        elif 'radius' in p:
            r = p['radius']; xmin, xmax, ymin, ymax = cx-r, cx+r, cy-r, cy+r
        else:
            sx, sy = p['size']; xmin, xmax, ymin, ymax = cx-sx/2, cx+sx/2, cy-sy/2, cy+sy/2
        for xi in range(math.ceil(xmin), math.floor(xmax)+1):
            for yi in range(math.ceil(ymin), math.floor(ymax)+1):
                if points and not _in_polygon(xi, yi, points):
                    continue
                if 'radius' in p and math.hypot(xi-cx, yi-cy)>p['radius']:
                    continue
                samples.append((xi, yi, z))
    samples.extend(tuple(n['ground']) for n in layout['nodes'])
    return samples


def audit(layout_path=None, output_path=None):
    """Audit source triangles only; UE scene collision remains the build's task."""
    layout_path = Path(layout_path or ROOT/'Docs/LevelDesign/Blockout_v03/LayoutSpec.json')
    output_path = Path(output_path or ROOT/'Docs/LevelDesign/Blockout_v04/TerrainEnrichmentSourceAudit.json')
    layout = json.loads(layout_path.read_text(encoding='utf-8'))
    generated = meshes()
    tree = terrain.make_bvh([(m['name'], tuple(m['vertices'][i] for i in tri))
                             for m in generated for tri in m['triangles']])
    sight = []
    for node in layout['nodes'][:6]:
        for eye_height in (1.1, 1.7):
            for ipd in (-.032, .032):
                eye = terrain.add(node['ground'], (ipd, 0, eye_height))
                for label, target in (('peak', (-174, 512.5, 132)),
                                      ('crown', (-174, 532.5, 158))):
                    hit = terrain.bvh_hit(tree, eye, target)
                    sight.append({'node': node['index'], 'eye_height_m': eye_height,
                                  'eye_offset_m': ipd, 'target': label, 'clear': hit is None,
                                  'blocker': hit[1] if hit else None})
    walk = _walking_samples(layout)
    minimum = None; under = []; hit_count = 0
    for p in walk:
        hit = terrain.bvh_hit(tree, (p[0], p[1], 170), (p[0], p[1], -100))
        if not hit:
            continue
        hit_count += 1
        gap = p[2]-(170-270*hit[0])
        minimum = gap if minimum is None else min(minimum, gap)
        if gap < 3:
            under.append({'point_m': p, 'clearance_m': gap, 'mesh': hit[1]})
    corridor = []
    for m in generated:
        for tri in m['triangles']:
            poly = [m['vertices'][i] for i in tri]
            for axis, lim, less in ((0, -14, True), (1, 138, True), (2, 20.5, False)):
                poly = terrain.clip_polygon_3d(poly, axis, lim, less)
            if len(poly)>=3:
                area = sum(math.sqrt(terrain.dot(n:=terrain.cross(terrain.sub(poly[i],poly[0]),
                               terrain.sub(poly[i+1],poly[0])), n))/2 for i in range(1,len(poly)-1))
                if area>1e-5:
                    corridor.append({'mesh': m['name'], 'area_m2': area})
    distant = []
    for m in generated:
        if m['kind'] != 'distant_peak':
            continue
        lo, hi = m['bounds_m']
        # AABB is deliberately conservative: all triangles lie within it.
        closest = min(math.hypot(max(lo[0]-p[0], 0, p[0]-hi[0]),
                                 max(lo[1]-p[1], 0, p[1]-hi[1])) for p in walk)
        distant.append({'mesh': m['name'], 'conservative_horizontal_gap_m': round(closest, 3)})
    report = {'scope': 'New source triangles only; existing geometry and UE collision excluded',
              'source_layout': str(layout_path), 'mesh_count': len(generated),
              'triangles': sum(len(m['triangles']) for m in generated),
              'closed_mesh_validation': {m['name']:m['validation'] for m in generated},
              'maximum_new_height_m': max(m['bounds_m'][1][2] for m in generated),
              'summit_floor_height_m': 132,
              'sight_checks': len(sight), 'blocked_sight_checks': sum(not s['clear'] for s in sight),
              'sight_details': sight, 'walking_samples': len(walk),
              'walking_samples_with_terrain_below': hit_count,
              'minimum_walk_clearance_m': round(minimum, 4) if minimum is not None else None,
              'walk_clearance_under_3m': under[:20],
              'B_corridor_intruding_triangles': len(corridor),
              'distant_peak_horizontal_clearance': distant,
              'pass': not under and not corridor and all(s['clear'] for s in sight)
                      and all(d['conservative_horizontal_gap_m']>=25 for d in distant)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    report = audit()
    print(json.dumps({k: report[k] for k in ('pass', 'mesh_count', 'triangles',
          'blocked_sight_checks', 'walking_samples', 'minimum_walk_clearance_m',
          'B_corridor_intruding_triangles', 'distant_peak_horizontal_clearance',
          'walk_clearance_under_3m')}, indent=2))
    raise SystemExit(0 if report['pass'] else 1)
