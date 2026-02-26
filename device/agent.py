from __future__ import annotations

import io
import os
import struct
import tempfile
import time
import uuid
import wave
from pathlib import Path
from typing import Optional

import pvporcupine
import pyaudio
import requests
import webrtcvad

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-device-token-001")
HEADERS_BASE = {"X-Device-Token": DEVICE_TOKEN}

# Porcupine
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
PAL_KEYWORD_PATH = os.getenv("PAL_KEYWORD_PATH", "")  # e.g. device/keywords/pal.ppn
FALLBACK_KEYWORD = os.getenv("FALLBACK_KEYWORD", "porcupine")  # built-in keyword
PORCUPINE_SENSITIVITY = float(os.getenv("PORCUPINE_SENSITIVITY", "0.6"))

# Audio
SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 20
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 320 @ 16kHz
HTTP_TIMEOUT = 10

# Optional audio device selection (Mac often needs this)
AUDIO_INPUT_DEVICE_INDEX = os.getenv("AUDIO_INPUT_DEVICE_INDEX")  # e.g. "0", "1"
PRINT_AUDIO_DEVICES = os.getenv("PRINT_AUDIO_DEVICES", "false").lower() == "true"

# Polling
POLL_INTERVAL = 0.6
MAX_POLLS = 80

# VAD tuning
VAD_AGGRESSIVENESS = 2  # 0-3
MAX_RECORD_SECONDS = 6
SILENCE_STOP_MS = 700

# UI sounds (optional)
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "device/assets"))
BEEP_WAV = ASSETS_DIR / "beep.wav"
THINKING_WAV = ASSETS_DIR / "thinking.wav"
FALLBACK_WAV = ASSETS_DIR / "fallback.wav"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def req(method: str, url: str, **kwargs) -> requests.Response:
    return requests.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)


def play_local_wav(path: Path) -> None:
    """Best-effort local wav playback (non-fatal if audio libs not installed)."""
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


def play_wav_bytes(wav_bytes: bytes) -> bool:
    """Play wav bytes. Returns True if played, False otherwise."""
    try:
        import sounddevice as sd
        import soundfile as sf

        audio, sr = sf.read(io.BytesIO(wav_bytes))
        sd.play(audio, sr)
        sd.wait()
        return True
    except Exception:
        return False


def write_wav_file(frames: list[bytes]) -> str:
    """Write int16 PCM frames to a wav file and return path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))
    return tmp.name


def record_until_silence(stream: pyaudio.Stream) -> str:
    """Record after wake until silence (or max seconds)."""
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
            # require at least ~0.5s total before allowing early stop
            if silence_ms >= SILENCE_STOP_MS and len(frames) > int(0.5 * 1000 / FRAME_MS):
                break

    return write_wav_file(frames)


def upload_audio(audio_path: str, trace_id: str) -> str:
    """POST wav to API. Returns interaction_id."""
    url = f"{API_BASE}/v1/voice-interactions"
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}
    with open(audio_path, "rb") as f:
        resp = req("POST", url, headers=headers, files={"audio": ("audio.wav", f, "audio/wav")})
    resp.raise_for_status()
    return resp.json()["interaction_id"]


def poll_interaction(interaction_id: str, trace_id: str) -> dict:
    """Poll interaction by id until complete/failed."""
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}

    by_id = f"{API_BASE}/v1/voice-interactions/{interaction_id}"
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


def fetch_audio(interaction_id: str, trace_id: str) -> Optional[bytes]:
    url = f"{API_BASE}/v1/audio/{interaction_id}.wav"
    headers = {**HEADERS_BASE, "X-Trace-Id": trace_id}
    r = req("GET", url, headers=headers)
    if r.status_code == 200 and r.content:
        return r.content
    return None


def build_porcupine() -> pvporcupine.Porcupine:
    """
    Prefer a custom 'pal' model if PAL_KEYWORD_PATH is provided.
    Otherwise fall back to a built-in keyword (computer/jarvis/etc).
    """
    if not PICOVOICE_ACCESS_KEY:
        raise RuntimeError("PICOVOICE_ACCESS_KEY is not set")

    if PAL_KEYWORD_PATH:
        keyword_path = Path(PAL_KEYWORD_PATH)
        if not keyword_path.exists():
            raise RuntimeError(f"PAL_KEYWORD_PATH not found: {PAL_KEYWORD_PATH}")

        return pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[str(keyword_path)],
            sensitivities=[PORCUPINE_SENSITIVITY],
        )

    return pvporcupine.create(
        access_key=PICOVOICE_ACCESS_KEY,
        keywords=[FALLBACK_KEYWORD],
        sensitivities=[PORCUPINE_SENSITIVITY],
    )


def print_input_devices(pa: pyaudio.PyAudio) -> None:
    print("\n--- Audio Input Devices ---")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            name = info.get("name", "")
            rate = info.get("defaultSampleRate", "")
            print(f"[{i}] {name} (defaultSampleRate={rate})")
    print("---------------------------\n")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    porcupine = build_porcupine()

    pa = pyaudio.PyAudio()
    if PRINT_AUDIO_DEVICES:
        print_input_devices(pa)

    input_device_index = int(AUDIO_INPUT_DEVICE_INDEX) if AUDIO_INPUT_DEVICE_INDEX else None

    stream = pa.open(
        rate=porcupine.sample_rate,  # Porcupine expects its sample rate
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        input_device_index=input_device_index,
        frames_per_buffer=porcupine.frame_length,
    )

    print(f"Listening, API_BASE={API_BASE}, keyword={'PAL' if PAL_KEYWORD_PATH else FALLBACK_KEYWORD}")
    if input_device_index is not None:
        print(f"Using AUDIO_INPUT_DEVICE_INDEX={input_device_index}")

    try:
        while True:
            # 1) Listen for wake
            pcm_bytes = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm_bytes)

            keyword_index = porcupine.process(pcm)
            if keyword_index < 0:
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
        try:
            stream.stop_stream()
            stream.close()
        finally:
            pa.terminate()
            porcupine.delete()


if __name__ == "__main__":
    main()