import os
import json
from supabase import create_client, Client

class SupabaseService:
    def __init__(self):
        cred_path = os.getenv("SUPABASE_CREDENTIALS")
        if not cred_path:
            raise RuntimeError("[SupabaseService] SUPABASE_CREDENTIALS env var not set")

        try:
            with open(cred_path, "r") as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"[SupabaseService] Credential file not found: {cred_path}")

        self.url = creds.get("SUPABASE_URL")
        self.key = creds.get("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("[SupabaseService] Invalid credentials in JSON file")

        self.client: Client = create_client(self.url, self.key)
        print("[SupabaseService] Initialized connection")

    def test_connection(self, table_name: str):
        try:
            resp = self.client.table(table_name).select("*").limit(1).execute()
            print("[SupabaseService] Connection successful!")
            print(f"[SupabaseService] Test query result: {resp.data}")
        except Exception as e:
            print(f"[SupabaseService] Connection failed: {e}")
