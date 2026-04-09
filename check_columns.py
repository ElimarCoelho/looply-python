import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("--- group_data ---")
res = supabase.table("group_data").select("*").limit(1).execute()
print(res.data[0] if res.data else "No data")

print("\n--- conversations ---")
res = supabase.table("conversations").select("*").limit(1).execute()
print(res.data[0] if res.data else "No data")
