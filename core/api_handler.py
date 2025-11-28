# api_handler.py
import os
import json
import aiohttp
from dotenv import load_dotenv
import asyncio
from google.cloud import speech
from supabase import create_client, Client


class APIHandler:
    def __init__(self, bus, state):
        self.bus = bus
        self.state = state

        self.supabase: Client | None = None
        self.google_client = None
        self.client = None

        self.online = state.hasConnection
        self.initialized = False

        bus.subscribe("init_api", self.initialize)
        bus.subscribe("network_lost", self.on_network_lost)
        bus.subscribe("network_restored", self.on_network_restored)
        bus.subscribe("speech_process", self.process_audio)

    # ----------------------------------------------------------------------
    async def on_network_lost(self, _):
        self.online = False
        print("[APIHandler] Internet lost.")

    async def on_network_restored(self, _):
        self.online = True
        print("[APIHandler] Internet restored.")

    # ----------------------------------------------------------------------
    async def initialize(self):
        if not self.state.hasConnection:
            print("[APIHandler] Cannot initialize APIs — no network.")
            return

        print("[APIHandler] Starting API initialization...")
        load_dotenv()

        await self.__init_google_client()
        await self.__init_supabase_client()
        await self.test_all_connections()

    # ----------------------------------------------------------------------
    async def __init_google_client(self):
        creds_path = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            print("[APIHandler] ⚠ Missing GOOGLE_CLOUD_CREDENTIALS file.")
            return

        with open(creds_path, "r") as f:
            self.google_client = json.load(f)
            self.client = speech.SpeechClient()

        print("[APIHandler] ✅ Google Cloud STT initialized.")

    # ----------------------------------------------------------------------
    async def __init_supabase_client(self):
        creds_path = os.getenv("SUPABASE_CREDENTIALS")
        if not creds_path or not os.path.exists(creds_path):
            print("[APIHandler] ⚠ Missing SUPABASE_CREDENTIALS file.")
            return

        with open(creds_path, "r") as f:
            creds = json.load(f)

        url = creds.get("SUPABASE_URL")
        key = creds.get("SUPABASE_KEY")

        if not url or not key:
            print("[APIHandler] ❌ Supabase creds invalid.")
            return

        try:
            self.supabase = create_client(url, key)
            print("[APIHandler] ✅ Supabase client initialized.")

            # IMPORTANT: Notify modules (EducationMode)
            await self.bus.publish("supabase_ready", {"client": self.supabase})

        except Exception as e:
            print("[APIHandler] ❌ Supabase creation error:", e)

    # ----------------------------------------------------------------------
    async def test_all_connections(self):
        print("[APIHandler] 🔍 Running connectivity tests...")

        google_ok = await self.test_google_connection()
        supabase_ok = await self.test_supabase_connection()

        if google_ok and supabase_ok:
            self.initialized = True
            print("[APIHandler] ✅ All external APIs online.")
        else:
            print("[APIHandler] ⚠ Some connections failed.")

    # ----------------------------------------------------------------------
    async def test_google_connection(self):
        print("[APIHandler] Testing Google Cloud...")
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://www.google.com/generate_204", timeout=5) as r:
                    return r.status in (200, 204)
        except Exception:
            return False

    # ----------------------------------------------------------------------
    async def test_supabase_connection(self):
        if not self.supabase:
            return False

        try:
            # simply ping the table metadata
            _ = self.supabase.table("performance_history").select("*").limit(1).execute()
            print("[APIHandler] ✅ Supabase reachable.")
            return True
        except Exception as e:
            print("[APIHandler] ❌ Supabase unreachable:", e)
            return False

    # ----------------------------------------------------------------------
    async def process_audio(self, data):
        """Send audio file to Google STT"""
        if not self.client:
            print("[APIHandler] No Google client available.")
            return

        file_path = data.get("file")
        if not file_path:
            print("[APIHandler] No audio file provided.")
            return

        try:
            with open(file_path, "rb") as audio_file:
                content = audio_file.read()

            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=data.get("sample_rate", 16000),
                language_code=self.state.language
            )

            response = await asyncio.to_thread(
                self.client.recognize, config=config, audio=audio
            )

            transcript = (
                response.results[0].alternatives[0].transcript
                if response.results else ""
            )

            await self.bus.publish("speech_result", {
                "file": file_path,
                "text": transcript
            })

        except Exception as e:
            print("[APIHandler] STT Error:", e)
            await self.bus.publish("speech_result", {
                "file": file_path,
                "text": ""
            })

