#!/usr/bin/env python3
"""Build the explainer video from real screenshots + generated narration.

Nothing here invents evidence:

* every app image comes from ``frontend/capture/capture.spec.ts``, which drives
  the real build in Chromium and saves what the app actually rendered;
* every word of narration is the text in this file, synthesised to audio and
  then timed against the images - the video is cut to the audio, never the
  other way round;
* the title, lower-third context lines and the closing card are drawn text on
  a plain background. They are labelled as such in ``DEMO_SCRIPT.md``.

Usage (from the repository root, after a capture run):

    .venv/bin/python scripts/build_video.py \
        --frames artifacts/video/frames \
        --audio  artifacts/video/audio \
        --out    artifacts/video/merchantshield-ai-explainer.mp4
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
FPS = 30
BG = (15, 23, 42)  # slate-900
FG = (241, 245, 249)  # slate-100
ACCENT = (56, 189, 248)  # sky-400
MUTED = (148, 163, 184)  # slate-400

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
FONT_REG = FONT_DIR / "DejaVuSans.ttf"
FONT_MONO = FONT_DIR / "DejaVuSansMono.ttf"


@dataclass(frozen=True)
class Segment:
    """One still on screen for a share of a scene's narration."""

    frame: str
    caption: str


@dataclass(frozen=True)
class Scene:
    audio: str
    title: str
    narration: str
    segments: tuple[Segment, ...]


SCENES: tuple[Scene, ...] = (
    Scene(
        audio="s01.mp3",
        narration="""A PayPal dispute is decided on evidence: a tracking number, a delivery confirmation, a message thread. By day forty-one, the tracking number was never attached to the PayPal order, and the buyer is already saying chargeback. Merchants lose these cases on paperwork they no longer have.""",
        title="The problem",
        segments=(
            Segment("__title__", "A dispute is decided on evidence. Evidence decays."),
            Segment("03-order-facts.png", "MS-2001 · 41 days old · no tracking on file"),
        ),
    ),
    Scene(
        audio="s02.mp3",
        narration="""MerchantShield AI scores every order, proposes the action that saves the evidence, and executes only after a human approves. Every record carries one of three labels: a real Sandbox response, generated locally, or a mock standing in for PayPal. There is no fourth label.""",
        title="What it is",
        segments=(
            Segment("01-overview.png", "Overview · demo on · paypal mock · llm none"),
            Segment("07-planner-proposals.png", "Proposals arrive PENDING · the agent cannot approve"),
        ),
    ),
    Scene(
        audio="s03.mp3",
        narration="""Twenty-five hand-written rules score each order from zero to one, and every point is attributed with a direction. No tracking costs twenty points. You can argue with a rule; you cannot argue with a number that appears from nowhere.""",
        title="Scoring an order",
        segments=(
            Segment("02-orders.png", "Orders, sorted by rule score"),
            Segment("04-risk-reasons.png", "Every point attributed, with a direction"),
        ),
    ),
    Scene(
        audio="s04.mp3",
        narration="""Beside it, a logistic-regression prototype, clearly labelled estimate, trained on synthetic data, with its metrics and two baselines on the Methodology page. Underneath, the seven documents this kind of case needs, which ones you hold, and what to do about each gap.""",
        title="Estimate and evidence",
        segments=(
            Segment("05-model-estimate.png", "ESTIMATE · trained on synthetic data"),
            Segment("06-evidence-checklist.png", "Seven documents · present or missing"),
            Segment("14-methodology.png", "Metrics and both baselines, on the Methodology page"),
        ),
    ),
    Scene(
        audio="s05.mp3",
        narration="""Ask the planner, and it proposes actions: attach this tracking number, message the buyer, flag the order. Everything arrives pending. The agent has no write access. Approve, then execute. The claim is a single conditional update, so two clicks cannot create two tracking numbers.""",
        title="Acting on it, safely",
        segments=(
            Segment("07-planner-proposals.png", "PENDING → APPROVED"),
            Segment("08-proposal-approved.png", "Approve, then execute"),
        ),
    ),
    Scene(
        audio="s06.mp3",
        narration="""A test fires eight concurrent executes and asserts exactly one claim, one external call and one audit row. And a timeout is not a failure. It is an unknown, and the app refuses a blind retry, because that is how duplicates happen.""",
        title="Once, and honestly unknown",
        segments=(
            Segment("09-proposal-executed.png", "EXECUTED · handled locally · SIMULATED"),
            Segment("13-audit.png", "One claim · one attempt · one audit row"),
        ),
    ),
    Scene(
        audio="s07.mp3",
        narration="""When the case does open, the packet is already assembled. The draft is a deterministic template without a key; with a Gemini key it is a model draft that must pass a hallucination guard. Every save is a new version. Submission is labelled simulated: no case is filed with PayPal.""",
        title="The dispute",
        segments=(
            Segment("12-dispute-packet.png", "Evidence packet, score and timeline"),
            Segment("12-dispute-packet.png", "Submission is SIMULATED and labelled"),
        ),
    ),
    Scene(
        audio="s08.mp3",
        narration="""Every state change is in an append-only audit log, with an actor and a source. The Methodology page prints the model's real numbers next to two baselines, and states what is not built: no production PayPal, no dispute filing, no carrier API, no training on PayPal data.""",
        title="Why you can trust it",
        segments=(
            Segment("13-audit.png", "Append-only audit log · actor and source on every row"),
            Segment("15-methodology-more.png", "Source labels and the rules the code holds itself to"),
            Segment("16-methodology-limits.png", "What is not built"),
        ),
    ),
    Scene(
        audio="s09.mp3",
        narration="""For a small merchant, that is the difference between arguing a case and losing it by default. Evidence collected on day one is worth more than any percentage a dashboard could invent. And when the app does not know something, it says so.""",
        title="What it changes",
        segments=(
            Segment("11-walkthrough-story.png", "The whole story, nine stages, each labelled"),
            Segment("16-methodology-limits.png", "When the app does not know, it says so"),
        ),
    ),
    Scene(
        audio="s10.mp3",
        narration="""Two hundred and fifteen backend tests, thirty-two browser tests and sixteen mutation checks run from one command. If a guarantee is removed, a test fails. PayPal Sandbox only. Nothing here moves real money.""",
        title="Where it stands",
        segments=(
            Segment("02-orders.png", "215 backend tests · 32 browser tests · 16 mutation checks"),
            Segment("__outro__", "PayPal Sandbox only. Nothing here moves real money."),
        ),
    ),
)


# --------------------------------------------------------------------- helpers
def run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(f"ffmpeg failed ({proc.returncode}): {' '.join(args[:6])} ...")


def ffprobe_duration(ffmpeg: str, path: Path) -> float:
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = stamp.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise SystemExit(f"could not read duration of {path}")


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if fnt.getlength(candidate) <= max_width or current == "":
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def title_card(text: str, out: Path, kicker: str = "") -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    f_big = font(FONT_BOLD, 96)
    f_kick = font(FONT_MONO, 34)
    lines = wrap(text, f_big, WIDTH - 360)
    line_height = 132
    total = len(lines) * line_height
    y = (HEIGHT - total) // 2
    if kicker:
        draw.text((180, y - 120), kicker.upper(), font=f_kick, fill=MUTED)
    for line in lines:
        draw.text((180, y), line, font=f_big, fill=FG)
        y += line_height
    draw.rectangle([180, y + 40, 180 + 160, y + 48], fill=ACCENT)
    img.save(out)


def app_frame(src: Path, caption: str, kicker: str, out: Path) -> None:
    """Compose a real 1500x900 screenshot into a 1920x1080 frame with a caption."""
    shot = Image.open(src).convert("RGB")
    caption_h = 86
    avail_w = WIDTH - 96
    avail_h = HEIGHT - caption_h - 120
    scale = min(avail_w / shot.width, avail_h / shot.height)
    shot = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)

    img = Image.new("RGB", (WIDTH, HEIGHT), (226, 232, 240))
    top = 96
    img.paste(shot, ((WIDTH - shot.width) // 2, top))
    draw = ImageDraw.Draw(img)
    draw.text((24, 26), kicker.upper(), font=font(FONT_MONO, 30), fill=(51, 65, 85))
    band_top = top + shot.height
    img.paste(Image.new("RGB", (WIDTH, HEIGHT - band_top), BG), (0, band_top))
    draw.text((24, band_top + 22), caption, font=font(FONT_REG, 30), fill=FG)
    img.save(out)


def build_segment(
    ffmpeg: str, frame: Path, duration: float, index: int, workdir: Path, zoom_in: bool
) -> Path:
    """One still, slowly zoomed, exactly `duration` seconds long."""
    out = workdir / f"seg-{index:03d}.mp4"
    frames = max(2, round(duration * FPS))
    if zoom_in:
        zoom = f"zoompan=z='min(1.06,1+0.00035*on)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS}"
    else:
        zoom = f"zoompan=z='max(1.0,1.06-0.00035*on)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS}"
    run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(frame),
            "-t", f"{duration:.3f}",
            "-vf", f"{zoom},format=yuv420p",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-tune", "stillimage",
            str(out),
        ]
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()

    ffmpeg = shutil.which(args.ffmpeg) or args.ffmpeg
    work = Path(tempfile.mkdtemp(prefix="msvideo-"))
    missing = [s.frame for scene in SCENES for s in scene.segments if not s.frame.startswith("__")]
    missing += [scene.audio for scene in SCENES]
    absent = [
        name
        for name in missing
        if not (args.frames / name).exists() and not (args.audio / name).exists()
    ]
    if absent:
        raise SystemExit(f"missing inputs: {sorted(set(absent))}")

    timeline: list[dict[str, object]] = []
    concat_list = work / "concat.txt"
    lines: list[str] = []
    index = 0
    cursor = 0.0

    for scene_no, scene in enumerate(SCENES, start=1):
        audio_path = args.audio / scene.audio
        total = ffprobe_duration(ffmpeg, audio_path)
        shares = [total / len(scene.segments)] * len(scene.segments)
        # give the last still in a scene any rounding remainder
        shares[-1] = total - sum(shares[:-1])

        for seg_no, (segment, share) in enumerate(zip(scene.segments, shares), start=1):
            if segment.frame == "__title__":
                frame_path = work / f"title-{index:03d}.png"
                title_card(segment.caption, frame_path, kicker=scene.title)
            elif segment.frame == "__outro__":
                frame_path = work / f"outro-{index:03d}.png"
                title_card("github.com/ShoryaPratapSinghChandrawat/MerchantShield-AI", frame_path, kicker="try it")
            else:
                frame_path = work / f"frame-{index:03d}.png"
                app_frame(
                    args.frames / segment.frame,
                    segment.caption,
                    kicker=scene.title,
                    out=frame_path,
                )
            seg = build_segment(ffmpeg, frame_path, share, index, work, zoom_in=index % 2 == 0)
            lines.append(f"file '{seg.as_posix()}'")
            timeline.append(
                {
                    "scene": scene_no,
                    "scene_title": scene.title,
                    "shot": seg_no,
                    "source_frame": segment.frame,
                    "caption": segment.caption,
                    "start": round(cursor, 2),
                    "duration": round(share, 2),
                }
            )
            cursor += share
            index += 1

    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- audio: every narration clip padded or trimmed to its scene's length
    audio_parts: list[str] = []
    audio_inputs: list[str] = []
    for scene_no, scene in enumerate(SCENES):
        audio_inputs += ["-i", str(args.audio / scene.audio)]
    filter_parts = []
    for scene_no, scene in enumerate(SCENES):
        total = ffprobe_duration(ffmpeg, args.audio / scene.audio)
        filter_parts.append(
            f"[{scene_no}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad,atrim=0:{total:.3f},asetpts=N/SR/TB[a{scene_no}]"
        )
    concat_inputs = "".join(f"[a{i}]" for i in range(len(SCENES)))
    filter_parts.append(f"{concat_inputs}concat=n={len(SCENES)}:v=0:a=1[out]")
    narration = work / "narration.wav"
    run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *audio_inputs,
         "-filter_complex", ";".join(filter_parts), "-map", "[out]", str(narration)]
    )

    video_only = work / "video-only.mp4"
    run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(video_only)]
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video_only), "-i", str(narration),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ac", "2",
         "-shortest", "-movflags", "+faststart", str(args.out)]
    )

    duration = ffprobe_duration(ffmpeg, args.out)
    words = sum(len(scene.narration.split()) for scene in SCENES)
    manifest = {
        "output": str(args.out),
        "narration_words": words,
        "narration_transcript": [
            {"scene": i, "title": scene.title, "audio": scene.audio, "text": scene.narration}
            for i, scene in enumerate(SCENES, start=1)
        ],
        "duration_seconds": round(duration, 2),
        "duration_mmss": f"{int(duration // 60)}:{int(duration % 60):02d}",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "shots": timeline,
        "note": (
            "App frames are real screenshots of this build (frontend/capture/capture.spec.ts). "
            "Narration is synthesised text, and this transcript is the text that was spoken. "
            "Title and closing cards are drawn text, not app footage."
        ),
    }
    (args.out.parent / "video-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    print(json.dumps({k: manifest[k] for k in ("output", "duration_seconds", "duration_mmss")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
