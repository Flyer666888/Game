"""Pack the two authored paper textures and lay out the Blender preview renders."""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def pack_images(images, filename, fill):
    atlas = Image.new("RGB", (2048, 2048), fill)
    for image, x in zip(images, (16, 1072)):
        image = image.resize((960, 2016), Image.Resampling.LANCZOS)
        atlas.paste(image, (x, 16))
        atlas.paste(image.crop((0, 0, 960, 1)).resize((960, 16)), (x, 0))
        atlas.paste(image.crop((0, 2015, 960, 2016)).resize((960, 16)), (x, 2032))
        atlas.paste(image.crop((0, 0, 1, 2016)).resize((16, 2016)), (x - 16, 16))
        atlas.paste(image.crop((959, 0, 960, 2016)).resize((16, 2016)), (x + 960, 16))
    atlas.save(ROOT / filename, optimize=True)


def pack_atlas():
    papers = [Image.open(ROOT / f"T_Talisman_{side}.png").convert("RGB") for side in ("Front", "Back")]
    gold = [Image.open(ROOT / f"T_Talisman_{side}_Gold.png").convert("L") for side in ("Front", "Back")]
    pack_images(papers, "T_JadeTalisman_BaseColor.png", (94, 67, 36))
    packed = []
    for mask in gold:
        metallic = mask.point(lambda x: round(x * .86))
        roughness = mask.point(lambda x: round(193 - .43 * x))
        packed.append(Image.merge("RGB", (Image.new("L", mask.size, 255), roughness, metallic)))
    pack_images(packed, "T_JadeTalisman_MetalRough.png", (255, 197, 0))
    # A fine amber edge follows the interior of the main cinnabar glyph.
    color = np.array(papers[0], dtype=np.float32)
    h, w = color.shape[:2]
    glyph = ((color[:, :, 0] > 1.52 * color[:, :, 1]) &
             (color[:, :, 0] > 1.48 * color[:, :, 2]))
    window = np.zeros((h, w), dtype=bool)
    window[round(.27 * h):round(.84 * h), round(.18 * w):round(.82 * w)] = True
    stroke = Image.fromarray(((glyph & window) * 255).astype("uint8"))
    eroded = np.asarray(stroke.filter(ImageFilter.MinFilter(5)), dtype=np.int16)
    edge = np.asarray(stroke, dtype=np.int16) - eroded
    aura = Image.fromarray(edge.astype("uint8")).filter(ImageFilter.GaussianBlur(.75))
    glow = Image.merge("RGB", (aura, aura.point(lambda x: round(x * .48)), aura.point(lambda x: round(x * .10))))
    pack_images((glow, Image.new("RGB", papers[1].size)), "T_JadeTalisman_Emissive.png", (0, 0, 0))

    rng = np.random.default_rng(1104)
    y, x = np.mgrid[-1:1:512j, -1:1:512j]
    noise = rng.normal(0, .045, (512, 512))
    ripple = np.sin(7 * x + 6 * y + 2 * np.sin(3 * y - 2 * x)) * .5 + .5
    vein = np.exp(-np.square(np.sin(8 * (x + .38 * y) + 1.4 * np.cos(4 * y)) / .18))
    jade = np.clip(.22 + .52 * ripple + .23 * vein + noise, 0, 1)[..., None]
    pixels = np.array([18, 78, 60]) + jade * np.array([110, 117, 103])
    Image.fromarray(pixels.astype("uint8")).save(ROOT / "T_JadeSeal_BaseColor.png", optimize=True)


def layout_preview():
    width, height = 1500, 1050
    backdrop = Image.new("RGB", (300, 210))
    backdrop.putdata([
        tuple(int(base + light * tint) for base, tint in zip((12, 22, 26), (15, 24, 24)))
        for y in range(210) for x in range(300)
        for light in [math.exp(-((x - 92) / 126)**2 - ((y - 115) / 105)**2)]
    ])
    canvas = backdrop.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    def label(position, value, size, fill, bold=False, anchor=None):
        draw.text(position, value, font=ImageFont.truetype(str(BOLD if bold else FONT), size),
                  fill=fill, anchor=anchor)

    def place(name, center, target_height):
        with Image.open(ROOT / f"Render_{name}.png") as source:
            render = source.convert("RGBA")
        crop = render.crop(render.getchannel("A").getbbox())
        scaled = crop.resize((round(crop.width * target_height / crop.height), target_height),
                             Image.Resampling.LANCZOS)
        canvas.alpha_composite(scaled, (round(center[0] - scaled.width / 2), round(center[1] - scaled.height / 2)))

    draw.line((64, 204, 1436, 204), fill="#355359", width=1)
    draw.line((750, 247, 750, 922), fill="#30454b", width=1)
    draw.line((64, 963, 1436, 963), fill="#355359", width=1)
    label((64, 50), "逆鳞   /   持符弟子道具", 23, "#87c8b6", True)
    label((62, 87), "青玉鎏金符", 64, "#f5e4bc", True)
    label((1436, 142), "VERDANT JADE SEAL", 20, "#99b9b7", anchor="ra")
    place("Front", (400, 576), 635)
    place("Back", (1265, 540), 450)
    with Image.open(ROOT / "Render_Seal.png") as source:
        seal = source.convert("RGBA").resize((310, 310), Image.Resampling.LANCZOS)
    canvas.alpha_composite(seal, (790, 344))
    label((400, 915), "正面   ·   鎏金云纹与朱砂", 24, "#f5e4bc", True, "ma")
    label((945, 685), "青玉印   ·   局部放大", 22, "#bdd6cf", True, "ma")
    label((1265, 822), "背面   ·   云篆暗纹", 22, "#bdd6cf", True, "ma")
    label((64, 986), "约 6.5 × 16 厘米     双面符纸     独立青玉与金属材质", 22, "#a2bbb6")
    canvas.convert("RGB").save(ROOT / "Talisman_Preview.png", optimize=True)


parser = argparse.ArgumentParser()
parser.add_argument("step", choices=("atlas", "preview"))
options = parser.parse_args()
(pack_atlas if options.step == "atlas" else layout_preview)()
