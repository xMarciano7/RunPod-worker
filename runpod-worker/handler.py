from faster_whisper import WhisperModel
import os
import subprocess
import tempfile
import base64
import json
import runpod

WHISPER_MODEL = "medium"

def run(cmd):
    subprocess.run(cmd, check=True)

def download(video_url, out):
    run(["yt-dlp", "-f", "mp4/best", "-o", out, video_url])

def cut_clip(inp, out):
    run([
        "ffmpeg", "-y",
        "-i", inp,
        "-t", "75",
        "-c", "copy",
        out
    ])

def extract_audio(video, audio):
    run([
        "ffmpeg", "-y",
        "-i", video,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        audio
    ])

def whisper(audio_path, out_json):
    model = WhisperModel(WHISPER_MODEL, compute_type="int8")
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    data = {"segments": []}

    for seg in segments:
        data["segments"].append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "words": [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end
                } for w in (seg.words or [])
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
            s = w["start"]
            e = w["end"]
            t = w["word"]
            f.write(
                f"Dialogue: 0,0:{int(s//60):02}:{s%60:05.2f},0:{int(e//60):02}:{e%60:05.2f},Default,,0,0,0,,{t}\n"
            )

def burn(video, ass, out):
    run([
        "ffmpeg", "-y",
        "-i", video,
        "-vf", f"ass={ass}",
        "-c:a", "copy",
        out
    ])

def handler(job):
    video_url = job["input"]["video_url"]

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

        b64 = base64.b64encode(open(final, "rb").read()).decode()

        return {
            "video_base64": b64
        }

runpod.serverless.start({"handler": handler})
