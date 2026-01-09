import os
import subprocess
import tempfile
import requests
import runpod

WHISPER_MODEL = "medium"

def download_video_http(video_url: str, dst_path: str):
    r = requests.get(video_url, stream=True, timeout=60)
    r.raise_for_status()

    with open(dst_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    if not os.path.exists(dst_path) or os.path.getsize(dst_path) < 1024 * 100:
        raise RuntimeError("Downloaded video is empty or invalid")

def download_video_ytdlp(video_url: str, dst_path: str):
    cmd = [
        "yt-dlp",
        "-f", "mp4/best",
        "-o", dst_path,
        video_url
    ]
    subprocess.run(cmd, check=True)

    if not os.path.exists(dst_path) or os.path.getsize(dst_path) < 1024 * 100:
        raise RuntimeError("yt-dlp download failed")

def validate_video(path: str):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def extract_audio(video_path: str, audio_path: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        audio_path
    ]
    subprocess.run(cmd, check=True)

def run_whisper(audio_path: str):
    cmd = [
        "faster-whisper",
        audio_path,
        "--model", WHISPER_MODEL,
        "--output_format", "json"
    ]
    subprocess.run(cmd, check=True)

def handler(job):
    try:
        video_url = job["input"].get("video_url")
        if not video_url:
            raise ValueError("Missing video_url")

        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "input.mp4")
            audio_path = os.path.join(tmp, "audio.wav")

            # YouTube / streaming → yt-dlp
            if "youtube.com" in video_url or "youtu.be" in video_url:
                download_video_ytdlp(video_url, video_path)
            else:
                # intenta HTTP normal primero
                try:
                    download_video_http(video_url, video_path)
                except Exception:
                    # fallback a yt-dlp para cualquier URL rara
                    download_video_ytdlp(video_url, video_path)

            validate_video(video_path)
            extract_audio(video_path, audio_path)
            run_whisper(audio_path)

        return {"status": "ok"}

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

runpod.serverless.start({"handler": handler})
