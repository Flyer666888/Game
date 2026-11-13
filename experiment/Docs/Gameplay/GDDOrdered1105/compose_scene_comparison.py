"""Lay out real, unchanged UE screenshots for a same-camera evidence report."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'SceneComparison.png'
META = HERE / 'SceneComparison.json'
FONT_REGULAR = Path('C:/Windows/Fonts/msyh.ttc')
FONT_BOLD = Path('C:/Windows/Fonts/msyhbd.ttc')

CELL_W, CELL_H = 800, 450
MARGIN, GAP, BAND = 24, 24, 46
TOP = 100
WIDTH = 2*MARGIN + 2*CELL_W + GAP
HEIGHT = TOP + 2*(BAND + CELL_H) + GAP + 48


def font(size, bold=False):
    path = FONT_BOLD if bold and FONT_BOLD.is_file() else FONT_REGULAR
    assert path.is_file(), path
    return ImageFont.truetype(str(path), size)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


canvas = Image.new('RGB', (WIDTH, HEIGHT), '#152028')
draw = ImageDraw.Draw(canvas)
draw.text((MARGIN, 20), '场景空间层次 · 调整前后', font=font(32, True), fill='#f2f5f5')
draw.text((MARGIN, 65), '实际 Unreal Engine 渲染截图 · 同机位对比', font=font(18), fill='#b9c8ce')

sources = []
for row, (stem, label) in enumerate((('Gate', '山门入口'), ('Overview', '整体山势'))):
    y = TOP + row*(BAND + CELL_H + GAP)
    for column, (folder, state, accent) in enumerate((
        ('ArtBeforeScreenshots', '调整前', '#b9c8ce'),
        ('ArtScreenshots', '调整后', '#9fd8cc'),
    )):
        x = MARGIN + column*(CELL_W+GAP)
        source = HERE / folder / (stem+'.png')
        assert source.is_file(), source
        original_hash = sha(source)
        with Image.open(source) as opened:
            dimensions = opened.size
            assert dimensions[0]*9 == dimensions[1]*16, (source, dimensions)
            assert opened.mode in ('RGB', 'RGBA'), (source, opened.mode)
            if opened.mode == 'RGBA':
                assert opened.getextrema()[3] == (255,255), 'Only fully opaque screenshots may be flattened'
            screenshot = opened.convert('RGB').resize((CELL_W,CELL_H), Image.Resampling.LANCZOS)
        draw.rectangle((x,y,x+CELL_W-1,y+BAND-1), fill='#1e2d37')
        draw.text((x+14,y+8), f'{label}  ·  {state}', font=font(24, True), fill=accent)
        canvas.paste(screenshot, (x,y+BAND))
        draw.rectangle((x,y+BAND,x+CELL_W-1,y+BAND+CELL_H-1), outline='#62717b', width=1)
        assert sha(source) == original_hash
        sources.append({'row':row,'column':column,'scene':stem,'state':state,'source':str(source),
                        'sha256':original_hash,'source_dimensions':list(dimensions),
                        'display_rectangle':[x,y+BAND,CELL_W,CELL_H]})

draw.text((MARGIN, HEIGHT-31), '原始截图仅等比缩放用于排版，场景内容与颜色未作修改。', font=font(16), fill='#b9c8ce')
canvas.save(OUTPUT, optimize=True)
with Image.open(OUTPUT) as checked:
    assert checked.size == (WIDTH,HEIGHT)
metadata = {
    'state':'composed', 'created_utc':datetime.now(timezone.utc).isoformat(),
    'output':str(OUTPUT), 'output_sha256':sha(OUTPUT), 'dimensions':[WIDTH,HEIGHT],
    'cell_dimensions':[CELL_W,CELL_H], 'source_images':sources,
    'presentation':'Two rows by two columns. Row 1 gate, row 2 overview. Before left, after right.',
    'operations':['RGB layout canvas','Proportional 1600x900 to 800x450 resampling','Text in separate header bands'],
    'scene_pixels_repainted':False,'source_color_adjustments':False,'ai_generated_scene_content':False,
    'scope':'Report layout of actual Unreal renderer evidence only.'
}
META.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'state':metadata['state'],'file':str(OUTPUT),'dimensions':metadata['dimensions']},ensure_ascii=False))
