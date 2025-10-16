import asyncio
import os

# --- Core ---
from core.event_bus import EventBus
from core.state_machine import StateMachine
from core.system_state import SystemState

# --- Services ---
from core.services.qr_service import QRService
from core.services.wifi_service import WifiService
from core.services.network_service import NetworkService
from core.services.supabase_client import SupabaseService
from core.services.account_service import AccountService
from core.services.google_speech import GoogleSpeechService
from core.services.speech_command_service import SpeechCommandService
from core.services.startup_service import StartupService  # ← NEW orchestration layer
from core.BrailleDetect import BrailleDetect

# --- HALs ---
from hal.hal_buttons import ButtonHAL
from hal.hal_audio import AudioHAL
from hal.hal_camera import CameraHAL
# from hal.hal_speech import SpeechHAL  # optional

# --- Modes ---
from modes.education.education_mode import EducationMode
from modes.education.education_idle_mode import EducationIdleMode
from modes.education.education_learn_mode import EducationLearnMode
from modes.education.education_quiz_mode import EducationQuizMode
from modes.scorecheck_mode import ScoreCheckMode
from modes.wifi_mode import WifiMode
from modes.volume_mode import VolumeMode


# ----------------------------------------------------------------------
# 🧊 Helper: Monitor temperature on Raspberry Pi
# ----------------------------------------------------------------------
async def thermal_monitor():
    """Print CPU temperature every few seconds (Raspberry Pi only)."""
    while True:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_str = f.readline().strip()
            temp = float(temp_str) / 1000.0
            print(f"[ThermalMonitor] CPU Temperature: {temp:.1f} °C")
        except FileNotFoundError:
            pass
        await asyncio.sleep(3)


# ----------------------------------------------------------------------
# 🧠 Main Entry
# ----------------------------------------------------------------------
async def main():
    print("[Main] Booting AEye system...")

    # --- Stage 0: Core setup ---
    bus = EventBus()
    state = SystemState()
    StateMachine(bus, state)

    # --- Stage 1: Hardware Abstraction Layer ---
    print("[Main] Initializing HALs...")
    ButtonHAL(bus, asyncio.get_event_loop())
    AudioHAL(bus, state)
    camera = CameraHAL(bus, state, show_preview=False)
    #SpeechHAL(bus)  # Optional, if needed later
    asyncio.create_task(thermal_monitor())

    print("[Main] System initialized — awaiting startup flow...")
    while True:
        camera.update()
        await asyncio.sleep(0.01)


# ----------------------------------------------------------------------
# 🚀 Entry Point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
