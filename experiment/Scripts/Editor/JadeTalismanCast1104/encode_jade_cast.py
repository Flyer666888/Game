"""Encode timestamped Unreal screenshots as an H.264 attack demo with Blender 5.2."""

import argparse
from bisect import bisect_left
from itertools import groupby
import json
import math
from pathlib import Path
import struct
import sys

import bpy


PROJECT = Path(__file__).resolve().parents[3]
OUTPUT = PROJECT / "Docs/Gameplay/JadeTalismanCast1104"
FPS = 24


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, default=OUTPUT / "Capture.json")
    parser.add_argument("--output", type=Path, default=OUTPUT / "JadeTalismanCastDemo.mp4")
    parser.add_argument("--poster-frame", type=int)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def read_capture(path):
    capture = json.loads(path.read_text(encoding="utf-8-sig"))
    if capture["state"] != "passed":
        raise ValueError("Capture did not pass")

    samples = []
    sizes = set()
    for row in capture["frames"]:
        source = (path.parent / row["file"]).resolve()
        timestamp = float(row["t"])
        if not source.is_relative_to(PROJECT) or not math.isfinite(timestamp):
            raise ValueError(f"Invalid sample {row}")
        with source.open("rb") as png:
            header = png.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG: {source}")
        sizes.add(struct.unpack(">II", header[16:24]))
        samples.append({**row, "t": timestamp, "file": source})

    if len(samples) < 2 or len(sizes) != 1:
        raise ValueError("Expected at least two equally sized screenshot samples")
    width, height = sizes.pop()
    if width % 2 or height % 2:
        raise ValueError("H.264 frame dimensions must be even")
    if any(a["t"] > b["t"] for a, b in zip(samples, samples[1:])):
        raise ValueError("Capture timestamps must be chronological")
    if samples[-1]["t"] <= samples[0]["t"]:
        raise ValueError("Capture must contain positive elapsed game time")
    return samples, width, height


def resample(samples):
    times = [sample["t"] for sample in samples]
    frame_count = round((times[-1] - times[0]) * FPS) + 1
    result = []
    for frame in range(frame_count):
        target = times[0] + frame / FPS
        right = bisect_left(times, target)
        if right == 0:
            index = 0
        elif right == len(times) or target - times[right - 1] <= times[right] - target:
            index = right - 1
        else:
            index = right
        result.append(samples[index])
    return result


def phase_labels(frames):
    health = frames[0].get("hp")
    show_impact_until = -1
    labels = []
    for index, sample in enumerate(frames):
        current_health = sample.get("hp")
        if health is not None and current_health is not None and current_health < health:
            show_impact_until = index + round(0.5 * FPS)
        health = current_health
        if index < show_impact_until:
            labels.append("命中玩家")
        elif sample.get("projectiles") or sample.get("phase") == "flight":
            labels.append("金色光球")
        elif sample.get("phase") == "windup" or any(
            "TELEGRAPH" in str(state).upper() for state in sample.get("states", [])
        ):
            labels.append("悬符蓄力")
        else:
            labels.append("")
    return labels


def encode(samples, width, height, destination, poster_override):
    frames = resample(samples)
    phases = phase_labels(frames)
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
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.sequencer_colorspace_settings.name = "sRGB"
    scene.frame_start = 1
    scene.frame_end = len(frames)
    editor = scene.sequence_editor_create()
    font = bpy.data.fonts.load("C:/Windows/Fonts/msyh.ttc")

    def label(name, content, channel, start, length, location, size):
        strip = editor.strips.new_effect(name, "TEXT", channel, start, length=length)
        strip.text = content
        strip.font = font
        strip.font_size = size * width / 960
        strip.location = location
        strip.color = (0.97, 0.98, 1.0, 1.0)
        strip.use_box = True
        strip.box_color = (0.025, 0.04, 0.06, 0.82)
        strip.box_margin = 0.009

    start = 1
    for _, group in groupby(frames, key=lambda sample: sample["file"].parent):
        paths = [sample["file"] for sample in group]
        strip = editor.strips.new_image(f"Unreal capture {start}", str(paths[0]), 1, start)
        for path in paths[1:]:
            strip.elements.append(path.name)
        strip.frame_final_duration = len(paths)
        strip.colorspace_settings.name = "sRGB"
        start += len(paths)

    label("Title", "R01 · 青玉鎏金符", 2, 1, len(frames), (0.14, 0.94), 21)
    start = 1
    for phase, group in groupby(phases):
        length = sum(1 for _ in group)
        if phase:
            label(phase, phase, 3, start, length, (0.89, 0.94), 20)
        start += length

    flight_frames = [i for i, phase in enumerate(phases, 1) if phase == "金色光球"]
    poster_index = poster_override or (
        flight_frames[len(flight_frames) // 2] if flight_frames else len(frames) // 2 + 1
    )
    if not 1 <= poster_index <= len(frames):
        raise ValueError("Poster frame is outside the video")

    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(destination)
    bpy.ops.render.render(animation=True)
    if not destination.is_file() or destination.stat().st_size < 1000:
        raise RuntimeError("The encoder did not write a video")

    decoded = editor.strips.new_movie("Verify encoded video", str(destination), 8, scene.frame_end + 10)
    dimensions = (decoded.elements[0].orig_width, decoded.elements[0].orig_height)
    if decoded.frame_duration != len(frames) or dimensions != (width, height) or abs(decoded.fps - FPS) > 0.01:
        raise RuntimeError("The encoded video does not match the planned dimensions, frame count, or rate")
    editor.strips.remove(decoded)

    scene.frame_set(poster_index)
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    poster = destination.with_suffix(".png")
    scene.render.filepath = str(poster)
    bpy.ops.render.render(write_still=True)

    metadata = {
        "video": str(destination),
        "poster": str(poster),
        "poster_frame": poster_index,
        "poster_source": str(frames[poster_index - 1]["file"]),
        "width": width,
        "height": height,
        "fps": FPS,
        "frames": len(frames),
        "duration_seconds": len(frames) / FPS,
        "game_time_span": samples[-1]["t"] - samples[0]["t"],
        "source_frames": len(samples),
        "flight_frame_count": len(flight_frames),
        "impact_frame_count": phases.count("命中玩家"),
    }
    destination.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RANGED_VIDEO_ENCODED " + json.dumps(metadata, ensure_ascii=True))


if __name__ == "__main__":
    args = arguments()
    output = args.output.resolve()
    if not output.is_relative_to(OUTPUT) or output.suffix.lower() != ".mp4":
        raise ValueError("Output must be a video inside the ranged demo folder")
    encode(*read_capture(args.capture.resolve()), output, args.poster_frame)

