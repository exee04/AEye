import pyaudio
from vosk import Model, KaldiRecognizer
import json

# === Configuration ===
MODEL_PATH = "/home/ky/AEye/AEyeProj/VoskModels/vosk-model-en-us-0.22"
SAMPLE_RATE = 16000
CHUNK = 4000  # bytes of audio per read

# === Initialize Vosk model and recognizer ===
model = Model(MODEL_PATH)
rec = KaldiRecognizer(model, SAMPLE_RATE)

# === Initialize Microphone Stream ===
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK)
stream.start_stream()

print("??? Listening... Press Ctrl+C to stop.")

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            print("???", res.get("text", ""))
        else:
            partial = json.loads(rec.PartialResult())
            print("...", partial.get("partial", ""), end="\r")

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
