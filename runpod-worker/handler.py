import os
import subprocess
import tempfile
import traceback
import uuid

import boto3
from runpod.serverless import start
from faster_whisper import WhisperModel


# ================= CONFIG =================
WHISPER_MODEL = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
MAX_DURATION = "75"

R2_BUCKET = os.getenv("R2_BUCKET")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")
# =========================================


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"CMD FAILED:\n{' '.join(cmd)}\nSTDERR:\n{p.stderr}")
    return p.stdout


def ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_color(hex_color: str):
    # #RRGGBB -> &HAABBGGRR
    hex_color = hex_color.lstrip("#")
    r = hex_color[0:2]
    g = hex_color[2:4]
    b = hex_color[4:6]
    return f"&H00{b}{g}{r}"


def ass_alignment(alignment: str):
    # ASS:
    # 1 bottom-left | 2 bottom-center | 3 bottom-right
    if alignment == "left":
        return 1
    if alignment == "right":
        return 3
    return 2  # center


def generate_ass(words, preset, path):
    font = preset.get("font", "Poppins")
    font_size = int(preset.get("fontSize", 96))

    text_color = ass_color(preset.get("color", "#FFFFFF"))
    outline_color = ass_color(preset.get("outlineColor", "#000000"))
    outline_size = int(preset.get("outlineThickness", 0))

    alignment = preset.get("alignment", "center")
    ass_align = ass_alignment(alignment)

    # Vertical position (% → MarginV)
    vertical_pct = int(preset.get("position", 50))
    play_res_y = 1920
    margin_v = int((100 - vertical_pct) / 100 * play_res_y)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{text_color},{text_color},{outline_color},&H00000000,1,0,1,{outline_size},0,{ass_align},60,60,{margin_v},1

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
        run(["yt-dlp", "-f", "mp4", "-o", output_path, url])
    else:
        run(["curl", "-L", "--fail", url, "-o", output_path])


def handler(event):
    try:
        data = event["input"]

        video_url = data["video_url"]
        preset = data.get("subtitle_preset", {})

        tmp = tempfile.mkdtemp()
        input_mp4 = os.path.join(tmp, "input.mp4")
        audio_wav = os.path.join(tmp, "audio.wav")
        subs_ass = os.path.join(tmp, "subs.ass")
        output_mp4 = os.path.join(tmp, "output.mp4")

        download_video(video_url, input_mp4)

        # AUDIO
        run([
            "ffmpeg", "-y",
            "-i", input_mp4,
            "-t", MAX_DURATION,
            "-ac", "1",
            "-ar", "16000",
            audio_wav
        ])

        # WHISPER
        model = WhisperModel(WHISPER_MODEL, device=DEVICE, compute_type=COMPUTE_TYPE)
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

        generate_ass(words, preset, subs_ass)

        # VIDEO FINAL 9:16 + ASS
        run([
            "ffmpeg", "-y",
            "-i", input_mp4,
            "-t", MAX_DURATION,
            "-filter_complex",
            (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,boxblur=20:1[bg];"
                "[0:v]scale=1080:-1:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,ass=" + subs_ass
            ),
            "-c:a", "copy",
            output_mp4
        ])

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

        return {
            "status": "ok",
            "video_url": f"{R2_PUBLIC_BASE}/{key}"
        }

    except Exception:
        print(traceback.format_exc())
        raise


start({"handler": handler})
