import os
import time
import asyncio
import numpy as np
from scipy.io.wavfile import write
import sounddevice as sd
import threading

# Detect if running on Raspberry Pi (same trick as hal_buttons)
def is_raspberry_pi():
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "Raspberry Pi" in f.read()
    except FileNotFoundError:
        return False


class SpeechHAL:
    def __init__(self, bus):
        self.bus = bus
        self.recording = False
        self.start_time = None
        self._recording_task = None
        self.frames = []
        self.stream = None
        self.device_index = None
        self.file_lock = threading.Lock()
        self.cache_file = os.path.expanduser(
            "~/Desktop/AEye/cache/audio_latest.wav"
        )
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

        # 🔹 Detect devices
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        host_api = sd.query_hostapis()[0]

        # Pick device: Pi USB mic or laptop default
        if is_raspberry_pi():
            for idx, dev in enumerate(devices):
                if "USB" in dev["name"] and dev["max_input_channels"] > 0:
                    self.device_index = idx
                    break
        if self.device_index is None:
            self.device_index = default_input

        self.device_info = devices[self.device_index]
        self.sample_rate = self._pick_sample_rate()

        print(f"[SpeechHAL] Using device {self.device_index}: {self.device_info['name']}")
        print(f"           Max input channels: {self.device_info['max_input_channels']}")
        print(f"           Default samplerate: {self.device_info['default_samplerate']}")
        print(f"           Selected samplerate: {self.sample_rate}")

        # Subscribe to button events
        bus.subscribe("button_hold", self.on_button_hold)
        bus.subscribe("button_press", self.on_button_tap)
        bus.subscribe("button_release", self.on_button_release)

    def _pick_sample_rate(self):
        """Try common sample rates and return one supported by the device"""
        common_rates = [16000, 44100, 48000]
        for rate in common_rates:
            try:
                sd.check_input_settings(device=self.device_index, samplerate=rate)
                print(f"[SpeechHAL] Sample rate {rate} Hz is supported")
                return rate
            except Exception as e:
                print(f"[SpeechHAL] Sample rate {rate} Hz not supported: {e}")
        raise RuntimeError("[SpeechHAL] No valid sample rate found for this device")


    async def on_button_hold(self, data):
        """Start recording when main button is held"""
        pin = data.get("pin")
        if pin == 24 and not self.recording:
            self.recording = True
            self.start_time = time.time()
            self.frames = []

            # 🔹 Start microphone stream
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device_index,
                callback=self._callback,
            )
            self.stream.start()

            print("[SpeechHAL] Recording started...")
            self._recording_task = asyncio.create_task(self._print_recording_loop())
            await self.bus.publish("speech_record_start", {"pin": pin})

    def _callback(self, indata, frames, time_info, status):
        """Collect audio samples into self.frames"""
        if self.recording:
            self.frames.append(indata.copy())

    async def _print_recording_loop(self):
        """Keep printing 'Recording...' while button is held"""
        while self.recording:
            print("Recording...")
            await asyncio.sleep(0.5)

    async def on_button_tap(self, data):
        """Quick tap (future use)"""
        pin = data.get("pin")
        if pin == 24:
            print("[SpeechHAL] Main button tapped → (reserved for future quick actions)")

    async def on_button_release(self, data):
        pin = data.get("pin")
        if pin == 24 and self.recording:
            self.recording = False
            duration = time.time() - self.start_time
            print(f"[SpeechHAL] Recording stopped. Duration: {duration:.2f}s")

            # Stop stream
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            # Cancel background "Recording..." loop
            if self._recording_task:
                self._recording_task.cancel()
                self._recording_task = None

            # 🔹 Save only if frames exist
            if self.frames:
                audio_data = np.concatenate(self.frames, axis=0).flatten()
                with self.file_lock:
                    write(self.cache_file, self.sample_rate, audio_data)
                print(f"[SpeechHAL] Audio saved → {self.cache_file}")

                # ✅ Instead of STT here → hand off to GoogleSpeechService
                await self.bus.publish("speech_process", {
                    "file": self.cache_file,
                    "sample_rate": self.sample_rate
                })
            else:
                print("[SpeechHAL] WARNING: No audio frames captured!")

        def get_audio_file(self):
            """Return last recorded file if exists"""
            with self.file_lock:
                return self.cache_file if os.path.exists(self.cache_file) else None
