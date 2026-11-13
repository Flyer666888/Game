"""Pack the two authored paper textures and lay out the Blender preview renders."""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def pack_atlas():
    atlas = Image.new("RGB", (2048, 2048), (132, 87, 36))
    for name, x in (("Front", 16), ("Back", 1072)):
        with Image.open(ROOT / f"T_Talisman_{name}.png") as source:
            image = source.convert("RGB").resize((960, 2016), Image.Resampling.LANCZOS)
        atlas.paste(image, (x, 16))
        atlas.paste(image.crop((0, 0, 960, 1)).resize((960, 16)), (x, 0))
        atlas.paste(image.crop((0, 2015, 960, 2016)).resize((960, 16)), (x, 2032))
        atlas.paste(image.crop((0, 0, 1, 2016)).resize((16, 2016)), (x - 16, 16))
        atlas.paste(image.crop((959, 0, 960, 2016)).resize((16, 2016)), (x + 960, 16))
    atlas.save(ROOT / "T_Talisman_Atlas.png", optimize=True)


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
    label((62, 87), "朱砂纸符", 64, "#f5e4bc", True)
    label((1436, 142), "BLENDER  •  3D ASSET", 20, "#99b9b7", anchor="ra")
    place("Front", (405, 573), 620)
    place("Back", (982, 546), 445)
    place("Edge", (1275, 546), 445)
    label((405, 915), "正面   ·   朱砂符纹", 24, "#f5e4bc", True, "ma")
    label((982, 810), "背面   ·   纸纤与透墨", 22, "#bdd6cf", True, "ma")
    label((1275, 810), "斜侧   ·   卷角与薄边", 22, "#bdd6cf", True, "ma")
    label((64, 986), "约 6.5 × 16 厘米     1,360 三角面     单张双面贴图", 22, "#a2bbb6")
    canvas.convert("RGB").save(ROOT / "Talisman_Preview.png", optimize=True)


parser = argparse.ArgumentParser()
parser.add_argument("step", choices=("atlas", "preview"))
options = parser.parse_args()
(pack_atlas if options.step == "atlas" else layout_preview)()
