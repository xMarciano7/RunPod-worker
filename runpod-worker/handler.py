import runpod
import tempfile
import subprocess
import os
import base64
from faster_whisper import WhisperModel

model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

def handler(event):
    # 1. Recibir vídeo en base64
    video_b64 = event["input"]["video_base64"]
    video_bytes = base64.b64decode(video_b64)

    # 2. Guardar vídeo temporal
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        video_path = vf.name

    audio_path = video_path.replace(".mp4", ".wav")
    output_video_path = video_path.replace(".mp4", "_out.mp4")

    # 3. Extraer audio (FFmpeg)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            audio_path
        ],
        check=True
    )

    # 4. Whisper
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

    # 5. (TEMPORAL) copiar vídeo como resultado final
    # 👉 aquí luego quemas subtítulos con ASS
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_video_path],
        check=True
    )

    # 6. Devolver vídeo final en base64
    with open(output_video_path, "rb") as f:
        output_b64 = base64.b64encode(f.read()).decode("utf-8")

    # 7. Limpieza
    os.remove(video_path)
    os.remove(audio_path)
    os.remove(output_video_path)

    return {
        "language": info.language,
        "words": words,
        "video_base64": output_b64
    }

runpod.serverless.start({"handler": handler})
