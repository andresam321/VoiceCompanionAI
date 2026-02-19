# device/agent.py
"""
Raspberry Pi device agent.

Records audio via microphone (or reads a .wav file),
sends it to the Companion API, polls for the result,
and plays back the TTS response.

Usage:
  python device/agent.py                  # record from mic
  python device/agent.py path/to/file.wav # send existing file
"""
from __future__ import annotations

import io
import os
import sys
import time
import tempfile

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-device-token-001")
RECORD_SECONDS = 5
SAMPLE_RATE = 16000
POLL_INTERVAL = 1.0
MAX_POLLS = 60

HEADERS = {"X-Device-Token": DEVICE_TOKEN}


def record_audio(duration: int = RECORD_SECONDS, sr: int = SAMPLE_RATE) -> str:
    """Record audio from the default microphone and save to a temp .wav file."""
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError:
        print("Install sounddevice and soundfile: pip install sounddevice soundfile")
        sys.exit(1)

    print(f"🎙  Recording for {duration}s...")
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="int16")
    sd.wait()
    print("✅ Recording complete.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, sr)
    return tmp.name


def upload_audio(audio_path: str) -> dict:
    """Upload audio to the API and return the response."""
    url = f"{API_BASE}/v1/voice-interactions"
    with open(audio_path, "rb") as f:
        resp = requests.post(url, headers=HEADERS, files={"audio": ("audio.wav", f, "audio/wav")})
    resp.raise_for_status()
    return resp.json()


def poll_result(interaction_id: str) -> dict:
    """Poll the API until the interaction is complete or times out."""
    url = f"{API_BASE}/v1/interactions/latest"
    for i in range(MAX_POLLS):
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  ⏳ Status: {status} (poll {i+1}/{MAX_POLLS})")
        if status == "complete":
            return data
        if status == "failed":
            print("❌ Processing failed.")
            return data
        time.sleep(POLL_INTERVAL)
    print("⏰ Timed out waiting for result.")
    return {}


def play_audio(interaction_id: str) -> None:
    """Download and play the TTS audio response."""
    url = f"{API_BASE}/v1/audio/{interaction_id}.wav"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print("⚠️  Audio not available.")
        return

    try:
        import sounddevice as sd
        import soundfile as sf

        audio_data, sr = sf.read(io.BytesIO(resp.content))
        print("🔊 Playing response...")
        sd.play(audio_data, sr)
        sd.wait()
    except ImportError:
        # Fallback: save to file
        out = "/tmp/companion_response.wav"
        with open(out, "wb") as f:
            f.write(resp.content)
        print(f"🔊 Audio saved to {out}")


def main():
    # Determine audio source
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        print(f"📁 Using file: {audio_path}")
    else:
        audio_path = record_audio()

    # Upload
    print("📤 Uploading audio...")
    result = upload_audio(audio_path)
    interaction_id = result["interaction_id"]
    print(f"📝 Interaction: {interaction_id}")

    # Poll
    print("⏳ Waiting for processing...")
    detail = poll_result(interaction_id)

    if detail.get("status") == "complete":
        print(f"\n👤 You said: {detail.get('transcript', '?')}")
        print(f"🤖 {detail.get('assistant_reply', '...')}")
        if detail.get("detected_emotion"):
            print(f"💭 Emotion: {detail['detected_emotion']} ({detail.get('emotion_confidence', 0):.0%})")

        # Play TTS
        play_audio(interaction_id)


if __name__ == "__main__":
    main()
