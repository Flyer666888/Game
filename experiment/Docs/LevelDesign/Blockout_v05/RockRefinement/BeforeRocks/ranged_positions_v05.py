"""Six static talisman sentries on accessible side galleries, in metres.

This module has no Unreal dependency.  ``build(scene)`` accepts the existing
Scene.box/beam adapter and returns encounter planning metadata.  It does not
create AI, triggers, damage, projectiles or an attack scheduler.  The two-actor
attack budget is a design constraint for the later gameplay implementation.

All three galleries attach to existing level stair rests.  They leave the
eight-metre central ascent and the Node02/Node04 recovery landings unchanged.
The caller must remove ONLY old rails within ``rail_clearance`` before using
the new connections; the saved level needs a collision/LOS validation pass.
"""
import math


STATIONS = (
    {
        'id': 'R01', 'name': 'Lower ascent talisman gallery',
        'flight': 'A_to_Rest', 'route_rest': (0.0, 45.275, 6.4),
        'side': -1, 'approach_foot': (0.0, 42.395, 5.44),
    },
    {
        'id': 'R02', 'name': 'Martial ascent talisman gallery',
        'flight': 'B_to_Threshold', 'route_rest': (0.0, 177.075, 34.4),
        'side': 1, 'approach_foot': (0.0, 174.1625, 33.12),
    },
    {
        'id': 'R03', 'name': 'Alchemy ascent talisman gallery',
        'flight': 'Threshold_to_C',
        'route_rest': (0.0, 233.703571428571, 56.8),
        'side': -1, 'approach_foot': (0.0, 230.657142857143, 55.68),
    },
)


def _point(station, x, y, z=0.0):
    """Local x is distance outward from the ascent centreline."""
    _, ry, rz = station['route_rest']
    return (station['side'] * x, ry + y, rz + z)


def _rail(scene, name, a, b, height=1.15):
    """Collision rails with only enough posts for a readable whitebox."""
    scene.beam(name + '_Rail', (a[0], a[1], a[2] + height),
               (b[0], b[1], b[2] + height), .22, .20, 'Stone', True)
    length = math.dist(a, b)
    spans = max(1, math.ceil(length / 3.2))
    for index in range(spans + 1):
        t = index / spans
        p = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
        scene.box(name + '_Post_%02d' % index,
                  (p[0], p[1], p[2] + (height + .15) / 2),
                  (.28, .28, height + .15), 'Stone', True)


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
    # The future projectile leaves the paper's upper tip, clearing the safety
    # rail rather than being spawned inside the sentry's lower arm.
    return p(.46, .66, 2.10)


def _station(scene, config):
    station = dict(config)
    sid = station['id']
    name = 'V10_Ranged_' + sid
    p = lambda x, y, z=0.0: _point(station, x, y, z)
    z = station['route_rest'][2]

    # The main gallery starts 25 cm outside the old eight-metre stair width.
    # Only its narrow, flush throat reaches the existing 1.25 m level rest.
    scene.box(name + '_SideGallery', p(10.25, 0, -.50),
              (12, 10, 1), 'Landing', True)
    scene.box(name + '_FlushRestConnection', p(4.15, 0, -.35),
              (.80, 1.25, .70), 'Landing', True)
    # Brackets under the gallery show how it is fixed into the mountainside.
    for offset in (-3.6, 3.6):
        scene.beam(name + '_Cantilever_%s' % offset,
                   p(4.6, offset, -4.2), p(15.7, offset, -.65),
                   .70, .75, 'Wood', True)
        scene.box(name + '_Anchor_%s' % offset, p(4.7, offset, -2.2),
                  (.75, 1.0, 4.1), 'Stone', True)

    # The raised rear strip provides elevation and a reachable melee fallback.
    scene.box(name + '_RaisedFiringDeck', p(10.25, 3.35, 1.2),
              (12, 3.30, 2.4), 'Stone', True)
    steps = []
    for index in range(15):
        height = (index + 1) * .16
        local_y = -3.7 + (index + .5) * .36
        scene.box(name + '_AccessStep_%02d' % (index + 1),
                  p(14.0, local_y, height / 2),
                  (2.4, .365, height), 'Floor', True)
        steps.append(p(14.0, local_y, height))

    # Stone rails wrap the exposed edges, with a single flush side opening.
    _rail(scene, name + '_FrontEdge', p(4.25, -5), p(16.25, -5))
    _rail(scene, name + '_OuterLowerEdge', p(16.25, -5), p(16.25, 1.7))
    _rail(scene, name + '_OuterUpperEdge', p(16.25, 1.7, 2.4), p(16.25, 5, 2.4))
    _rail(scene, name + '_RearEdge', p(4.25, 5, 2.4), p(16.25, 5, 2.4))
    _rail(scene, name + '_InnerLowerEdge', p(4.25, -5), p(4.25, -.85))
    _rail(scene, name + '_InnerUpperEdge', p(4.25, .85), p(4.25, 1.7))
    _rail(scene, name + '_InnerRaisedEdge', p(4.25, 1.7, 2.4), p(4.25, 5, 2.4))
    _rail(scene, name + '_FiringDeckFront', p(4.25, 1.7, 2.4), p(12.6, 1.7, 2.4))
    _rail(scene, name + '_AccessOuterHandrail', p(15.4, -3.7), p(15.4, 1.7, 2.4))

    # Small open timber posts and upturned crossbeam ends echo the Chinese
    # architecture, without adding a roof over the player's ascent view.
    for xpos in (5.25, 15.25):
        scene.box(name + '_TimberPost_%s' % xpos, p(xpos, 4.15, 4.1),
                  (.34, .34, 3.4), 'Wood', True)
        scene.box(name + '_PostFoot_%s' % xpos, p(xpos, 4.15, 2.56),
                  (.66, .66, .32), 'Stone', True)
    scene.box(name + '_OpenEfang', p(10.25, 4.15, 5.70),
              (10.8, .42, .36), 'Wood', True)
    scene.box(name + '_EfangGoldBand', p(10.25, 4.15, 5.85),
              (10.95, .44, .10), 'Trim', False)
    for xpos, direction in ((4.85, -1), (15.65, 1)):
        scene.beam(name + '_RaisedEave_%s' % xpos,
                   p(xpos, 4.15, 5.70), p(xpos + direction * .70, 4.15, 6.02),
                   .32, .24, 'Wood', False)

    # Cover remains entirely inside the side gallery, never on the main steps.
    cover_specs = [
        {'id': sid + '_Cover01', 'foot': p(5.65, -2.50),
         'size': (1.5, 1.25, 2.10), 'purpose': 'standing retreat cover'},
        {'id': sid + '_Cover02', 'foot': p(9.35, -.55),
         'size': (2.1, 1.0, 1.75), 'purpose': 'lateral approach cover'},
    ]
    for cover in cover_specs:
        center = (cover['foot'][0], cover['foot'][1], z + cover['size'][2] / 2)
        scene.box('V10_' + cover['id'], center, cover['size'], 'Stone', True)
        scene.box('V10_' + cover['id'] + '_Cap',
                  (center[0], center[1], z + cover['size'][2] + .06),
                  (cover['size'][0] + .12, cover['size'][1] + .12, .12),
                  'Trim', True)

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

    # Access samples follow the free southern aisle, the outer steps, and the
    # rear deck.  Nothing requires jumping or a vertical movement mechanic.
    access = [station['route_rest'], p(3.3, 0), p(4.5, 0), p(6.6, 0),
              p(7.0, -3.85), p(14.0, -3.85)]
    access.extend(steps)
    access.extend([p(14.0, 2.4, 2.4), p(11.5, 2.45, 2.4),
                   p(7.4, 2.45, 2.4)])
    station.update({
        'display_only': True, 'enemy_count': 2,
        'simultaneous_attacker_budget': 2,
        'landing': {'center': p(10.25, 0), 'size': (12, 10)},
        'raised_deck': {'center': p(10.25, 3.35, 2.4), 'size': (12, 3.30)},
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
            'retreat': 'return downhill behind the previous flight break or use side-gallery cover',
            'melee_fallback': 'flush side connection and guarded outer access steps reach both sentries',
            'recovery_nodes': 'Node02 and Node04 remain enemy-free',
        },
    })
    return station


def build(scene):
    """Emit static gallery geometry and six enemy figures; return specifications."""
    stations = [_station(scene, station) for station in STATIONS]
    return {
        'version': 'V10 ascent ranged-enemy placement blockout',
        'units': 'metres', 'display_only': True,
        'implemented_ai': False, 'total_enemies': 6,
        'simultaneous_attacker_budget': 2,
        'stations': stations,
        'safe_recovery_nodes': ['Node02_Landing', 'Node04_Landing'],
        'notes': [
            'Only whitebox silhouettes and encounter spaces are implemented; no projectile damage or runtime AI.',
            'Remove only legacy side-rest rails in the returned clearance boxes before level validation.',
            'Both sentries at each gallery can be reached on foot by 16 cm steps.',
            'The unchanged central ascent is eight metres wide; the side connection is 1.25 m deep.',
            'The two-attacker budget is global design intent, not a running attack director.',
        ],
    }
