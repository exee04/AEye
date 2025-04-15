import pyaudio
import time
from google.cloud import speech
import os


# Initialize Google Cloud client
client = speech.SpeechClient()

# Audio recording parameters
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=RATE,
    language_code="en-US",
    alternative_language_codes=["fil-PH"],
)

streaming_config = speech.StreamingRecognitionConfig(
    config=config,
    interim_results=True,
)

def generate_audio():
    mic = pyaudio.PyAudio()
    stream = mic.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    start_time = time.time()
    print("??? Listening for 5 seconds...")

    try:
        while time.time() - start_time < RECORD_SECONDS:
            yield speech.StreamingRecognizeRequest(audio_content=stream.read(CHUNK))
    finally:
        stream.stop_stream()
        stream.close()
        mic.terminate()
        print("?? Stopped recording")

def main():
    responses = client.streaming_recognize(streaming_config, generate_audio())

    print("?? Transcription:")
    try:
        for response in responses:
            for result in response.results:
                if result.is_final:
                    print("?", result.alternatives[0].transcript)
                    return  # Exit after first final result (optional)
    except Exception as e:
        print("? Error during transcription:", e)

if __name__ == "__main__":
    main()
