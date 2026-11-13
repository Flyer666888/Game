"""Pack newly rendered comparison frames into two authoring GIFs and a sheet."""
from pathlib import Path
from PIL import Image,ImageDraw
PROJECT=Path(__file__).resolve().parents[2]
OUT=PROJECT/'ArtSource/WuxiaMale/DeathSelection20261012'
for label in ('Before','After'):
 frames=[Image.open(p).convert('RGB') for p in sorted((OUT/(label+'Frames')).glob('frame_*.png'))]
 if len(frames)!=34:raise RuntimeError('Need complete rendered '+label+' clip.')
 path=OUT/(label+'DeathAuthorPreview.gif')
 frames[0].save(path,save_all=True,append_images=frames[1:],duration=[100]*33+[20],loop=0,optimize=True)
 print('DEATH_COMPARISON_GIF',path.name,path.stat().st_size)
sheet=Image.new('RGB',(1600,760),(32,32,32));draw=ImageDraw.Draw(sheet)
for row,label in enumerate(('Before','After')):
 for col,frame in enumerate((0,13,19,27)):
  image=Image.open(OUT/(label+'Frames')/('frame_%03d.png'%frame)).convert('RGB');image.thumbnail((400,340))
  x=col*400;y=row*380+30;sheet.paste(image,(x,y));draw.text((x+10,row*380+8),label+'  %.1f s'%(frame*.1),fill=(230,230,230))
sheet.save(OUT/'DeathBeforeAfterContactSheet.png')
