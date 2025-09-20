# modes/education/education_quiz_mode.py
import asyncio
import random

class EducationQuizMode:
    def __init__(self, bus):
        self.bus = bus
        self.current_letter = None
        self.correct_count = 0
        self.total_attempts = 0
        bus.subscribe("enter_education_quiz_mode", self.enter)
        bus.subscribe("exit_education_quiz_mode", self.exit)
        bus.subscribe("letter_selected", self.on_letter_selected)

    async def enter(self, data):
        print("[EducationQuizMode] ENTER")
        self.correct_count = 0
        self.total_attempts = 0
        await self.bus.publish("tts", {"text": "Quiz mode activated. Touch any braille letter and I'll tell you what it is."})

    async def exit(self, data):
        print("[EducationQuizMode] EXIT")
        self.current_letter = None
        if self.total_attempts > 0:
            accuracy = (self.correct_count / self.total_attempts) * 100
            await self.bus.publish("tts", {"text": f"Quiz session complete. You got {self.correct_count} out of {self.total_attempts} correct. That's {accuracy:.0f} percent accuracy!"})

    async def on_letter_selected(self, data):
        """Handle when a letter is selected in quiz mode"""
        if data.get("mode") == "quiz":
            letter = data.get("letter")
            self.current_letter = letter
            self.total_attempts += 1
            print(f"[EducationQuizMode] Letter selected: {letter}")
            
            # Always provide feedback for blind users
            await self.bus.publish("tts", {"text": f"You touched the letter {letter}"})
            
            # Give additional feedback based on letter
            if letter in ["A", "E", "I", "O", "U"]:
                await asyncio.sleep(1)
                await self.bus.publish("tts", {"text": f"{letter} is a vowel"})
            elif letter in ["B", "C", "D", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "X", "Y", "Z"]:
                await asyncio.sleep(1)
                await self.bus.publish("tts", {"text": f"{letter} is a consonant"})
            
            # Mark as correct (since they're learning by touching)
            self.correct_count += 1
            
            # Wait a bit before allowing next selection
            await asyncio.sleep(2)
            await self.bus.publish("tts", {"text": "Touch another letter to continue learning"})