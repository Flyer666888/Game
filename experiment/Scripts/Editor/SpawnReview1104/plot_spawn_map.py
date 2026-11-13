"""Render an annotated plan of the spawn points exported from the saved UE map."""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parents[3] / "Docs/Gameplay/SpawnReview1104"
FONT = Path("C:/Windows/Fonts")
BG, PANEL, GRID = "#101820", "#17242e", "#263742"
INK, MUTED, FAINT = "#edf6fa", "#a9bdc9", "#5e7787"
TEAL, FRAME = "#74d9bf", "#354a57"
ROLES = {
    "sword": ("持剑", "#f2b674", "circle"),
    "talisman": ("持符", "#68cef2", "square"),
    "formation_breaker": ("破阵修士", "#ba9af2", "diamond"),
    "master": ("宗师", "#f5d761", "star"),
    "boss": ("首领", "#f484a0", "star"),
}


class Canvas:
    def __init__(self, size):
        self.size = size
        self.image = Image.new("RGB", tuple(v * 2 for v in size), BG)
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {}

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            filename = "msyhbd.ttc" if bold else "msyh.ttc"
            self.fonts[key] = ImageFont.truetype(str(FONT / filename), size * 2)
        return self.fonts[key]

    def text(self, xy, value, size=18, color=INK, bold=False, anchor="lt"):
        self.draw.text(tuple(v * 2 for v in xy), value, font=self.font(size, bold),
                       fill=color, anchor=anchor)

    def box(self, bounds, fill=PANEL, outline=FRAME, radius=14):
        self.draw.rounded_rectangle(tuple(v * 2 for v in bounds), radius=radius * 2,
                                    fill=fill, outline=outline, width=2)

    def line(self, points, color=FRAME, width=1):
        self.draw.line([(x * 2, y * 2) for x, y in points], fill=color, width=width * 2)

    def polygon(self, points, color, outline=None):
        self.draw.polygon([(x * 2, y * 2) for x, y in points], fill=color,
                          outline=outline, width=2)

    def circle(self, xy, radius, color, outline=None):
        x, y = xy
        self.draw.ellipse(tuple(v * 2 for v in (x - radius, y - radius, x + radius, y + radius)),
                          fill=color, outline=outline, width=2)

    def save(self, name):
        self.image.resize(self.size, Image.Resampling.LANCZOS).save(OUTPUT / name, optimize=True)


def meters(vector):
    return [float(v) / 100 for v in vector]


def suffix(point):
    return point["id"].rsplit("_", 1)[-1].replace("Guard", "护卫").replace("Master", "宗师")


def grouped_stages(stages):
    court = [stage for stage in stages if stage["id"].startswith("C")]
    by_location = {}
    for stage in court:
        for point in stage["points"]:
            key = tuple(round(v, 4) for v in point["position"])
            item = by_location.setdefault(key, dict(point, roles=[]))
            item["roles"] = sorted(set(item["roles"]) | set(point["roles"]))
    merged = dict(court[0], id="C", label="炼丹院 · 四阶段共用", points=list(by_location.values()))
    groups = []
    for i, stage in enumerate(stages, 1):
        if stage is court[0]:
            groups.append(dict(merged, sequence=f"{i:02d}–{i + len(court) - 1:02d}"))
        elif stage not in court:
            groups.append(dict(stage, sequence=f"{i:02d}"))
    return groups


def marker(canvas, xy, roles, radius=7):
    x, y = xy
    names = [role for role in ROLES if role in roles]
    colors = [ROLES[role][1] for role in names]
    _, color, shape = ROLES[names[-1]]
    if shape == "circle":
        canvas.circle(xy, radius, color, BG)
    elif shape == "square":
        canvas.box((x - radius, y - radius, x + radius, y + radius), color, BG, 1)
    elif shape == "diamond":
        canvas.polygon([(x, y-radius), (x+radius, y), (x, y+radius), (x-radius, y)], color, BG)
    else:
        points = []
        for i in range(10):
            angle = math.pi * i / 5 - math.pi / 2
            r = radius * (1.25 if i % 2 == 0 else 0.55)
            points.append((x + r * math.cos(angle), y + r * math.sin(angle)))
        canvas.polygon(points, color, BG)
    if len(colors) > 1:
        canvas.circle(xy, radius + 2, None, colors[0])


def entry_marker(canvas, xy, radius=7):
    x, y = xy
    canvas.polygon([(x, y-radius), (x+radius, y+radius), (x-radius, y+radius)], TEAL, BG)


def frame(canvas, bounds, coordinates, pad=3):
    left, top, right, bottom = bounds
    x0 = min(p[0] for p in coordinates) - pad
    x1 = max(p[0] for p in coordinates) + pad
    y0 = min(p[1] for p in coordinates) - pad
    y1 = max(p[1] for p in coordinates) + pad
    scale = min((right-left) / (x1-x0), (bottom-top) / (y1-y0))
    ox = (left+right) / 2 - (x0+x1) * scale / 2
    oy = (top+bottom) / 2 + (y0+y1) * scale / 2

    def project(position):
        return ox + position[0] * scale, oy - position[1] * scale

    step = next(value for value in (2, 5, 10, 20, 25, 50, 100) if value * scale >= 29)
    for i in range(math.ceil((left-ox) / scale / step), math.floor((right-ox) / scale / step) + 1):
        x, _ = project((i*step, 0))
        canvas.line([(x, top), (x, bottom)], GRID)
    for i in range(math.ceil((oy-bottom) / scale / step), math.floor((oy-top) / scale / step) + 1):
        _, y = project((0, i*step))
        canvas.line([(left, y), (right, y)], GRID)
    return project, scale


def trigger_bounds(stage):
    x, y, _ = meters(stage["trigger_center"])
    ex, ey, _ = meters(stage["trigger_extent"])
    return (x-ex, y-ey), (x+ex, y+ey)


def draw_trigger(canvas, project, stage):
    bottom_left, top_right = trigger_bounds(stage)
    x0, y1 = project(bottom_left)
    x1, y0 = project(top_right)
    canvas.box((x0, y0, x1, y1), "#1d333e", "#3e5968", 1)


def ruler(canvas, x, y, distance, scale):
    length = distance * scale
    canvas.line([(x, y), (x + length, y)], MUTED, 2)
    for tick in (x, x + length):
        canvas.line([(tick, y - 4), (tick, y + 4)], MUTED)
    canvas.text((x + length + 10, y), f"{distance} m", 14, MUTED, anchor="lm")


def panel(canvas, bounds, stage, with_start=None, enlarge=False):
    left, top, right, bottom = bounds
    canvas.box(bounds)
    canvas.text((left + 20, top + 18), stage["sequence"], 16, TEAL, True)
    title_offset = 88 if "–" in stage["sequence"] else 61
    canvas.text((left + title_offset, top + 15), stage["label"], 22 if enlarge else 19, INK, True)
    entry = meters(stage["entry"])
    coordinates = [entry] + list(trigger_bounds(stage)) + [meters(p["position"]) for p in stage["points"]]
    if with_start:
        coordinates.append(meters(with_start))
    plot_box = (left+20, top+57, right-20, bottom-46)
    project, scale = frame(canvas, plot_box, coordinates, pad=3.5)
    draw_trigger(canvas, project, stage)
    ep = project(entry)
    entry_marker(canvas, ep)
    canvas.text((ep[0]+10, ep[1]+6), "阶段入口", 13 if not enlarge else 15, TEAL)
    if with_start:
        start = project(meters(with_start))
        canvas.circle(start, 5, INK, BG)
        canvas.text((start[0]+10, start[1]+5), "玩家起点", 15)
    for point in stage["points"]:
        position = meters(point["position"])
        xy = project(position)
        marker(canvas, xy, point["roles"], 8 if enlarge else 6)
        canvas.text((xy[0], xy[1]-12), suffix(point), 19 if enlarge else 14, INK, True, anchor="mb")
        if enlarge:
            canvas.text((xy[0], xy[1]+13), f"({position[0]:g}, {position[1]:g})", 14, MUTED, anchor="mt")
    ruler(canvas, left+24, bottom-21, 10, scale)
    canvas.text((right-20, bottom-31), f"{len(stage['points'])} 个出生位置", 13, MUTED, anchor="rt")


def overview(data, groups):
    canvas = Canvas((1560, 1220))
    canvas.text((46, 30), "逆鳞  /  主关卡配置", 19, TEAL, True)
    canvas.text((46, 62), "敌人刷怪点示意图", 48, INK, True)
    canvas.text((47, 127), "俯视投影  ·  UE 世界坐标（米）  ·  +Y 朝上，+X 朝右", 20, MUTED)
    canvas.box((45, 172, 879, 1135))
    canvas.text((68, 195), "全关卡 · 阶段推进", 24, INK, True)
    coordinates = [meters(data["player_start"])]
    for stage in groups:
        coordinates.extend([meters(stage["entry"]), *trigger_bounds(stage)])
        coordinates.extend(meters(point["position"]) for point in stage["points"])
    project, scale = frame(canvas, (74, 254, 519, 1061), coordinates, pad=8)
    for stage in groups:
        draw_trigger(canvas, project, stage)
    entries = [project(meters(stage["entry"])) for stage in groups]
    canvas.line(entries, "#589787", 2)
    for stage, entry in zip(groups, entries):
        canvas.line([entry, (533, entry[1]), (553, entry[1])], FAINT)
        canvas.text((561, entry[1]), stage["sequence"], 14, TEAL, True, anchor="lm")
        canvas.text((626, entry[1]), stage["label"], 15, INK, anchor="lm")
    for stage, entry in zip(groups, entries):
        entry_marker(canvas, entry, 5)
        for point in stage["points"]:
            marker(canvas, project(meters(point["position"])), point["roles"], 3.5)
    ruler(canvas, 74, 1106, 50, scale)
    canvas.text((854, 1095), "连线表示阶段推进顺序", 16, MUTED, anchor="rt")
    panel(canvas, (903, 172, 1515, 639), groups[0], data["player_start"], enlarge=True)
    canvas.box((903, 660, 1515, 1135))
    canvas.text((931, 686), "图例与点位规则", 23, INK, True)
    for i, (role, (label, _, _)) in enumerate(ROLES.items()):
        x = 943 + 178 * (i % 3)
        y = 742 + 45 * (i // 3)
        marker(canvas, (x, y), [role], 8)
        canvas.text((x+17, y), label, 17, INK, anchor="lm")
    entry_marker(canvas, (943, 834))
    canvas.text((960, 834), "阶段入口", 17, INK, anchor="lm")
    canvas.box((1120, 826, 1137, 842), "#1d333e", "#3e5968", 1)
    canvas.text((1147, 834), "触发范围（俯视）", 17, INK, anchor="lm")
    canvas.line([(929, 867), (1488, 867)], FRAME)
    positions = {tuple(round(v, 4) for v in point["position"])
                 for stage in groups for point in stage["points"]}
    canvas.text((931, 890), f"{len(data['stages'])} 个阶段  /  {len(positions)} 个不同出生位置", 23, TEAL, True)
    canvas.text((931, 934), "炼丹院四阶段共用 8 个位置，点位叠加显示。", 17, MUTED)
    canvas.text((931, 976), "生成时跳过玩家 3 米内及被占用的点。", 17, MUTED)
    canvas.text((931, 1013), "圆环标记表示该位置可用于多种敌人。", 17, MUTED)
    canvas.text((931, 1050), "查看分区详图可读全部编号。", 17, MUTED)
    canvas.text((47, 1165), "来源  " + data["map"].rsplit("/", 1)[-1] + "  ·  保存地图配置", 17, MUTED)
    canvas.save("SpawnOverview.png")


def details(data, groups):
    canvas = Canvas((1920, 1980))
    canvas.text((42, 26), "逆鳞  /  主关卡配置", 19, TEAL, True)
    canvas.text((42, 56), "敌人刷怪点 · 分区详图", 40, INK, True)
    canvas.text((42, 110), "每格单独缩放，按比例尺读距离  ·  +Y 朝上", 18, MUTED)
    for i, (role, (label, _, _)) in enumerate(ROLES.items()):
        x = 874 + 142 * i
        marker(canvas, (x, 122), [role], 8)
        canvas.text((x+17, 122), label, 17, INK, anchor="lm")
    entry_marker(canvas, (1601, 122))
    canvas.text((1618, 122), "入口", 17, INK, anchor="lm")
    canvas.box((1711, 115, 1726, 129), "#1d333e", "#3e5968", 1)
    canvas.text((1736, 122), "触发范围", 17, INK, anchor="lm")
    for i, stage in enumerate(groups):
        left = 42 + (i % 3) * 618
        top = 158 + (i // 3) * 353
        panel(canvas, (left, top, left+600, top+335), stage,
              with_start=data["player_start"] if i == 0 else None)
    canvas.box((660, 1570, 1878, 1905))
    canvas.text((689, 1600), "怎么读这张图", 24, INK, True)
    canvas.text((689, 1650), "编号对应保存地图中的出生点 ID 后缀。", 20, MUTED)
    canvas.text((689, 1693), "炼丹院四阶段使用同一组空间坐标，图中合并为八个点。", 20, MUTED)
    canvas.text((689, 1736), "圆环表示位置可用于多种敌人。图形表示该点可用的一种敌人类型。", 20, MUTED)
    canvas.text((689, 1779), "触发区、入口和敌人出生位置分别标记，候选点按波次启用。", 20, MUTED)
    canvas.text((42, 1940), "来源  " + data["map"].rsplit("/", 1)[-1] + "  ·  保存地图配置", 17, MUTED)
    canvas.save("SpawnDetails.png")


if __name__ == "__main__":
    data = json.loads((OUTPUT / "SpawnLayout.json").read_text(encoding="utf-8-sig"))
    groups = grouped_stages(data["stages"])
    overview(data, groups)
    details(data, groups)
