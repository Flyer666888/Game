"""Deterministic, seamless technical PBR maps for the local V03 sword.

No downloaded imagery or provider service is used. Normal PNGs encode a
DirectX tangent frame: red +U, green toward image-down, blue outward.
"""
from pathlib import Path
import hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

P = Path(__file__).resolve().parents[3]
OUT = P/'ArtSource/WeaponReview/SelectedA_DetailV03/Textures'
OUT.mkdir(parents=True,exist_ok=True)
N = 512
SEED = 315927
rng = np.random.default_rng(SEED)
fy = np.fft.fftfreq(N)[:,None]
fx = np.fft.fftfreq(N)[None,:]

def field(scale_x,scale_y):
    data = rng.normal(size=(N,N))
    response = np.exp(-2*math.pi**2*((scale_x*fx)**2+(scale_y*fy)**2))
    smooth = np.fft.ifft2(np.fft.fft2(data)*response).real
    return np.clip((smooth-smooth.mean())/(smooth.std()+1e-12),-3.5,3.5)/3.5

def blur_periodic(data,sigma):
    return np.fft.ifft2(np.fft.fft2(data)*np.exp(-2*math.pi**2*sigma*sigma*(fx*fx+fy*fy))).real

def normals(height, target_rms, max_slope):
    # Texture-row direction is image-down. A high spot leans its normal away
    # from its height gradient, so the encoded green has DirectX orientation.
    dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.5
    dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.5
    multiplier=target_rms/math.sqrt(float(np.mean(dx*dx+dy*dy))+1e-16)
    nx=np.clip(-dx*multiplier,-max_slope,max_slope)
    ny=np.clip(-dy*multiplier,-max_slope,max_slope)
    nz=np.ones_like(nx)
    lengths=np.sqrt(nx*nx+ny*ny+nz*nz)
    return np.stack((nx/lengths,ny/lengths,nz/lengths),axis=2)*.5+.5

files={}
def write(name,data,kind,srgb=False):
    data=np.clip(data,0,1)
    pixels=np.round(data*255).astype(np.uint8)
    path=OUT/(name+'.png')
    Image.fromarray(pixels).save(path,optimize=True)
    across=np.concatenate(((data[:,0]-data[:,-1]).reshape(-1),(data[0]-data[-1]).reshape(-1)))
    internal=np.concatenate((np.diff(data,axis=0).reshape(-1),np.diff(data,axis=1).reshape(-1)))
    stats={
        'min':float(data.min()),'max':float(data.max()),'mean':float(data.mean()),
        'std':float(data.std()),'border_difference_rms':float(np.sqrt(np.mean(across*across))),
        'interior_difference_rms':float(np.sqrt(np.mean(internal*internal))),
        'finite':bool(np.isfinite(data).all())}
    stats['border_to_interior_difference_ratio']=stats['border_difference_rms']/max(stats['interior_difference_rms'],1e-12)
    if kind=='normal':
        decoded=pixels.astype(float)/255*2-1
        length=np.linalg.norm(decoded,axis=2)
        stats.update({'decoded_length_min':float(length.min()),'decoded_length_max':float(length.max()),
                      'decoded_z_min':float(decoded[:,:,2].min()),'green_convention':'DirectX / image-down'})
        assert length.min()>.99 and length.max()<1.01 and decoded[:,:,2].min()>.95
    assert stats['finite'] and stats['border_to_interior_difference_ratio']<2.5
    files[name]={'file':str(path),'relative_file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'size':[N,N],'channels':1 if data.ndim==2 else data.shape[2],
                 'type':kind,'sRGB':srgb,'address_x':'wrap','address_y':'wrap','stats':stats}

# Fine polishing aligned with V, with broad low-contrast variation rather than
# large rust spots or worn-through patches. Shorter directional grain gives
# the metal a roughness signal that survives normal mip filtering.
steel_brush=field(1.15,29.0)
steel_variation=field(20,62)
steel_fine=field(.55,8)
steel_h=.74*steel_brush+.18*steel_fine+.08*steel_variation
write('SteelSurface_Roughness',.275+.055*steel_brush+.018*steel_variation+.008*steel_fine,'roughness')
write('SteelSurface_Normal',normals(steel_h,.025,.065),'normal')

# Small shallow tooling/hammering marks; all color comes from engine metal
# constants, retaining correct metallic reflectance instead of dirty albedo.
guard_h=.65*field(5,5)+.23*field(1.7,1.7)+.12*field(16,16)
guard_var=field(32,32)
write('AgedSilver_Roughness',.335+.075*guard_h+.035*guard_var,'roughness')
write('AgedSilver_Normal',normals(guard_h,.032,.09),'normal')

# Very fine leather relief. The grip keeps its existing UV topology and is
# rendered as near-black desaturated leather, not brightly colored plastic.
leather_cells=field(2.2,2.8)
leather_grain=np.tanh(leather_cells*2.8)+.22*field(.65,.8)
leather_broad=field(24,30)
write('DarkLeather_Roughness',.61+.095*leather_cells+.04*leather_broad,'roughness')
write('DarkLeather_Normal',normals(leather_grain,.065,.16),'normal')

# Draw narrow gently branching crystal veins on a torus. Repeating every
# branch at ± one tile gives continuous edges before periodic filtering.
veins=Image.new('L',(N,N),0)
draw=ImageDraw.Draw(veins)
for branch in range(5):
    start=rng.uniform(0,N,size=2)
    angle=rng.uniform(-math.pi,math.pi)
    points=[start.copy()]
    for index in range(int(rng.integers(11,19))):
        angle+=rng.normal(0,.22)
        points.append(points[-1]+rng.uniform(6,11)*np.array([math.cos(angle),math.sin(angle)]))
    for shift_x in (-N,0,N):
        for shift_y in (-N,0,N):
            shifted=[(float(p[0]+shift_x),float(p[1]+shift_y)) for p in points]
            draw.line(shifted,fill=180 if branch%2 else 230,width=1)
    if branch<3:
        origin=points[len(points)//2]
        branch_angle=angle+.65
        twig=[origin.copy()]
        for index in range(5):
            branch_angle+=rng.normal(0,.2)
            twig.append(twig[-1]+rng.uniform(5,9)*np.array([math.cos(branch_angle),math.sin(branch_angle)]))
        for shift_x in (-N,0,N):
            for shift_y in (-N,0,N):
                draw.line([(float(p[0]+shift_x),float(p[1]+shift_y)) for p in twig],fill=135,width=1)
vein=blur_periodic(np.array(veins,dtype=float)/255,.55)
vein_halo=blur_periodic(vein,2.4)
cloud=field(31,31)*.70+field(12,19)*.30
ice_base=np.zeros((N,N,3))
for channel,(base,variance) in enumerate(zip((.68,.81,.845),(.052,.038,.028))):
    ice_base[:,:,channel]=base+cloud*variance+vein*.16+vein_halo*.14
write('IceJade_BaseColor',ice_base,'base_color',True)
write('IceJade_Roughness',.285+cloud*.038+vein*.06,'roughness')
write('IceJade_Normal',normals(cloud*.2-vein,.014,.055),'normal')

def maps(prefix,base=False):
    result={'roughness':prefix+'_Roughness','normal':prefix+'_Normal'}
    if base:result['base_color']=prefix+'_BaseColor'
    return result

contract={
    'state':'passed','version':'V03','generator':str(Path(__file__).resolve()),
    'provenance':'Locally authored deterministic technical PBR maps. No downloaded or AI-provider imagery.',
    'seed':SEED,'resolution':N,'files':files,
    'normal_convention':'DirectX tangent-space normal; green image-down. Unreal texture compression Normalmap; sRGB false; do not flip green.',
    'roughness_import':'sRGB false; CompressionSettings Masks or Grayscale; use red output.',
    'sampling':'Default mipmaps, wrap U/V, trilinear or anisotropic filtering. Avoid sharpening.',
    'periodicity':'All stochastic fields use periodic FFT filtering, all derivatives wrap, and veins are rasterized onto a torus. Texture borders need not be duplicate pixels; their neighbor differences are comparable to interior differences.',
    'materials':{
        'BladeSteel':{'textures':maps('SteelSurface'),'uv_scale':[1,1],'direction':'polish lines parallel to V; map V along blade length','base_color_linear':[.52,.55,.58],'metallic':1.0,'roughness_multiplier':1.0,'normal_strength':1.0},
        'BladeEdge':{'textures':maps('SteelSurface'),'uv_scale':[1,1],'base_color_linear':[.61,.64,.67],'metallic':1.0,'roughness_multiplier':.72,'normal_strength':.55},
        'GuardMetal':{'textures':maps('AgedSilver'),'uv_scale':[2,2],'base_color_linear':[.43,.46,.49],'metallic':1.0,'roughness_multiplier':1.0,'normal_strength':1.0},
        'DarkLeather':{'textures':maps('DarkLeather'),'uv_scale':[4,4],'base_color_linear':[.014,.019,.021],'metallic':0.0,'roughness_multiplier':1.0,'normal_strength':1.0},
        'IceJade':{'textures':maps('IceJade',True),'uv_scale':[1,1],'metallic':0.0,'roughness_multiplier':1.0,'normal_strength':1.0,'opacity':1.0,'emissive':0.0}},
    'ice_vein_coverage_above_0_1':float((vein>.1).mean()),
    'limits':'This is offline texture validation. Unreal material compilation and game lighting review are separate.'}
contract['sets']={}
for prefix in ('SteelSurface','AgedSilver','DarkLeather','IceJade'):
    tex={}
    for role,suffix in (('roughness','Roughness'),('normal','Normal'),('base_color','BaseColor')):
        key=prefix+'_'+suffix
        if key in files:
            tex[role]={'file':files[key]['file'],'srgb':files[key]['sRGB'],'sha256':files[key]['sha256']}
    contract['sets'][prefix]={'textures':tex,'roughness_range':[files[prefix+'_Roughness']['stats']['min'],files[prefix+'_Roughness']['stats']['max']],
                              'roughness_mean':files[prefix+'_Roughness']['stats']['mean']}
contract['blender_preview']='These normal images are DirectX. In Blender invert the green channel before a Normal Map node (RGB=(R,1-G,B)).'
contract['suggested_uv_scale_for_4cm_geometry_uvs']={'SteelSurface':[1,1],'AgedSilver':[1,1],'IceJade':[2,2],'DarkLeather_original_grip_uvs':[4,4]}
(OUT/'material_texture_contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False),encoding='utf-8')

# Inspection sheet: first column is roughness, second normal, third ice color
# or representative base tint. It is an inspection preview, not a PBR render.
tile=256
sheet=Image.new('RGB',(tile*3+48,tile*4+160),(25,29,34))
draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
for row,prefix in enumerate(('SteelSurface','AgedSilver','DarkLeather','IceJade')):
    y=36+row*(tile+30)
    draw.text((12,y-24),prefix,fill=(225,230,235),font=font)
    for col,suffix in enumerate(('Roughness','Normal','BaseColor')):
        file=OUT/(prefix+'_'+suffix+'.png')
        if file.exists():img=Image.open(file).convert('RGB').resize((tile,tile))
        else:
            color={'SteelSurface':(190,196,200),'AgedSilver':(174,181,186),'DarkLeather':(31,38,40)}[prefix]
            img=Image.new('RGB',(tile,tile),color)
        x=12+col*(tile+12)
        sheet.paste(img,(x,y))
        draw.text((x+6,y+tile-21),suffix if file.exists() else 'base tint example',font=small,fill=(235,235,235),stroke_width=1,stroke_fill=(30,30,30))
sheet.save(OUT/'SurfaceMaps_ContactSheet.png')
print(json.dumps({'state':'passed','files':len(files),'output':str(OUT),'max_border_ratio':max(x['stats']['border_to_interior_difference_ratio'] for x in files.values()),'ice_vein_coverage':contract['ice_vein_coverage_above_0_1']},indent=2))
