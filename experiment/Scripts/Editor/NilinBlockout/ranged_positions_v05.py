"""Six static talisman sentries on accessible mountain outcrops, in metres.

This module has no Unreal dependency.  ``build(scene)`` accepts the existing
Scene.box/beam/part adapter and returns encounter planning metadata.  It does not
create AI, triggers, damage, projectiles or an attack scheduler.  The two-actor
attack budget is a design constraint for the later gameplay implementation.

All three rock shelves attach to existing level stair rests.  They leave the
eight-metre central ascent and the Node02/Node04 recovery landings unchanged.
The caller must remove ONLY old rails within ``rail_clearance`` before using
the new connections; the saved level needs a collision/LOS validation pass.
"""
import math


STATIONS = (
    {
        'id': 'R01', 'name': 'Lower ascent talisman rock outcrop',
        'flight': 'A_to_Rest', 'route_rest': (0.0, 45.275, 6.4),
        'side': -1, 'approach_foot': (0.0, 42.395, 5.44),
    },
    {
        'id': 'R02', 'name': 'Martial ascent talisman rock outcrop',
        'flight': 'B_to_Threshold', 'route_rest': (0.0, 177.075, 34.4),
        'side': 1, 'approach_foot': (0.0, 174.1625, 33.12),
    },
    {
        'id': 'R03', 'name': 'Alchemy ascent talisman rock outcrop',
        'flight': 'Threshold_to_C',
        'route_rest': (0.0, 233.703571428571, 56.8),
        'side': -1, 'approach_foot': (0.0, 230.657142857143, 55.68),
    },
)


def _point(station, x, y, z=0.0):
    """Local x is distance outward from the ascent centreline."""
    _, ry, rz = station['route_rest']
    return (station['side'] * x, ry + y, rz + z)


def _rock(scene, name, station, outline, layers, mat='Cliff', inner_limit=None):
    """A closed, faceted rock with a flat upper face, in local metres.

    Outline is counterclockwise; layers are bottom-to-top (height, scale,
    x-shift, y-shift). After constructing mathematical outward winding and
    correcting the mirrored outcrops, reverse for UE GeometryScript's visible
    front-face convention. Rock is visual; inset stock-box cores provide
    reliable walkable collision.
    """
    count = len(outline)
    area = sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(outline, outline[1:] + outline[:1]))
    if area <= 0:
        raise ValueError('Rock outline must be counterclockwise: ' + name)
    cx = sum(p[0] for p in outline) / count
    cy = sum(p[1] for p in outline) / count
    vertices = []
    for height, scale, dx, dy in layers:
        for x, y in outline:
            rx = cx + (x - cx) * scale + dx
            if inner_limit is not None and height > -4:
                rx = max(inner_limit, rx)
            vertices.append(_point(station, rx, cy + (y - cy) * scale + dy, height))
    triangles = []
    for ring in range(len(layers) - 1):
        for i in range(count):
            a = ring * count + i
            b = ring * count + (i + 1) % count
            c, d = a + count, b + count
            triangles.extend([(a, b, d), (a, d, c)])
    for ring, bottom in ((0, True), (len(layers) - 1, False)):
        points = vertices[ring * count:(ring + 1) * count]
        center = len(vertices)
        vertices.append(tuple(sum(p[k] for p in points) / count for k in range(3)))
        for i in range(count):
            a, b = ring * count + i, ring * count + (i + 1) % count
            triangles.append((center, b, a) if bottom else (center, a, b))
    if station['side'] < 0:
        triangles = [(a, c, b) for a, b, c in triangles]
    # UE's rendered front face is opposite the mathematical cross-product
    # convention used above. Without this final conversion all near faces are
    # culled and the inset collision boxes become visibly exposed inside shells.
    triangles = [(a, c, b) for a, b, c in triangles]
    scene.part(name, vertices, triangles, mat, False)


def _boulder(scene, name, station, foot, size, seed=0, mat='CliffLight', solid=True):
    """A chipped boulder, with a smaller collision core buried inside it."""
    x, y, z = foot
    width, depth, height = size
    outline = []
    for index in range(9):
        angle = 2 * math.pi * index / 9
        irregularity = 1 + .08 * math.sin(index * 2.7 + seed)
        outline.append((x + width * .5 * math.cos(angle) * irregularity,
                        y + depth * .5 * math.sin(angle) * irregularity))
    _rock(scene, name, station, outline,
          [(z - .18, .88, 0, 0), (z + height * .28, 1.04, 0, 0),
           (z + height * .76, 1.00, 0, 0),
           (z + height, .78, 0, 0)], mat)
    if solid:
        scene.box(name + '_BuriedCollision', _point(station, x, y, z + height * .43),
                  (width * .54, depth * .54, height * .82), mat, True)


def _sentry(scene, name, foot, aim_target):
    """A robed, raised-arm figure and a gold paper talisman; no collision."""
    dx, dy = aim_target[0] - foot[0], aim_target[1] - foot[1]
    distance = math.hypot(dx, dy)
    forward = (dx / distance, dy / distance)
    right = (forward[1], -forward[0])
    yaw = math.degrees(math.atan2(right[1], right[0]))

    def p(x, y, z):
        return (foot[0] + right[0] * x + forward[0] * y,
                foot[1] + right[1] * x + forward[1] * y, foot[2] + z)

    def box(suffix, center, size, material='Dummy'):
        scene.box(name + '_' + suffix, p(*center), size,
                  material, False, yaw)

    for side in (-1, 1):
        box('Foot_' + str(side), (side * .17, .035, .15), (.20, .35, .30))
    box('RobeHem', (0, 0, .57), (.78, .48, .75))
    box('RobeBody', (0, 0, 1.14), (.58, .40, .66))
    box('Belt', (0, .01, .96), (.63, .44, .10), 'Trim')
    box('Head', (0, 0, 1.69), (.34, .32, .36))
    box('Topknot', (0, 0, 1.93), (.15, .17, .14), 'Wood')
    scene.beam(name + '_RaisedUpperArm', p(.30, 0, 1.37),
               p(.51, .28, 1.53), .21, .23, 'Dummy', False)
    scene.beam(name + '_RaisedForearm', p(.51, .28, 1.53),
               p(.46, .62, 1.76), .16, .18, 'Dummy', False)
    scene.beam(name + '_SupportingArm', p(-.30, 0, 1.37),
               p(-.43, .34, 1.22), .19, .22, 'Dummy', False)
    box('TalismanPaper', (.46, .64, 1.93), (.25, .055, .43), 'Warm')
    box('TalismanSeal', (.46, .676, 1.92), (.09, .028, .16), 'Dummy')
    # The future projectile leaves the paper's upper tip, clearing the low
    # natural rock lip rather than starting inside the sentry's lower arm.
    return p(.46, .66, 2.10)


def _station(scene, config):
    station = dict(config)
    sid = station['id']
    name = 'V10_Ranged_' + sid
    p = lambda x, y, z=0.0: _point(station, x, y, z)
    variant = int(sid[-1])
    # Broad, irregular rock faces grow down into the existing mountain. Upper
    # surfaces remain outside x=4.25, preserving the main ascent's clear width.
    # Each outline has different facets; no timber support or pavilion remains.
    shelf_outline = [
        (4.25, -4.95), (6.15, -5.45 - .12 * variant),
        (10.7 + .18 * variant, -5.35), (15.2, -5.50 + .11 * variant),
        (16.65 + .10 * variant, -3.65), (16.8, -.8),
        (17.0 - .11 * variant, 2.8), (16.1, 5.25),
        (13.7, 5.80 - .15 * variant), (10.2, 5.35),
        (7.1 - .15 * variant, 5.65), (4.25, 4.85),
    ]
    _rock(scene, name + '_MountainRoot', station, shelf_outline,
          [(-15.0 - variant * 1.7, .57, -2.2, .7),
           (-7.2, 1.02, -.8, -.45 + variant * .2),
           (-2.3, 1.08, -.25, .05), (-.65, 1.025, 0, 0),
           (0, 1, 0, 0)], 'Cliff', inner_limit=4.24)
    # Stable flat collision is 8 mm beneath the rendered rock; its rectangular
    # sides are fully enclosed by the larger natural stone footprint.
    scene.box(name + '_ShelfBuriedCollision', p(10.0, 0, -.504),
              (11.5, 9.2, .992), 'Cliff', True)
    throat = [(3.68, -.70), (4.7, -.72), (5.2, -.38),
              (5.2, .43), (4.6, .72), (3.68, .70)]
    _rock(scene, name + '_RockNeck', station, throat,
          [(-.72, 1, 0, 0), (0, 1, 0, 0)], 'CliffLight')
    scene.box(name + '_NeckBuriedCollision', p(4.15, 0, -.354),
              (.80, 1.25, .692), 'CliffLight', True)

    # One irregular raised ridge supports both sentries. The two shallow teeth
    # at its front make their silhouettes read as enemies standing on crags.
    ridge_outline = [
        (4.70, 1.90), (5.40, 1.08 + .10 * variant),
        (7.35, 1.16), (9.15, 1.60), (11.50, 1.12),
        (12.65, 1.55), (15.65, 1.70), (16.45, 2.75),
        (16.10, 4.55), (14.60, 5.40), (10.35, 5.15),
        (7.25, 5.52 - .10 * variant), (4.55, 4.15),
    ]
    _rock(scene, name + '_RaisedSentryCrag', station, ridge_outline,
          [(-.5, 1.07, -.12, -.13), (.72, 1.045, .10, -.08),
           (1.80, 1.015, -.06, -.03), (2.4, 1, 0, 0)], 'CliffLight')
    scene.box(name + '_CragBuriedCollision', p(10.60, 3.16, 1.196),
              (9.8, 2.88, 2.392), 'CliffLight', True)

    # The same fifteen 16 cm steps climb the outer flank. Chipped stone meshes
    # wrap their inset collision boxes; no wooden staircase or handrail is used.
    steps = []
    for index in range(15):
        height = (index + 1) * .16
        local_y = -3.7 + (index + .5) * .36
        cut = .045 + .012 * ((index + variant) % 3)
        step_outline = [(12.77, local_y - .1825 + cut),
                        (12.77 + cut, local_y - .1825),
                        (15.23 - cut, local_y - .1825),
                        (15.23, local_y - .1825 + cut),
                        (15.23, local_y + .1825 - cut),
                        (15.23 - cut, local_y + .1825),
                        (12.77 + cut, local_y + .1825),
                        (12.77, local_y + .1825 - cut)]
        _rock(scene, name + '_HewnStoneStep_%02d' % (index + 1), station,
              step_outline, [(-.06, 1.005, 0, 0), (height, 1, 0, 0)], 'Stone')
        scene.box(name + '_StepBuriedCollision_%02d' % (index + 1),
                  p(14.0, local_y, (height - .008) / 2),
                  (2.30, .365, height - .008), 'Stone', True)
        steps.append(p(14.0, local_y, height))
    # Broken, staggered natural rock rims replace the architectural balustrade.
    # The throat, southern approach aisle, stair axis and firing faces stay open.
    rim_specs = [(6.1, -5.0, 0, 2.3, .85, .75),
                 (10.0, -5.0, 0, 2.6, .95, .85),
                 (14.2, -5.0, 0, 2.2, .90, 1.00),
                 (16.15, -3.3, 0, .95, 2.1, 1.15),
                 (16.05, -.65, 0, .95, 2.0, 1.45),
                 (16.15, 3.1, 2.4, .90, 1.9, 1.05),
                 (13.5, 5.05, 2.4, 2.6, 1.0, 1.20),
                 (8.5, 5.05, 2.4, 3.0, .95, 1.05),
                 (4.85, 3.55, 2.4, .90, 1.6, 1.15)]
    for index, (x, y, h, width, depth, height) in enumerate(rim_specs):
        _boulder(scene, name + '_BrokenRockRim_%02d' % index, station,
                 (x, y, h), (width, depth, height), variant * 7 + index)

    # Natural stone cover keeps the previous footprint and the same clear aisles.
    cover_specs = [
        {'id': sid + '_Cover01', 'foot': p(5.65, -2.50),
         'size': (1.5, 1.25, 2.10), 'purpose': 'standing retreat cover'},
        {'id': sid + '_Cover02', 'foot': p(9.35, -.55),
         'size': (2.1, 1.0, 1.75), 'purpose': 'lateral approach cover'},
    ]
    for index, cover in enumerate(cover_specs):
        local = (abs(cover['foot'][0]), cover['foot'][1] - station['route_rest'][1], 0)
        _boulder(scene, 'V10_' + cover['id'] + '_NaturalBoulder', station,
                 local, cover['size'], variant * 11 + index)
        cover['visual_theme'] = 'irregular natural boulder with buried collision core'

    aim = (station['approach_foot'][0], station['approach_foot'][1],
           station['approach_foot'][2] + 1.60)
    enemies = []
    for index, xpos in enumerate((7.4, 11.5), 1):
        eid = sid + '_Talisman_%02d' % index
        foot = p(xpos, 2.45, 2.4)
        origin = _sentry(scene, 'V10_' + eid, foot, aim)
        enemies.append({
            'id': eid, 'foot': foot, 'role': 'ranged_talisman',
            'display_only': True, 'visual_collision': False,
            'tag': 'NLBlockout.EncounterEnemy.' + eid,
            'aim_target': aim, 'projectile_origin': origin,
            'perch_height_above_gallery': 2.4,
        })

    # Access samples follow the free southern shelf, outer stone steps and the
    # raised crag. Nothing requires jumping or a vertical movement mechanic.
    access = [station['route_rest'], p(3.3, 0), p(4.5, 0), p(6.6, 0),
              p(7.0, -3.85), p(14.0, -3.85)]
    access.extend(steps)
    access.extend([p(14.0, 2.4, 2.4), p(11.5, 2.45, 2.4),
                   p(7.4, 2.45, 2.4)])
    station.update({
        'display_only': True, 'enemy_count': 2,
        'visual_theme': 'natural_rock_outcrops',
        'simultaneous_attacker_budget': 2,
        # Legacy landing/deck keys describe the encounter envelopes. The actual
        # surfaces are irregular natural rock, with stable inset collision cores.
        'landing': {'center': p(10.25, 0), 'size': (12, 10)},
        'raised_deck': {'center': p(10.25, 3.35, 2.4), 'size': (12, 3.30)},
        'rock_shelf': {'top_outline': [p(x, y) for x, y in shelf_outline],
                       'root_depth': 15.0 + variant * 1.7},
        'sentry_crag': {'top_outline': [p(x, y, 2.4) for x, y in ridge_outline],
                        'height_above_shelf': 2.4},
        'collision_implementation': 'inset stock-box cores 8 mm below the horizontal rock faces; visual rock meshes have no collision',
        'main_route_clear_width': 8.0,
        'connection': {'center': p(4.15, 0), 'size': (.80, 1.25)},
        'rail_clearance': {
            'center': p(4.0, 0, 1.05), 'size': (.95, 1.72, 2.30),
            'match_labels_only': ['Handrail', 'RailPost'],
            'reason': 'Open only the existing level-rest side rail; retain adjacent stair rails.',
        },
        'access_stairs': {'width': 2.4, 'riser': .16, 'tread': .36,
                          'steps': steps},
        'access_route': access, 'enemies': enemies, 'covers': cover_specs,
        'shooting_lanes': [
            {'enemy_id': enemy['id'], 'from': enemy['projectile_origin'],
             'to': enemy['aim_target'], 'purpose': 'visible downhill telegraph'}
            for enemy in enemies
        ],
        'encounter_design': {
            'activation': 'approach enters this flight only; never activate adjacent stations together',
            'attack_cadence': 'alternate telegraphed single projectiles; avoid simultaneous crossfire',
            'retreat': 'return downhill behind the previous flight break or use natural boulder cover',
            'melee_fallback': 'flush rock neck and outer stone steps reach both sentries',
            'recovery_nodes': 'Node02 and Node04 remain enemy-free',
        },
    })
    return station


def build(scene):
    """Emit natural rock outcrops and six static enemy figures; return specs."""
    stations = [_station(scene, station) for station in STATIONS]
    return {
        'version': 'V10 ascent ranged-enemy placement blockout',
        'visual_theme': 'natural_rock_outcrops',
        'units': 'metres', 'display_only': True,
        'implemented_ai': False, 'total_enemies': 6,
        'simultaneous_attacker_budget': 2,
        'stations': stations,
        'safe_recovery_nodes': ['Node02_Landing', 'Node04_Landing'],
        'notes': [
            'Only whitebox silhouettes and encounter spaces are implemented; no projectile damage or runtime AI.',
            'Remove only legacy side-rest rails in the returned clearance boxes before level validation.',
            'Both sentries on each natural rock crag can be reached on foot by 16 cm stone steps.',
            'The unchanged central ascent is eight metres wide; the side connection is 1.25 m deep.',
            'Pavilion posts, crossbeams, timber brackets, architectural rails and capped masonry cover have been removed.',
            'Flat, inset collision cores support the old route and enemy foot positions; irregular rock exteriors hide their rectangular sides.',
            'The two-attacker budget is global design intent, not a running attack director.',
        ],
    }
