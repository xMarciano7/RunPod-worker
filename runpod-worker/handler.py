import os
import subprocess
import tempfile
import traceback
import uuid

import boto3
from runpod.serverless import start
from faster_whisper import WhisperModel


# ================= CONFIG =================
WHISPER_MODEL = "tiny"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
FONT_NAME = "Liberation Sans"
MAX_DURATION = "75"

R2_BUCKET = os.getenv("R2_BUCKET")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")
# =========================================


def run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"CMD FAILED:\n{' '.join(cmd)}\nSTDERR:\n{p.stderr}"
        )
    return p.stdout


def ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def generate_ass(words, path):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},130,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,1,0,1,6,0,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for w in words:
        lines.append(
            f"Dialogue: 0,{ts(w['start'])},{ts(w['end'])},Default,,0,0,0,,{w['word'].upper()}"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines))


def download_video(url, output_path):
    if "youtube.com" in url or "youtu.be" in url:
        run([
            "yt-dlp",
            "-f", "mp4",
            "-o", output_path,
            url
        ])
    else:
        run([
            "curl",
            "-L",
            "--fail",
            url,
            "-o",
            output_path
        ])


def handler(event):
    try:
        video_url = event["input"]["video_url"]
        print("VIDEO URL:", video_url)

        tmp = tempfile.mkdtemp()
        input_mp4 = os.path.join(tmp, "input.mp4")
        audio_wav = os.path.join(tmp, "audio.wav")
        subs_ass = os.path.join(tmp, "subs.ass")
        output_mp4 = os.path.join(tmp, "output.mp4")

        # DOWNLOAD
        download_video(video_url, input_mp4)

        # VALIDATE VIDEO
        run(["ffprobe", "-v", "error", "-show_format", input_mp4])

        # AUDIO (RECORTADO)
        run([
            "ffmpeg", "-y",
            "-i", input_mp4,
            "-t", MAX_DURATION,
            "-ac", "1",
            "-ar", "16000",
            audio_wav
        ])

        # WHISPER
        model = WhisperModel(
            WHISPER_MODEL,
            device=DEVICE,
            compute_type=COMPUTE_TYPE
        )

        segments, _ = model.transcribe(audio_wav, word_timestamps=True)

        words = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    words.append({
                        "start": w.start,
                        "end": w.end,
                        "word": w.word
                    })

        if not words:
            raise RuntimeError("NO WORDS FROM WHISPER")

        # ASS
        generate_ass(words, subs_ass)

        # BURN
        run([
            "ffmpeg", "-y",
            "-i", input_mp4,
            "-vf", f"ass={subs_ass}",
            "-c:a", "copy",
            output_mp4
        ])

        # UPLOAD R2
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto"
        )

        key = f"clips/{uuid.uuid4()}.mp4"
        s3.upload_file(
            output_mp4,
            R2_BUCKET,
            key,
            ExtraArgs={"ContentType": "video/mp4"}
        )

        return {"video_url": f"{R2_PUBLIC_BASE}/{key}"}

    except Exception as e:
        print("FATAL ERROR:", str(e))
        print(traceback.format_exc())
        raise e


start({"handler": handler})
