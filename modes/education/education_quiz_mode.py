# modes/education/education_quiz_mode.py
import asyncio
import random

class EducationQuizMode:
    def __init__(self, bus):
        self.bus = bus
        self.is_active = False
        self.current_question = None
        self.questions = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", 
                         "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", 
                         "U", "V", "W", "X", "Y", "Z"]
        bus.subscribe("enter_education_quiz_mode", self.enter)
        bus.subscribe("exit_education_quiz_mode", self.exit)
        bus.subscribe("braille_letter_detected", self.on_letter_detected)

    async def enter(self, data):
        print("[EducationQuizMode] ENTER")
        self.is_active = True
        await self.bus.publish("tts", {"text": "Education sub-mode: Quiz. I will ask you to find letters."})
        await self.bus.publish("education_mode_entered", {"submode": "quiz"})
        await self.ask_question()

    async def exit(self, data):
        print("[EducationQuizMode] EXIT")
        self.is_active = False
        await self.bus.publish("education_mode_exited", {"submode": "quiz"})
        
    async def ask_question(self):
        """Ask a random letter question"""
        if not self.is_active:
            return
            
        self.current_question = random.choice(self.questions)
        print(f"[EducationQuizMode] Asking for letter: {self.current_question}")
        await self.bus.publish("tts", {"text": f"Can you find the letter {self.current_question}?"})
        
    async def on_letter_detected(self, data):
        """Handle detected braille letter in quiz mode"""
        if not self.is_active or not self.current_question:
            return
            
        letter = data.get("letter", "?")
        dot_pattern = data.get("dot_pattern", "")
        
        print(f"[EducationQuizMode] Letter detected: {letter} (pattern: {dot_pattern})")
        
        if letter == self.current_question:
            # Correct answer
            await self.bus.publish("tts", {"text": f"Correct! That is the letter {letter}. Well done!"})
            await asyncio.sleep(2)  # Wait a bit before next question
            await self.ask_question()
        elif letter != "?":
            # Wrong answer
            await self.bus.publish("tts", {"text": f"That is the letter {letter}. Try to find {self.current_question}."})
        else:
            # Unknown pattern
            await self.bus.publish("tts", {"text": "I don't recognize that pattern. Try to find the letter I asked for."})
