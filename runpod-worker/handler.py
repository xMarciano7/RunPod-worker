from faster_whisper import WhisperModel
import os
import subprocess
import tempfile
import json
import runpod
import boto3
from botocore.client import Config

WHISPER_MODEL = "medium"

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY = os.environ["R2_ACCESS_KEY"]
R2_SECRET_KEY = os.environ["R2_SECRET_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]
R2_PUBLIC_BASE = os.environ["R2_PUBLIC_BASE"]

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

def run(cmd):
    subprocess.run(cmd, check=True)

def download(url, out):
    run(["yt-dlp", "-f", "mp4/best", "-o", out, url])

def cut_clip(inp, out):
    run(["ffmpeg", "-y", "-i", inp, "-t", "75", "-c", "copy", out])

def extract_audio(video, audio):
    run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", audio])

def whisper(audio_path, out_json):
    model = WhisperModel(WHISPER_MODEL, compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    data = {"segments": []}
    for seg in segments:
        data["segments"].append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "words": [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in (seg.words or [])
            ]
        })

    with open(out_json, "w", encoding="utf8") as f:
        json.dump(data, f)

def make_ass(words, ass):
    with open(ass, "w", encoding="utf8") as f:
        f.write("""[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Style: Default,Poppins ExtraBold,80,&H00FFFFFF,&H00000000,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,6,0,2,10,10,40,1

[Events]
""")
        for w in words:
            s, e, t = w["start"], w["end"], w["word"]
            f.write(
                f"Dialogue: 0,0:{int(s//60):02}:{s%60:05.2f},0:{int(e//60):02}:{e%60:05.2f},Default,,0,0,0,,{t}\n"
            )

def burn(video, ass, out):
    run(["ffmpeg", "-y", "-i", video, "-vf", f"ass={ass}", "-c:a", "copy", out])

def upload_r2(local_path, key):
    s3.upload_file(local_path, R2_BUCKET, key)
    return f"{R2_PUBLIC_BASE}/{key}"

def handler(job):
    video_url = job["input"]["video_url"]
    job_id = job["id"]

    with tempfile.TemporaryDirectory() as tmp:
        raw = f"{tmp}/raw.mp4"
        clip = f"{tmp}/clip.mp4"
        audio = f"{tmp}/audio.wav"
        ass = f"{tmp}/sub.ass"
        final = f"{tmp}/final.mp4"
        transcript = f"{tmp}/audio.json"

        download(video_url, raw)
        cut_clip(raw, clip)
        extract_audio(clip, audio)
        whisper(audio, transcript)

        data = json.load(open(transcript))
        words = data["segments"][0]["words"] if data["segments"] else []
        make_ass(words, ass)
        burn(clip, ass, final)

        key = f"clips/{job_id}.mp4"
        url = upload_r2(final, key)

        return {"video_url": url}

runpod.serverless.start({"handler": handler})
