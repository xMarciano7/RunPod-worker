import base64
import tempfile
import os
import runpod
from faster_whisper import WhisperModel

model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

def handler(event):
    audio_b64 = event["input"]["audio_base64"]
    audio_bytes = base64.b64decode(audio_b64)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        audio_path = f.name

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

    os.remove(audio_path)

    return {
        "language": info.language,
        "words": words
    }

runpod.serverless.start({"handler": handler})
