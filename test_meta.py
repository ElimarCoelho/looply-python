import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

try:
    # Intento de inserción con metadata para ver si falla
    print("Testing insert with metadata on conversations...")
    # Buscamos un lead_id válido
    res = supabase.table("leads").select("id").limit(1).execute()
    if not res.data:
        print("No leads found to test.")
    else:
        lead_id = res.data[0]['id']
        test_res = supabase.table("conversations").insert({
            "lead_id": lead_id,
            "role": "user",
            "content": "TEST_METADATA",
            "metadata": {"test": "ok"}
        }).execute()
        print("✅ Success! The column exists.")
except Exception as e:
    print(f"❌ Error: {e}")
