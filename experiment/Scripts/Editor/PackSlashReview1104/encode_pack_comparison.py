"""Encode complete Unreal package-animation captures with Blender 5.2.

Example (after CandidateCapture.json is complete):
  blender --background --python encode_pack_comparison.py -- --capture <json>

Only existing PNGs are used. No retarget, animation, rig, or gameplay asset is
edited. Every sampled frame is displayed once at 1x and twice at 0.5x.
"""
import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

PROJECT = Path(r'D:/game design/experiment').resolve()
DEFAULT_OUT = PROJECT / 'Docs/Gameplay/PackSlashReview1104'
FPS = 30
HOLD_FRAMES = 12


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=DEFAULT_OUT / 'CandidateCapture.json')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--replace', action='store_true', help='Replace these generated preview outputs.')
    parser.add_argument('--validate-only', action='store_true', help='Inspect complete capture without loading Blender.')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return parser.parse_args(argv)


def load_capture(path):
    path = path.resolve()
    assert path.is_relative_to(PROJECT), 'Capture must be inside this project'
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    clips = report.get('clips')
    assert isinstance(clips, list) and clips, 'Expected a nonempty clips list'
    checks = report.get('checks', {})
    assert checks.get('all_clips_captured') is True, 'Capture has not finished all clips'
    assert checks.get('all_frames_exist') is True, 'Capture frame check did not finish successfully'
    dimensions = set()
    keys = set()
    validated = []
    for i, clip in enumerate(clips):
        key = str(clip['key'])
        assert re.fullmatch(r'[A-Za-z0-9_-]+', key), 'Unsafe output key: ' + key
        assert key not in keys, 'Duplicate clip key: ' + key
        keys.add(key)
        assert abs(float(clip['fps']) - FPS) < 0.001, 'Capture must be complete 30 fps samples'
        duration = float(clip['duration_seconds'])
        assert math.isfinite(duration) and duration > 0
        frames = clip['frames']
        expected_count = math.ceil(duration * FPS) + 1
        assert len(frames) == expected_count, f'{key}: expected {expected_count} frames, got {len(frames)}'
        files = []
        for j, frame in enumerate(frames):
            expected_time = min(j / FPS, duration)
            assert abs(float(frame['animation_time']) - expected_time) < 0.0001, f'{key}: incomplete/nonuniform sample {j}'
            if 'actual_time' in frame:
                assert abs(float(frame['actual_time']) - expected_time) < 0.002, f'{key}: animation sample was not applied at {j}'
            filename = Path(frame['file']).resolve()
            assert filename.is_relative_to(PROJECT), 'Frame must be inside this project'
            with filename.open('rb') as stream:
                header = stream.read(24)
            assert len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n', 'Invalid PNG: ' + str(filename)
            size = struct.unpack('>II', header[16:24])
            assert min(size) >= 128 and size[0] % 2 == 0 and size[1] % 2 == 0, 'Invalid H264 dimensions'
            dimensions.add(size)
            files.append(filename)
        assert len({p.parent for p in files}) == 1, 'A clip sequence must share a source directory'
        source_asset = clip.get('source_asset') or clip['asset']
        source_name = str(source_asset).rsplit('/', 1)[-1].split('.', 1)[0]
        validated.append({
            'key': key, 'label': str(clip.get('label') or chr(65 + i)),
            'asset': clip['asset'], 'source_asset': source_asset, 'source_name': source_name,
            'duration_seconds': duration, 'files': files,
        })
    assert len(dimensions) == 1, 'Mixed source image dimensions'
    return report, validated, next(iter(dimensions))


def encode(bpy, clips, dest, dimensions, capture_path):
    width, height = dimensions
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.use_sequencer = True
    scene.render.use_compositing = False
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.sequencer_colorspace_settings.name = 'sRGB'
    editor = scene.sequence_editor_create()
    font = None
    for path in (Path('C:/Windows/Fonts/msyh.ttc'), Path('C:/Windows/Fonts/simhei.ttf')):
        if path.is_file():
            font = bpy.data.fonts.load(str(path))
            break
    assert font, 'A Chinese font is required for accurate captions'

    def label(name, text, channel, start, length, position, size):
        strip = editor.strips.new_effect(name, 'TEXT', channel, start, length=length)
        strip.text = text
        strip.font = font
        strip.font_size = size * width / 960
        strip.color = (1, 1, 1, 1)
        strip.location = position
        strip.use_shadow = True
        strip.shadow_color = (0, 0, 0, 1)
        strip.use_box = True
        strip.box_color = (.015, .022, .032, .82)
        strip.box_margin = .008
        return strip

    timeline = []
    next_frame = 1
    poster_frame = 1
    for clip_index, clip in enumerate(clips):
        for repeat, speed in ((1, '1.0x 原速'), (2, '0.5x 慢放')):
            ordered = [path for path in clip['files'] for _ in range(repeat)]
            motion_frames = len(ordered)
            ordered += [clip['files'][-1]] * HOLD_FRAMES
            section_name = f"{clip['key']}_{repeat}"
            strip = editor.strips.new_image(section_name, str(ordered[0]), 1, next_frame)
            for path in ordered[1:]:
                strip.elements.append(path.name)
            strip.frame_final_duration = len(ordered)
            strip.colorspace_settings.name = 'sRGB'
            label(section_name + '_title', clip['label'], 2, next_frame, len(ordered), (.25, .95), 25)
            label(section_name + '_speed', speed, 3, next_frame, len(ordered), (.86, .95), 22)
            label(section_name + '_source', clip['source_name'], 4, next_frame, len(ordered), (.5, .09), 21)
            label(section_name + '_note', '原包动作 · 新骨架重定向（41 骨骼）｜Unreal 动画预览',
                  5, next_frame, len(ordered), (.5, .045), 16)
            if clip_index == 0 and repeat == 1:
                poster_frame = next_frame + round((len(clip['files']) - 1) * .45)
            timeline.append({
                'key': clip['key'], 'label': clip['label'], 'source_asset': clip['source_asset'],
                'retargeted_asset': clip['asset'], 'source_duration_seconds': clip['duration_seconds'],
                'start_frame': next_frame, 'end_frame': next_frame + len(ordered) - 1,
                'motion_frames': motion_frames, 'endpoint_hold_frames': HOLD_FRAMES,
                'speed': 1.0 / repeat, 'source_frame_count': len(clip['files']),
            })
            next_frame += len(ordered)

    scene.frame_start = 1
    scene.frame_end = next_frame - 1
    scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.ffmpeg.audio_codec = 'NONE'
    scene.render.filepath = str(dest)
    bpy.ops.render.render(animation=True)
    assert dest.is_file() and dest.stat().st_size > 1000, 'No encoded video'

    # Decode the produced file independently through Blender's movie reader.
    decoded = editor.strips.new_movie('DecodedVerification', str(dest), 8, scene.frame_end + 10)
    decoded_meta = {'frames': decoded.frame_duration, 'fps': decoded.fps,
                    'width': decoded.elements[0].orig_width, 'height': decoded.elements[0].orig_height}
    assert decoded_meta['frames'] == scene.frame_end, 'Encoded video lost frames'
    assert abs(decoded_meta['fps'] - FPS) < .01, 'Encoded video FPS differs'
    assert (decoded_meta['width'], decoded_meta['height']) == dimensions, 'Encoded dimensions differ'
    editor.strips.remove(decoded)

    scene.frame_set(poster_frame)
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    poster = dest.with_suffix('.png')
    scene.render.filepath = str(poster)
    bpy.ops.render.render(write_still=True)
    assert poster.is_file(), 'Missing preview poster'
    report = {
        'capture': str(capture_path), 'output': str(dest), 'poster': str(poster),
        'frames': scene.frame_end, 'fps': FPS, 'duration_seconds': scene.frame_end / FPS,
        'width': width, 'height': height, 'sections': timeline,
        'bytes': dest.stat().st_size, 'decoded_video': decoded_meta,
        'checks': {'all_source_samples_shown': True, 'decoded_dimensions_fps_and_frames_match': True},
        'note': 'Complete Unreal samples, including final endpoint, shown once at 1x and twice at 0.5x. '
                'Each section adds 0.4 seconds of endpoint hold. No invented intermediate frames. '
                'AI and collision held for animation preview; not a manual gameplay or headset test.',
    }
    dest.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PACK_SLASH_VIDEO_ENCODED ' + json.dumps(report, ensure_ascii=True))
    return report


def main():
    args = arguments()
    capture_path = args.capture.resolve()
    _, clips, dimensions = load_capture(capture_path)
    out = args.output_dir.resolve()
    assert out.is_relative_to(DEFAULT_OUT.resolve()), 'Outputs must remain in PackSlashReview1104'
    if args.validate_only:
        print(json.dumps({'capture_validated': True, 'clips': [c['key'] for c in clips],
                          'dimensions': dimensions, 'source_frames': sum(len(c['files']) for c in clips)}))
        return
    plans = [(out / (clip['key'] + '_PackageSlash.mp4'), [clip]) for clip in clips]
    plans.append((out / 'PackSlashComparison.mp4', clips))
    for dest, _ in plans:
        for path in (dest, dest.with_suffix('.png'), dest.with_suffix('.json')):
            assert args.replace or not path.exists(), 'Output exists; pass --replace for generated previews: ' + str(path)
    manifest = out / 'EncodedComparison.json'
    assert args.replace or not manifest.exists(), 'Manifest exists; pass --replace'
    out.mkdir(parents=True, exist_ok=True)
    import bpy
    reports = [encode(bpy, selected, dest, dimensions, capture_path) for dest, selected in plans]
    manifest.write_text(json.dumps({'capture': str(capture_path), 'outputs': reports,
                                    'complete': True}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
