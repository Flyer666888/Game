"""Present three complete real UE frames with captions outside the screenshots."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'GameplayEvidence.png'
META = HERE / 'GameplayEvidence.json'
FONT = Path('C:/Windows/Fonts/msyh.ttc')
FONT_BOLD = Path('C:/Windows/Fonts/msyhbd.ttc')
CELL_W, CELL_H = 1280, 720
MARGIN, GAP, BAND, TOP = 24, 24, 46, 116
WIDTH = CELL_W + 2*MARGIN
HEIGHT = TOP + 3*(BAND+CELL_H) + 2*GAP + 48
CAPTION = '自动化验证截图：使用受控姿态／伤害夹具，非人工头显试玩'
FRAMES = (
    ('Queue_FourActive.png', '候场补位'),
    ('Weak_SphereHead.png', '头部弱点 ×1.5'),
    ('Loot_Collected.png', '还元补给拾取'),
)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)


comparison = HERE / 'SceneComparison.png'
comparison_hash = sha(comparison)
canvas = Image.new('RGB', (WIDTH,HEIGHT), '#152028')
draw = ImageDraw.Draw(canvas)
draw.text((MARGIN,20),'玩法验证画面',font=font(34,True),fill='#f2f5f5')
draw.text((MARGIN,70),CAPTION,font=font(22),fill='#edcc8f')
assert draw.textbbox((0,0),CAPTION,font=font(22))[2] <= CELL_W
sources = []
for index,(filename,label) in enumerate(FRAMES):
    path = HERE / filename
    original_hash = sha(path)
    with Image.open(path) as image:
        assert image.size==(CELL_W,CELL_H), (filename,image.size)
        assert image.mode in ('RGB','RGBA'), (filename,image.mode)
        if image.mode=='RGBA':
            assert image.getextrema()[3]==(255,255), filename
        frame = image.convert('RGB')
    y = TOP+index*(BAND+CELL_H+GAP)
    draw.rectangle((MARGIN,y,MARGIN+CELL_W-1,y+BAND-1),fill='#1e2d37')
    draw.text((MARGIN+14,y+7),label,font=font(27,True),fill='#a4ded2')
    canvas.paste(frame,(MARGIN,y+BAND))
    assert sha(path)==original_hash
    sources.append({'index':index,'caption':label,'source':str(path),'sha256':original_hash,
                    'source_dimensions':[CELL_W,CELL_H],
                    'display_rectangle':[MARGIN,y+BAND,CELL_W,CELL_H],
                    'resized':False,'cropped':False,'color_adjusted':False})
draw.text((MARGIN,HEIGHT-33),'原始场景截图未重绘或调色；每格保留完整画面。',font=font(20),fill='#bac8ce')
canvas.save(OUTPUT,optimize=True)
with Image.open(OUTPUT) as proof:
    assert proof.size==(WIDTH,HEIGHT)
    for source in sources:
        x,y,w,h=source['display_rectangle']
        with Image.open(source['source']) as original:
            assert proof.crop((x,y,x+w,y+h)).tobytes()==original.convert('RGB').tobytes()
assert sha(comparison)==comparison_hash, 'Scene comparison changed unexpectedly'
metadata = {
    'state':'composed','created_utc':datetime.now(timezone.utc).isoformat(),
    'output':str(OUTPUT),'output_sha256':sha(OUTPUT),'dimensions':[WIDTH,HEIGHT],
    'source_images':sources,'fixture_notice':CAPTION,
    'layout':'Three full-resolution frames stacked vertically with separate caption bands.',
    'scene_pixels_identical_to_sources':True,'resizing':False,'cropping':False,'color_adjustments':False,
    'ai_generated_scene_content':False,'scene_comparison_unchanged':True,
    'weakpoint_selection':'Sphere-head frame retains the visible in-game x1.5 feedback without the floating blade fixture visible in the blade-head frame.',
}
META.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'state':'composed','output':str(OUTPUT),'dimensions':[WIDTH,HEIGHT]},ensure_ascii=False))
