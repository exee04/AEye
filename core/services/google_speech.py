import asyncio
from google.cloud import speech

class GoogleSpeechService:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.client = speech.SpeechClient()
        print("[GoogleSpeechService] Initialized with Google Cloud Speech-to-Text")

        # Listen for recorded audio from hal_speech
        self.bus.subscribe("speech_process", self.process_audio)

    async def process_audio(self, data):
        """Send audio to Google Speech API and return text result."""
        file_path = data.get("file")
        if not file_path:
            print("[GoogleSpeechService] No file provided")
            return

        print(f"[GoogleSpeechService] Processing file: {file_path}")

        # TODO: Load audio file for real API request
        # with open(file_path, "rb") as audio_file:
        #     content = audio_file.read()

        # audio = speech.RecognitionAudio(content=content)
        # config = speech.RecognitionConfig(
        #     encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        #     sample_rate_hertz=16000,
        #     language_code=self.state.language  # en-US or fil-PH
        # )
        # response = self.client.recognize(config=config, audio=audio)
        # transcript = response.results[0].alternatives[0].transcript

        # Mock result for now
        transcript = "mock speech-to-text result"
        print(f"[GoogleSpeechService] Mock transcript: {transcript}")

        # Publish final result
        await self.bus.publish("speech_result", {
            "file": file_path,
            "text": transcript
        })
