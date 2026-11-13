"""Package offline sequence frames without modifying rendered content."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(r'D:\game design\experiment\ArtSource\WuxiaMale\RigPolishV04\Attack')
folder=root/'PreviewFrames'
font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',20)
frames=[]
for i in range(71):
    frame=Image.new('RGB',(720,440),(32,32,32));draw=ImageDraw.Draw(frame)
    for j,view in enumerate(('Front','Side')):
        im=Image.open(folder/f'{view}_{i:03d}.png').convert('RGB').resize((360,400),Image.Resampling.LANCZOS)
        frame.paste(im,(j*360,35));draw.text((j*360+12,7),f'{view}   {i/30:.2f} s',font=font,fill='white')
    frames.append(frame)
durations=[30,30,40]*23+[30,40]
frames[0].save(root/'NaturalAttack_FullCycle.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
frames[0].save(root/'NaturalAttack_FullCycle_Slow.gif',save_all=True,append_images=frames[1:],duration=[100]*71,loop=0,optimize=False)
for name,indices in [('Entry',[0,2,4,6,8,10]),('Recovery',[50,54,58,62,66,70]),('Strike',[21,23,25,27,29,31])]:
    for view in ('Front','Side'):
        sheet=Image.new('RGB',(1260,900),(24,24,24));draw=ImageDraw.Draw(sheet)
        for n,i in enumerate(indices):
            im=Image.open(folder/f'{view}_{i:03d}.png').convert('RGB').crop((70,100,650,680)).resize((420,420),Image.Resampling.LANCZOS)
            x=(n%3)*420;y=(n//3)*450;sheet.paste(im,(x,y+30));draw.text((x+12,y+4),f'{name} / {view} / {i/30:.3f} s',font=font,fill='white')
        sheet.save(root/f'NaturalAttack_{name}_{view}.jpg',quality=93)
print(root/'NaturalAttack_FullCycle.gif')
