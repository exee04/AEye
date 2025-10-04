import json
from supabase import create_client
from pathlib import Path
class UserManager:

    def __init__(self, json_file="stats.json"):
        self.user = "username"
        self.uuid = None
        self.json_file = Path(json_file)
    def load_user(self):
        if self.json_file.exists():
            with open(self.json_file, "r") as f:
                self.user = json.load(f)
            print(f"[UserManager]: Loaded user: {self.user['username']}")
        else:
            self.user = None
            print("[UserManager]: No user found")
