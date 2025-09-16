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
        """Send audio file to Google STT"""
        file_path = data.get("file")
        rate = data.get("sample_rate", 16000)
        if not file_path:
            print("[GoogleSpeechService] No file provided")
            return

        print(f"[GoogleSpeechService] Processing file: {file_path} (rate={rate})")

        try:
            with open(file_path, "rb") as audio_file:
                content = audio_file.read()

            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=rate,
                language_code=self.state.language  # "en-US" or "fil-PH"
            )

            # Run STT in background thread to not block asyncio loop
            response = await asyncio.to_thread(
                self.client.recognize, config=config, audio=audio
            )

            transcript = (
                response.results[0].alternatives[0].transcript
                if response.results else ""
            )

            print(f"[GoogleSpeechService] Transcript: '{transcript}'")
            await self.bus.publish("speech_result", {
                "file": file_path,
                "text": transcript
            })

        except Exception as e:
            print(f"[GoogleSpeechService] Error: {e}")
            await self.bus.publish("speech_result", {
                "file": file_path,
                "text": ""
            })
