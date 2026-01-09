import os
import json
import uuid
import subprocess
import requests
import boto3
from runpod.serverless import start

# =============================
# CONFIG
# =============================

TMP_DIR = "/tmp"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
)

# =============================
# UTILS
# =============================

def download_file(url, out_path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def upload_r2(local_path, key):
    s3.upload_file(local_path, R2_BUCKET, key)
    return f"{R2_ENDPOINT}/{R2_BUCKET}/{key}"

def run_cmd(cmd):
    subprocess.run(cmd, check=True)

# =============================
# MAIN HANDLER
# =============================

def handler(job):
    job_id = job["id"]
    data = job["input"]

    video_url = data["video_url"]

    work_id = str(uuid.uuid4())

    video_path = f"{TMP_DIR}/input_{work_id}.mp4"
    audio_path = f"{TMP_DIR}/audio_{work_id}.wav"
    whisper_json = f"{TMP_DIR}/whisper_{work_id}.json"
    ass_path = f"{TMP_DIR}/subs_{work_id}.ass"
    output_video = f"{TMP_DIR}/final_{work_id}.mp4"

    # =============================
    # 1. DOWNLOAD VIDEO
    # =============================
    download_file(video_url, video_path)

    # =============================
    # 2. EXTRACT AUDIO
    # =============================
    run_cmd([
        "ffmpeg", "-y",
        "-i", video_path,
        "-ac", "1",
        "-ar", "16000",
        audio_path
    ])

    # =============================
    # 3. TRANSCRIBE (NO CLI)
    # =============================
    from faster_whisper import WhisperModel

    model = WhisperModel(
        WHISPER_MODEL,
        device="cuda",
        compute_type="float16"
    )

    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True
    )

    words = []
    for seg in segments:
        for w in seg.words:
            words.append({
                "start": w.start,
                "end": w.end,
                "word": w.word
            })

    with open(whisper_json, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)

    # =============================
    # 4. BUILD ASS (FULL LENGTH)
    # =============================
    subprocess.run([
        "python",
        "handler_merge_ass.py",
        whisper_json,
        ass_path
    ], check=True)

    # =============================
    # 5. BURN SUBTITLES
    # =============================
    subprocess.run([
        "python",
        "handler_burn_final.py",
        video_path,
        ass_path,
        output_video
    ], check=True)

    # =============================
    # 6. UPLOAD RESULT
    # =============================
    r2_key = f"clips/{job_id}.mp4"
    final_url = upload_r2(output_video, r2_key)

    return {
        "status": "completed",
        "video_url": final_url
    }

# =============================
# START SERVERLESS
# =============================

start({"handler": handler})
