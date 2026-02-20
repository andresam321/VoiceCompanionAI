# device/wake_agent.py
from __future__ import annotations

import os
import time
import uuid
import wave
import tempfile
from pathlib import Path

import requests
import webrtcvad
import pyaudio

from openwakeword.model import Model

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-device-token-001")
HEADERS_BASE = {"X-Device-Token": DEVICE_TOKEN}

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 20
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
FRAME_BYTES = FRAME_SAMPLES * 2  # int16

POLL_INTERVAL = 0.6
MAX_POLLS = 80
HTTP_TIMEOUT = 10

ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "device/assets"))
BEEP_WAV = ASSETS_DIR / "beep.wav"
THINKING_WAV = ASSETS_DIR / "thinking.wav"
FALLBACK_WAV = ASSETS_DIR / "fallback.wav"

# Wake words you care about.
# Start with names, not generic "hey".
WAKE_NAMES = ["Pal"]

# VAD tuning
VAD_AGGRESSIVENESS = 2  # 0-3
MAX_RECORD_SECONDS = 6
SILENCE_STOP_MS = 700


def req(method: str, url: str, **kwargs) -> requests.Response:
    return requests.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)


def play_local_wav(path: Path) -> None:
    if not path.exists():
        return
    try:
        import sounddevice as sd
        import soundfile as sf
        audio, sr = sf.read(str(path))
        sd.play(audio, sr)
        sd.wait()
    except Exception:
        return


def upload_audio(audio_path: str, trace_id: str) -> str:
    url = f"{API_BASE}/v1/voice-interactions"
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}
    with open(audio_path, "rb") as f:
        resp = req("POST", url, headers=headers, files={"audio": ("audio.wav", f, "audio/wav")})
    resp.raise_for_status()
    return resp.json()["interaction_id"]


def poll_interaction(interaction_id: str, trace_id: str) -> dict:
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}

    by_id = f"{API_BASE}/v1/interactions/{interaction_id}"
    latest = f"{API_BASE}/v1/interactions/latest"

    for _ in range(MAX_POLLS):
        r = req("GET", by_id, headers=headers)
        if r.status_code == 404:
            r = req("GET", latest, headers=headers)

        if r.status_code < 400:
            data = r.json()
            if data.get("status") in {"complete", "failed"}:
                return data

        time.sleep(POLL_INTERVAL)

    return {}


def fetch_audio(interaction_id: str, trace_id: str) -> bytes | None:
    url = f"{API_BASE}/v1/audio/{interaction_id}.wav"
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}
    r = req("GET", url, headers=headers)
    if r.status_code == 200 and r.content:
        return r.content
    return None


def play_wav_bytes(wav_bytes: bytes) -> bool:
    try:
        import sounddevice as sd
        import soundfile as sf
        import io
        audio, sr = sf.read(io.BytesIO(wav_bytes))
        sd.play(audio, sr)
        sd.wait()
        return True
    except Exception:
        return False


def write_wav_file(frames: list[bytes]) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))
    return tmp.name


def record_until_silence(stream: pyaudio.Stream) -> str:
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    frames: list[bytes] = []
    silence_ms = 0
    max_frames = int(MAX_RECORD_SECONDS * 1000 / FRAME_MS)

    for _ in range(max_frames):
        frame = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
        frames.append(frame)

        is_speech = vad.is_speech(frame, SAMPLE_RATE)
        if is_speech:
            silence_ms = 0
        else:
            silence_ms += FRAME_MS
            if silence_ms >= SILENCE_STOP_MS and len(frames) > int(0.5 * 1000 / FRAME_MS):
                break

    return write_wav_file(frames)


def main() -> None:
    # openWakeWord model, you can load custom wake word models later.
    # For now, we’ll use built-in keyword spotting by scoring text-like labels.
    model = Model()  # default pretrained

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=FRAME_SAMPLES,
    )

    try:
        while True:
            # 1) Listen for wake word
            frame = stream.read(FRAME_SAMPLES, exception_on_overflow=False)

            # openWakeWord expects numpy int16 frames
            import numpy as np
            audio_i16 = np.frombuffer(frame, dtype=np.int16)

            preds = model.predict(audio_i16)

            # preds is a dict of keyword->score depending on model config
            # We'll do a simple heuristic: if any known name appears as a key and score high
            triggered = False
            triggered_key = None

            for key, score in preds.items():
                k = str(key).lower()
                if any(name in k for name in WAKE_NAMES) and score >= 0.60:
                    triggered = True
                    triggered_key = k
                    break

            if not triggered:
                continue

            # 2) Wake detected
            play_local_wav(BEEP_WAV)

            # 3) Record until silence
            audio_path = record_until_silence(stream)

            # 4) Send to API
            trace_id = uuid.uuid4().hex
            try:
                interaction_id = upload_audio(audio_path, trace_id)
            except Exception:
                play_local_wav(FALLBACK_WAV)
                continue

            play_local_wav(THINKING_WAV)

            # 5) Wait, fetch, play
            detail = poll_interaction(interaction_id, trace_id)
            if not detail or detail.get("status") != "complete":
                play_local_wav(FALLBACK_WAV)
                continue

            wav_bytes = fetch_audio(interaction_id, trace_id)
            if wav_bytes and play_wav_bytes(wav_bytes):
                continue

            play_local_wav(FALLBACK_WAV)

    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()