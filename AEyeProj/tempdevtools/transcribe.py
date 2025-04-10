import whisper

model = whisper.load_model("base")  # You can try "base" for better accuracy
result = model.transcribe("audio.wav")
print("You said:", result["text"])
