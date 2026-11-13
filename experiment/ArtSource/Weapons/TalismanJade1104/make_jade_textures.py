"""Paint an ivory, cinnabar, jade and gold revision of the original Nilin seal."""

from pathlib import Path
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / 'Talisman1104'))
from make_talisman_texture import WIDTH, HEIGHT, cinnabar_design, curve, noise_field, paper, point


def polygon(draw, vertices, color):
    draw.polygon([point(vertex) for vertex in vertices], fill=color)


def line(draw, vertices, color, width=2):
    draw.line([point(vertex) for vertex in vertices], fill=color, width=width, joint='curve')


def path(draw, vertices, color, width=2):
    line(draw, curve(vertices, 24), color, width)


def circle(draw, x, y, r, color, width=2):
    draw.ellipse([point((x - r, y - r)), point((x + r, y + r))], outline=color, width=width)


def disk(draw, x, y, r, color):
    draw.ellipse([point((x - r, y - r)), point((x + r, y + r))], fill=color)


def dyed_paper():
    fibers = np.asarray(paper().convert('RGB'), dtype=np.float32)
    ivory = np.asarray((234, 214, 161), dtype=np.float32)
    fibers = ivory + (fibers - (224, 184, 109)) * .72
    return Image.fromarray(np.clip(fibers, 0, 255).astype(np.uint8)).convert('RGBA')


def frame_polygon(inset):
    left, right = 24 + inset, 488 - inset
    top, bottom = 37 + inset, 1213 - inset
    corner = 29
    return [(left + corner, top), (right - corner, top),
            (right, top + corner), (right, bottom - corner),
            (right - corner, bottom), (left + corner, bottom),
            (left, bottom - corner), (left, top + corner)]


def jade_frame(surface, rear):
    zone = Image.new('L', surface.size)
    brush = ImageDraw.Draw(zone)
    polygon(brush, frame_polygon(0), 255)
    polygon(brush, frame_polygon(22), 0)
    mineral = noise_field(19, 47) + .5 * noise_field(70, 110)
    rgb = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for index, (base, amplitude) in enumerate(((23, 18), (72, 35), (62, 28))):
        rgb[..., index] = np.clip(base + mineral * amplitude - (6 if rear else 0), 0, 255)
    jade = Image.fromarray(rgb).convert('RGBA')
    jade.putalpha(zone)
    return Image.alpha_composite(surface, jade)


def seal_watermark(surface, rear):
    layer = Image.new('RGBA', surface.size)
    draw = ImageDraw.Draw(layer)
    if rear:
        center, radius, strength = (256, 651), 126, 63
    else:
        center, radius, strength = (256, 660), 152, 38
    cx, cy = center
    for offset, opacity, width in ((0, strength, 3), (-7, strength // 2, 2),
                                    (-17, strength // 2, 2)):
        circle(draw, cx, cy, radius + offset, (139, 83, 36, opacity), width)
    for index in range(24):
        angle = index * math.tau / 24
        step = 9 if index % 3 == 0 else 4
        r = radius - 7
        direction = (math.cos(angle), math.sin(angle))
        line(draw, [(cx + direction[0] * r, cy + direction[1] * r),
                    (cx + direction[0] * (r - step), cy + direction[1] * (r - step))],
             (127, 82, 46, strength), 2)
    return Image.alpha_composite(surface, layer)


def scrollwork(draw, rear):
    # Keyed rails around the jade strips, kept inside the sculpted paper edge.
    for inset, opacity, width in ((0, 219, 4), (6, 159, 2), (21, 245, 4), (27, 202, 2)):
        outline = frame_polygon(inset)
        line(draw, outline + outline[:1], opacity, width)
    for flip in (False, True):
        def mirror(x, y):
            return (512 - x if flip else x, y)
        for y in range(125, 1158, 71):
            pattern = [mirror(x, yy) for x, yy in (
                (36, y - 21), (28, y - 13), (28, y + 2), (38, y + 5),
                (44, y + 7), (44, y + 17), (34, y + 22),
            )]
            path(draw, pattern, 156, 2)
            disk(draw, *mirror(36, y - 27), 1.8, 225)
        for bottom in (False, True):
            def corner(x, y):
                return mirror(x, 1250 - y if bottom else y)
            # The long strokes form paired cloud curls within the upper and lower corners.
            primary = [(57, 106), (72, 89), (86, 101), (108, 103),
                       (130, 105), (153, 96), (146, 79),
                       (140, 66), (115, 66), (113, 81),
                       (112, 88), (124, 93), (129, 83)]
            secondary = [(58, 130), (77, 116), (88, 120), (109, 126),
                         (126, 131), (138, 131), (148, 119)]
            path(draw, [corner(*p) for p in primary], 238, 4)
            path(draw, [corner(*p) for p in secondary], 190, 2)
            disk(draw, *corner(76, 142), 2.3, 218)
    center_x, center_y = 256, 175
    for radius, opacity, width in ((78, 233, 4), (82, 169, 2), (91, 157, 2)):
        circle(draw, center_x, center_y, radius, opacity, width)
    for index in range(8):
        angle = index * math.tau / 8
        x = center_x + math.cos(angle) * 89
        y = center_y + math.sin(angle) * 89
        disk(draw, x, y, 3 if index % 2 else 3.8, 242)
    if rear:
        for radius, opacity in ((59, 180), (50, 135)):
            circle(draw, center_x, center_y, radius, opacity, 2)
        vertices = [(center_x, center_y - 42), (center_x + 40, center_y),
                    (center_x, center_y + 42), (center_x - 40, center_y)]
        line(draw, vertices + vertices[:1], 200, 3)
        disk(draw, center_x, center_y, 7, 175)
    else:
        for side in (-1, 1):
            def reflect(x, y):
                return center_x + side * x, center_y + y
            path(draw, [reflect(x, y) for x, y in (
                (92, 0), (106, -3), (105, -22), (124, -20),
                (134, -18), (137, -7), (131, -5),
                (126, -3), (124, -6), (125, -10),
            )], 213, 3)
            path(draw, [reflect(x, y) for x, y in (
                (92, 10), (105, 25), (123, 26), (142, 12),
            )], 177, 2)
    for x in (193, 319):
        line(draw, [(x, 1177), (x + (-25 if x < 256 else 25), 1177)], 200, 2)
    polygon(draw, [(256, 1167), (265, 1176), (256, 1185), (247, 1176)], 216)


def apply_gold(surface, rear):
    mask = Image.new('L', surface.size)
    scrollwork(ImageDraw.Draw(mask), rear)
    mask = mask.filter(ImageFilter.GaussianBlur(.32))
    offset = Image.new('L', surface.size)
    offset.paste(mask, (1, 2))
    shadow = Image.new('RGBA', surface.size, (54, 30, 19))
    shadow.putalpha(offset.point(lambda value: int(value * .53)).filter(ImageFilter.GaussianBlur(.6)))
    surface = Image.alpha_composite(surface, shadow)
    flecks = noise_field(110, 153) + .33 * noise_field(350, 400)
    rgb = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for index, (base, amplitude) in enumerate(((228, 37), (176, 43), (89, 34))):
        rgb[..., index] = np.clip(base + flecks * amplitude, 0, 255)
    foil = Image.fromarray(rgb).convert('RGBA')
    foil.putalpha(mask)
    return Image.alpha_composite(surface, foil), mask


def new_glyph():
    original = cinnabar_design()
    glyph = original.crop((0, int(point((0, 233))[1]), WIDTH, int(point((0, 1162))[1])))
    top = int(point((0, 280))[1])
    height = int(point((0, 1161))[1]) - top
    result = Image.new('L', (WIDTH, HEIGHT))
    result.paste(glyph.resize((WIDTH, height), Image.Resampling.LANCZOS), (0, top))
    return result


def apply_ink(surface, glyph, rear):
    grain = noise_field(22, 39) + .46 * noise_field(220, 329)
    strength = np.asarray(glyph, dtype=np.float32)
    dry = np.clip(strength + grain * 50, 0, 255) * (strength > 0)
    if rear:
        stain = Image.new('RGBA', surface.size, (115, 58, 34))
        ghost = Image.fromarray((dry * .14).astype(np.uint8)).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT).filter(ImageFilter.GaussianBlur(2.4))
        stain.putalpha(ghost)
        return Image.alpha_composite(surface, stain)
    pigment = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for index, (base, amplitude) in enumerate(((105, 48), (24, 21), (23, 17))):
        pigment[..., index] = np.clip(base + grain * amplitude, 0, 255)
    pigment[..., 3] = dry
    return Image.alpha_composite(surface, Image.fromarray(pigment))


def main():
    paper_surface = dyed_paper()
    glyph = new_glyph()
    for name in ('Front', 'Back'):
        rear = name == 'Back'
        ground = paper_surface.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if rear else paper_surface
        surface = seal_watermark(jade_frame(ground, rear), rear)
        surface, foil = apply_gold(surface, rear)
        surface = apply_ink(surface, glyph, rear)
        surface.convert('RGB').save(OUT / f'T_Talisman_{name}.png')
        foil.save(OUT / f'T_Talisman_{name}_Gold.png')


if __name__ == '__main__':
    main()
