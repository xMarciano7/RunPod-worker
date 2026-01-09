import os
import time
import json
import uuid
import subprocess
import requests
from runpod.serverless import start

TMP = "/tmp"

def run(cmd):
    subprocess.run(cmd, check=True)

def sh(cmd):
    return subprocess.check_output(cmd).decode()

def download_video(url, out_mp4):
    tmp = out_mp4 + ".tmp"

    if "youtube.com" in url or "youtu.be" in url:
        run([
            "yt-dlp",
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "-o", tmp,
            url
        ])
    else:
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

    # esperar a que el archivo sea estable
    for _ in range(10):
        if os.path.exists(tmp) and os.path.getsize(tmp) > 1024 * 500:
            break
        time.sleep(1)

    if not os.path.exists(tmp) or os.path.getsize(tmp) < 1024 * 500:
        raise RuntimeError("download failed or empty")

    # validar MP4 real
    run([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        tmp
    ])

    os.rename(tmp, out_mp4)



def extract_audio(mp4, wav):
    run([
        "ffmpeg", "-y",
        "-i", mp4,
        "-ac", "1",
        "-ar", "16000",
        wav
    ])

def whisper(audio, out_json):
    run([
        "python", "-m", "faster_whisper",
        audio,
        "--model", "medium",
        "--output_format", "json",
        "--output_dir", os.path.dirname(out_json)
    ])

def json_to_ass(json_path, ass_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BorderStyle,Outline,Alignment\n")
        f.write("Style: Default,Poppins ExtraBold,130,&H00FFFFFF,&H00000000,1,4,2\n\n")
        f.write("[Events]\n")
        f.write("Format: Start,End,Style,Text\n")

        for s in data["segments"]:
            start = s["start"]
            end = s["end"]
            text = s["text"].strip().replace("\n", " ")
            f.write(
                f"Dialogue: 0,{sec(start)},{sec(end)},Default,{text}\n"
            )

def sec(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def burn(mp4, ass, out):
    run([
        "ffmpeg", "-y",
        "-i", mp4,
        "-vf", f"ass={ass}",
        "-c:a", "copy",
        out
    ])

def handler(job):
    url = job["input"].get("video_url")
    if not url:
        raise RuntimeError("video_url missing")

    jid = str(uuid.uuid4())

    mp4 = f"{TMP}/input_{jid}.mp4"
    wav = f"{TMP}/audio_{jid}.wav"
    jsn = f"{TMP}/audio_{jid}.json"
    ass = f"{TMP}/subs_{jid}.ass"
    out = f"{TMP}/clip_{jid}.mp4"

    download_video(url, mp4)
    extract_audio(mp4, wav)
    whisper(wav, jsn)
    json_to_ass(jsn, ass)
    burn(mp4, ass, out)

    return {
        "status": "ok",
        "local_path": out
    }

start({"handler": handler})
