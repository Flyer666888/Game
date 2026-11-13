"""Encode existing Unreal PNGs using Blender's bundled FFmpeg, without editing assets.

Default: 46 captured samples at t=0..1.5s (30Hz), two 1x passes then one 0.5x.
--smoke uses old offline PNGs ONLY to verify the encoder, into EncodingSmoke.mp4.
No Blender scene, source frame, or Unreal asset is changed.
"""
import bpy, json, struct, sys
from pathlib import Path

P = Path(r'D:/game design/experiment')
OUT = P / 'Docs/Gameplay/SlashRevision1104'
smoke = '--smoke' in sys.argv
def option(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

folder = Path(option('--frames', str(OUT / ('OfflineFrames' if smoke else 'DemoFrames')))).resolve()
dest = Path(option('--output', str(OUT / ('EncodingSmoke.mp4' if smoke else 'NativeSlashDemo.mp4')))).resolve()
assert dest.suffix.lower() == '.mp4'
assert dest.is_relative_to(P.resolve()), 'Output must remain inside this project'
assert not dest.exists() or '--replace' in sys.argv, 'Output exists; pass --replace only for this generated preview'
if smoke:
    frames = [folder / ('attack_%03d.png' % (i * 3)) for i in range(8)]
else:
    frames = [folder / ('frame_%03d.png' % i) for i in range(100)]
assert all(f.is_file() and f.stat().st_size > 10000 for f in frames), 'Capture incomplete'
sizes = []
for path in frames:
    raw = path.read_bytes()[:24]
    assert raw[:8] == b'\x89PNG\r\n\x1a\n', path
    sizes.append(struct.unpack('>II', raw[16:24]))
assert len(set(sizes)) == 1, 'Mixed dimensions'
width, height = sizes[0]
assert width % 2 == 0 and height % 2 == 0, 'H264 requires even dimensions'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = width
scene.render.resolution_y = height
scene.render.resolution_percentage = 100
scene.render.fps = 60
scene.render.fps_base = 1.0
scene.render.use_sequencer = True
scene.render.use_compositing = False
scene.render.use_file_extension = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.sequencer_colorspace_settings.name = 'sRGB'
editor = scene.sequence_editor_create()

font = None
for fontpath in (Path('C:/Windows/Fonts/msyh.ttc'), Path('C:/Windows/Fonts/simhei.ttf')):
    if fontpath.is_file():
        font = bpy.data.fonts.load(str(fontpath))
        break

def label(name, text, channel, start, duration, position, size):
    strip = editor.strips.new_effect(name, 'TEXT', channel, start, length=duration)
    strip.text = text
    if font: strip.font = font
    strip.font_size = size * width / 1280
    strip.color = (1, 1, 1, 1)
    strip.location = position
    strip.use_shadow = True
    strip.shadow_color = (0, 0, 0, 1)
    strip.use_box = True
    strip.box_color = (.015, .022, .032, .78)
    strip.box_margin = .008
    return strip

def image_sequence(name, ordered, start):
    strip = editor.strips.new_image(name, str(ordered[0]), 1, start)
    for path in ordered[1:]: strip.elements.append(path.name)
    strip.frame_final_duration = len(ordered)
    strip.colorspace_settings.name = 'sRGB'
    return strip

timeline = []
next_frame = 1
if smoke:
    plans = [('ENCODER TEST', frames, '1.0x', 0)]
else:
    # Endpoint sample at t=1.5 is held between passes; 45 intervals form exactly 1.5s.
    plans = [
        ('normal_1', frames[:99], '1.0x  原速', 30),
        ('normal_2', frames[:99], '1.0x  原速', 30),
        ('slow', [p for p in frames[:99] for _ in range(2)], '0.5x  慢放', 60),
    ]
for name, ordered, speed, hold in plans:
    expanded = ordered + [frames[-1]] * hold
    image_sequence(name, expanded, next_frame)
    label('Speed_' + name, speed, 3, next_frame, len(expanded), (.85, .94), 28)
    timeline.append({'section': name, 'start_frame': next_frame,
                     'motion_frames': len(ordered), 'hold_frames': hold, 'speed_label': speed})
    next_frame += len(expanded)
scene.frame_start = 1
scene.frame_end = next_frame - 1
label('Title', '编码测试' if smoke else '新骨架 · 大幅度劈砍 v07', 2, 1, scene.frame_end, (.25, .94), 28)
label('Source', 'Offline encoder check' if smoke else 'Unreal Engine 当前动画预览',
      4, 1, scene.frame_end, (.5, .045), 20)

scene.render.image_settings.media_type = 'VIDEO'
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
scene.render.ffmpeg.audio_codec = 'NONE'
scene.render.filepath = str(dest)
bpy.ops.render.render(animation=True)
assert dest.is_file() and dest.stat().st_size > 1000, 'Encoder did not write a video'

# Render one labeled preview with the same sequencer for immediate visual QA.
scene.frame_set(4 if smoke else 48)
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
poster = dest.with_suffix('.png')
scene.render.filepath = str(poster)
bpy.ops.render.render(write_still=True)
decoded = editor.strips.new_movie('EncodedVerification', str(dest), 8, scene.frame_end + 10)
decoded_meta = {'frames': decoded.frame_duration, 'fps': decoded.fps,
                'width': decoded.elements[0].orig_width, 'height': decoded.elements[0].orig_height}
assert decoded_meta['frames'] == scene.frame_end and abs(decoded_meta['fps'] - 60) < .01
assert decoded_meta['width'] == width and decoded_meta['height'] == height
editor.strips.remove(decoded)
report = {'source': str(folder), 'output': str(dest), 'smoke_only': smoke,
          'frames': scene.frame_end, 'fps': 60, 'duration_seconds': scene.frame_end / 60,
          'width': width, 'height': height, 'sections': timeline,
          'source_frame_count': len(frames), 'source_sizes_consistent': True,
          'bytes': dest.stat().st_size, 'poster': str(poster),
          'decoded_video': decoded_meta,
          'note': 'Existing PNG samples encoded; no scene or game assets changed. No invented in-between frames.'}
dest.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('SLASH_VIDEO_ENCODED ' + json.dumps(report, ensure_ascii=True))

