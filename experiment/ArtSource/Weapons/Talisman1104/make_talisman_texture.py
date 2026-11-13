"""Original hand-laid cinnabar strokes on procedural mulberry paper."""

from pathlib import Path
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


OUT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1024, 2048
LAYOUT_WIDTH, LAYOUT_HEIGHT = 512, 1250
RANDOM = random.Random(916204)
NOISE = np.random.default_rng(916204)


def point(position):
    return position[0] * WIDTH / LAYOUT_WIDTH, position[1] * HEIGHT / LAYOUT_HEIGHT


def noise_field(width, height):
    source = NOISE.integers(0, 256, (height, width), dtype=np.uint8)
    expanded = Image.fromarray(source).resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)
    return np.asarray(expanded, dtype=np.float32) / 255 - .5


def paper():
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    x /= WIDTH - 1
    y /= HEIGHT - 1
    coarse = noise_field(10, 18)
    edge_distance = np.minimum.reduce((x, 1 - x, y * 1.75, (1 - y) * 1.75))
    edge = np.exp(-edge_distance * (29 + 11 * coarse))
    stains = sum(
        weight * np.exp(-((x - cx) / sx) ** 2 - ((y - cy) / sy) ** 2)
        for cx, cy, sx, sy, weight in (
            (.14, .16, .09, .075, .7),
            (.72, .77, .16, .13, .4),
            (.92, .53, .075, .09, .5),
            (.28, .98, .26, .052, 1.2),
            (.57, .18, .12, .12, .34),
        )
    )
    light = 15 * coarse + 8 * noise_field(85, 116) + 5 * noise_field(303, 485)
    light += NOISE.normal(0, 1.9, (HEIGHT, WIDTH)).astype(np.float32)
    light += 8 * np.sin(y * 2.9) + 5 * (1 - np.abs(x - .44) * 2)
    for position, angle in ((.345, -.055), (.704, .075), (.914, -.11)):
        distance = (y - position - (x - .5) * angle) * HEIGHT
        texture = .60 + .25 * np.cos(x * 14 + position * 29)
        light += texture * (8 * np.exp(-((distance - 2) / 2.1) ** 2)
                            - 11 * np.exp(-((distance + 1) / 3.6) ** 2))
    rgb = np.stack(
        (224 + light - 39 * edge - 19 * stains,
         184 + light - 43 * edge - 26 * stains,
         109 + light - 29 * edge - 20 * stains),
        axis=-1,
    )
    base = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert('RGBA')
    fibers = Image.new('RGBA', base.size)
    draw = ImageDraw.Draw(fibers)
    for _ in range(15300):
        x0 = RANDOM.uniform(0, WIDTH)
        y0 = RANDOM.uniform(0, HEIGHT)
        length = RANDOM.uniform(2, 27) if RANDOM.random() < .98 else RANDOM.uniform(28, 74)
        angle = RANDOM.gauss(.9, 1.0)
        dx = length * math.cos(angle)
        dy = length * math.sin(angle)
        color = (86, 51, 28) if RANDOM.random() < .56 else (255, 240, 167)
        draw.line(
            ((x0, y0), (x0 + .49 * dx, y0 + .54 * dy), (x0 + dx, y0 + dy)),
            fill=(*color, RANDOM.randint(4, 30)), width=1,
        )
    return Image.alpha_composite(base, fibers.filter(ImageFilter.GaussianBlur(.31)))


def curve(vertices, steps=36):
    result = []
    start = vertices[0]
    for index in range(1, len(vertices), 3):
        c1, c2, end = vertices[index:index + 3]
        for step in range(steps):
            t = step / steps
            s = 1 - t
            result.append(tuple(
                s ** 3 * start[axis] + 3 * s * s * t * c1[axis]
                + 3 * s * t * t * c2[axis] + t ** 3 * end[axis]
                for axis in range(2)
            ))
        start = end
    return result + [start]


def brush(draw, vertices, widths, opacity=255, nib=.22):
    center = curve(vertices)
    left, right = [], []
    for index, position in enumerate(center):
        before = center[max(0, index - 1)]
        after = center[min(len(center) - 1, index + 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        pressure = index * (len(widths) - 1) / (len(center) - 1)
        section = min(int(pressure), len(widths) - 2)
        factor = pressure - section
        width = (1 - factor) * widths[section] + factor * widths[section + 1]
        rough = 1 + .08 * math.sin(index * .76) + RANDOM.uniform(-.09, .09)
        left.append(point((position[0] + nx * width * rough * (.5 + nib * .3),
                           position[1] + ny * width * rough * (.5 + nib * .3))))
        right.append(point((position[0] - nx * width * (.5 - nib * .3),
                            position[1] - ny * width * (.5 - nib * .3))))
    draw.polygon(left + list(reversed(right)), fill=opacity)


def cinnabar_design():
    ink = Image.new('L', (WIDTH, HEIGHT))
    pen = ImageDraw.Draw(ink)
    # Small handwritten-looking rubric above an invented vertical seal glyph.
    font = ImageFont.truetype(r'C:\Windows\Fonts\simkai.ttf', 91)
    pen.text(point((179, 145)), '敕令', font=font, fill=238, anchor='lt', stroke_width=1)
    for points, weights in (
        ([(246, 85), (259, 74), (263, 77), (265, 113)], [1, 12, 5, .4]),
        ([(209, 102), (223, 93), (232, 93), (238, 112)], [.4, 8, 5, .2]),
        ([(276, 109), (288, 90), (298, 89), (303, 99)], [.4, 6, 8, .5]),
    ):
        brush(pen, points, weights, 215)
    # Asymmetric curves and tapered tails give the large glyph an ink-brush silhouette.
    strokes = [
        ([(138, 304), (187, 305), (302, 270), (363, 292)], [4, 17, 25, 12, .8]),
        ([(257, 252), (279, 283), (269, 341), (247, 370),
          (213, 409), (171, 421), (128, 424)], [2, 22, 30, 29, 22, 5, .8]),
        ([(261, 331), (293, 363), (314, 398), (381, 407)], [1, 10, 21, 30, 8]),
        ([(153, 455), (205, 469), (298, 441), (350, 441)], [3, 11, 21, 18, .5]),
        ([(205, 402), (193, 435), (188, 475), (184, 522)], [6, 17, 15, .8]),
        ([(305, 400), (312, 451), (305, 485), (280, 503)], [3, 15, 18, 7, .7]),
        ([(165, 557), (208, 577), (312, 519), (354, 536),
          (360, 554), (332, 595), (294, 610)], [2, 12, 24, 24, 19, 6, .4]),
        ([(245, 491), (259, 552), (241, 629), (241, 692),
          (241, 735), (272, 781), (316, 773),
          (341, 768), (369, 751), (380, 732)], [2, 22, 26, 30, 28, 17, 11, .5]),
        ([(167, 635), (203, 643), (304, 625), (344, 641)], [2, 13, 25, 14, .6]),
        ([(212, 601), (209, 674), (173, 721), (117, 741)], [3, 19, 29, 18, .8]),
        ([(288, 668), (299, 681), (333, 697), (354, 699)], [1, 9, 20, 4]),
        ([(145, 828), (201, 842), (308, 806), (359, 812)], [2, 19, 26, 17, 1]),
        ([(202, 772), (208, 808), (192, 864), (183, 901)], [4, 22, 19, 7, .7]),
        ([(311, 793), (325, 836), (307, 882), (275, 907),
          (251, 924), (231, 921), (208, 907)], [3, 17, 25, 28, 12, 4, .6]),
        ([(160, 940), (210, 955), (299, 929), (348, 918)], [2, 14, 24, 14, 1]),
        ([(245, 850), (243, 921), (255, 967), (235, 1004),
          (219, 1033), (194, 1048), (167, 1049)], [3, 19, 22, 24, 16, 7, .6]),
        ([(268, 966), (297, 979), (318, 1001), (324, 1019)], [2, 12, 20, 4, .7]),
    ]
    for vertices, widths in strokes:
        brush(pen, vertices, widths, RANDOM.randint(214, 253))
    # Independent square mark gives the lower edge a hand-stamped finish.
    mark = Image.new('L', (156, 156))
    stamp = ImageDraw.Draw(mark)
    stamp.rectangle((8, 8, 148, 148), outline=242, width=9)
    stamp_font = ImageFont.truetype(r'C:\Windows\Fonts\simkai.ttf', 63)
    stamp.text((18, 14), '玄', font=stamp_font, fill=242)
    stamp.text((71, 74), '印', font=stamp_font, fill=241)
    stamp.line(((22, 80), (126, 72)), fill=229, width=5)
    mark = mark.rotate(-7, resample=Image.Resampling.BICUBIC, expand=True)
    ink.paste(mark, tuple(map(int, point((287, 1047)))), mark)
    return ink


def add_decoration(front):
    motif = Image.new('RGBA', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(motif)
    palette = ((140, 78, 36, 140), (247, 214, 129, 130))
    for offset, color, width in ((0, palette[0], 4), (6, palette[1], 3)):
        left, right = 51 + offset, 461 - offset
        top, bottom = 76 + offset, 1175 - offset
        vertices = [(left, top + 44), (left + 18, top + 28), (left + 34, top),
                    (right - 34, top), (right - 17, top + 28), (right, top + 44),
                    (right, bottom - 44), (right - 17, bottom - 28),
                    (right - 34, bottom), (left + 34, bottom),
                    (left + 17, bottom - 28), (left, bottom - 44), (left, top + 44)]
        draw.line([point(p) for p in vertices], fill=color, width=width, joint='curve')
    for mirror in (False, True):
        for y in (110, 1130):
            def flip(x, yy):
                return (512 - x if mirror else x), yy
            cloud = [flip(*p) for p in (
                (59, y + 18), (71, y + 11), (89, y + 13), (100, y + 16),
                (118, y + 24), (136, y + 15), (132, y + 2),
                (127, y - 10), (108, y - 11), (106, y + 1),
                (106, y + 7), (115, y + 9), (119, y + 4),
            )]
            draw.line([point(p) for p in curve(cloud, 18)], fill=(153, 94, 43, 157), width=4)
    return Image.alpha_composite(front, motif.filter(ImageFilter.GaussianBlur(.3)))


def main():
    base = paper()
    design = cinnabar_design()
    mask = np.asarray(design, dtype=np.float32)
    dry = noise_field(26, 31) * 34 + noise_field(154, 301) * 38
    speckles = NOISE.random((HEIGHT, WIDTH))
    weathered = np.clip(mask + dry - np.where(speckles < .037, speckles * 650, 0), 0, 255)
    weathered *= mask > 0
    pigment = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    pigment[..., 0] = np.clip(122 + 38 * noise_field(16, 26) + dry * .40, 0, 255)
    pigment[..., 1] = np.clip(32 + dry * .30, 0, 255)
    pigment[..., 2] = np.clip(26 + dry * .26, 0, 255)
    pigment[..., 3] = weathered
    front = Image.alpha_composite(add_decoration(base), Image.fromarray(pigment))
    ghost = Image.fromarray((weathered * .19).astype(np.uint8)).transpose(
        Image.Transpose.FLIP_LEFT_RIGHT).filter(ImageFilter.GaussianBlur(2.4))
    reverse = Image.new('RGBA', base.size, (135, 51, 31, 255))
    reverse.putalpha(ghost)
    back = Image.alpha_composite(base.transpose(Image.Transpose.FLIP_LEFT_RIGHT), reverse)
    front.convert('RGB').save(OUT / 'T_Talisman_Front.png')
    back.convert('RGB').save(OUT / 'T_Talisman_Back.png')


if __name__ == '__main__':
    main()
