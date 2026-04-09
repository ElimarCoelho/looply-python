import os, json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# Check latest group_data entries
res = supabase.table("group_data").select("group_id, group_name, sender_name, created_at").order("created_at", desc=True).limit(10).execute()
print("=== ÚLTIMOS 10 REGISTROS DE group_data ===")
for r in res.data:
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print("---")

# Check unique group names
print("\n=== NOMBRES ÚNICOS DE GRUPO ===")
res2 = supabase.table("group_data").select("group_id, group_name").execute()
seen = {}
for r in res2.data:
    gid = r.get('group_id')
    gname = r.get('group_name')
    if gid not in seen:
        seen[gid] = set()
    seen[gid].add(gname or 'NULL')

for gid, names in seen.items():
    print(f"  Group ID: {gid}")
    print(f"  Nombres guardados: {names}")
    print()
