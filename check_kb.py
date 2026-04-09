import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("Checking base_conocimiento table...")
try:
    response = supabase.table("base_conocimiento").select("*").limit(5).execute()
    print("Data found:")
    for row in response.data:
        print(f"Phone: {row.get('phone_number')}, Business: {row.get('business_name')}, KB length: {len(row.get('knowledge_base', ''))}")
except Exception as e:
    print(f"Error: {e}")
