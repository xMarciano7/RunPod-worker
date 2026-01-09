#!/usr/bin/env python3
import sys
import subprocess
import os

def run(cmd):
    subprocess.run(cmd, check=True)

def main():
    if len(sys.argv) != 4:
        raise RuntimeError(
            "Usage: handler_burn_final.py <input_video.mp4> <subtitles.ass> <output_video.mp4>"
        )

    input_video = os.path.abspath(sys.argv[1])
    input_ass = os.path.abspath(sys.argv[2])
    output_video = os.path.abspath(sys.argv[3])

    if not os.path.isfile(input_video):
        raise RuntimeError(f"Input video not found: {input_video}")
    if not os.path.isfile(input_ass):
        raise RuntimeError(f"ASS file not found: {input_ass}")

    out_dir = os.path.dirname(output_video)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", f"ass={input_ass}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.1",
        "-movflags", "+faststart",
        "-c:a", "copy",
        output_video
    ])

    print("[OK] Burn final completado:", output_video)

if __name__ == "__main__":
    main()
