import os
import wave
import struct
import pvporcupine

ACCESS_KEY = os.environ["PICOVOICE_ACCESS_KEY"]

# built-in keyword for testing
porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keywords=["porcupine"],
)

def detect_in_wav(path: str) -> bool:
    with wave.open(path, "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError(f"{path}: must be mono")
        if wf.getsampwidth() != 2:
            raise ValueError(f"{path}: must be 16-bit PCM")
        if wf.getframerate() != porcupine.sample_rate:
            raise ValueError(f"{path}: must be {porcupine.sample_rate} Hz")

        while True:
            pcm_bytes = wf.readframes(porcupine.frame_length)
            if len(pcm_bytes) < porcupine.frame_length * 2:
                break
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm_bytes)
            if porcupine.process(pcm) >= 0:
                return True
    return False

def scan_folder(folder: str) -> None:
    hits = 0
    total = 0
    skipped = 0

    for name in os.listdir(folder):
        if not name.lower().endswith(".wav"):
            continue

        path = os.path.join(folder, name)
        try:
            ok = detect_in_wav(path)
        except ValueError as e:
            print(f"⚠️  SKIP {path}: {e}")
            skipped += 1
            continue

        total += 1
        print(f"{'✅' if ok else '❌'} {path}")
        hits += 1 if ok else 0

    print(f"\nHits: {hits}/{total} (skipped: {skipped})")
if __name__ == "__main__":
    scan_folder("samples/wake")
    scan_folder("samples/neg")