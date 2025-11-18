import os
import json
import aiohttp
from dotenv import load_dotenv
import asyncio
from google.cloud import speech

class APIHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state
        self.google_client = None
        self.client = None
        self.supabase_client = None
        self.runpod_client = None
        self.is_initialized = False
        self.online = state.hasConnection
        self.bus.subscribe("init_api", self.initialize)
        bus.subscribe("network_lost", self.on_network_lost)
        bus.subscribe("network_restored", self.on_network_restored)
        bus.subscribe("speech_process", self.process_audio)

    async def on_network_lost(self, _):
        self.online = False
        await self.bus.publish("tts", {"text": "Connection lost. Switching to offline mode."})
        print("[APIService] Internet connection lost.")

    async def on_network_restored(self, _):
        self.online = True
        await self.bus.publish("tts", {"text": "Internet connection restored."})
        print("[APIService] Internet connection restored.")

    async def initialize(self):
        print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        if not self.state.hasConnection:
            print("[APIHandler] No Connection, can't initiaize API Serivces")
            return
        load_dotenv()

        print("[APIHandler] Network online initializing APIs...")

        await self.__init_google_client()
        await self.__init_supabase_client()
        await self.test_all_connections()

    async def __init_google_client(self):
        creds_path = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            print("[APIHandler] ⚠️ Missing GOOGLE_CLOUD_CREDENTIALS.")
            return
        with open(creds_path, "r") as f:
            print(str(f))
            self.google_client = json.load(f)
            self.client = speech.SpeechClient()
        print("[APIHandler] ✅ Google credentials loaded from file.")

    async def __init_supabase_client(self):
        creds_path = os.getenv("SUPABASE_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            print("[APIHandler] ⚠️ Missing SUPABASE_CLIENT.")
            return
        with open(creds_path, "r") as f:
            self.supabase_client = json.load(f)
        print("[APIHandler] ✅ Supabase credentials loaded from file.")

    async def __init_runpod_client(self):
        # No runpod client yet
        return

    async def test_all_connections(self):
        """Run lightweight connectivity checks."""
        print("[APIHandler] 🔍 Testing API connections...")
        google_ok = await self.test_google_connection()
        supabase_ok = await self.test_supabase_connection()
        #runpod_ok = await self.test_runpod_connection()

        if all([google_ok, supabase_ok]):
            print("[APIHandler] ✅ All APIs reachable.")
            self.is_initialized = True
        else:
            print("[APIHandler] ⚠️ Some API checks failed.")

    async def test_google_connection(self):
        print("[APIHandler] 🧠 Testing Google Cloud connection...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.google.com/generate_204", timeout=5) as r:
                    print(f"[APIHandler] → HTTP {r.status}")
                    if r.status in (200, 204):
                        print("[APIHandler] ✅ Google reachable.")
                        return True
        except Exception as e:
            print(f"[APIHandler] ❌ Google unreachable: {type(e).__name__} - {e}")
        print("[APIHandler] ⚠️ Google API test failed.")
        return False

    async def test_supabase_connection(self):
        try:
            if not self.supabase_client:
                return False
            url = self.supabase_client.get("SUPABASE_URL")
            if not isinstance(url, str):
                print("[APIHandler] ⚠️ Supabase URL invalid:", url)
                return False
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as r:
                    if r.status < 500:
                        print("[APIHandler] ✅ Supabase reachable.")
                        return True
        except Exception as e:
            print(f"[APIHandler] Supabase unreachable: {e}")
        return False

    #    async def test_runpod_connection(self):
#        """Optional: Test runpod.io API."""
#        try:
#            async with aiohttp.ClientSession() as session:
#                async with session.get("https://api.runpod.io", timeout=3) as r:
#                    if r.status == 200:
#                        print("[APIHandler] Runpod API reachable.")
#                        return True
#        except Exception as e:
#            print(f"[APIHandler] Runpod API unreachable: {e}")
#        return False

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

