"""
Script para corregir los nombres de grupo incorrectos en Supabase.
Consulta la API de WaSender para obtener el nombre real y actualiza los registros.
"""
import os, json, requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# Obtener el token dinámico desde la configuración remota
try:
    config_res = requests.get('https://moneymaze.es/apps/looply/user_settings.php', timeout=5)
    wasender_token = config_res.json().get('data', {}).get('wasender_token')
    print(f"✅ Token dinámico obtenido: {wasender_token[:10]}...")
except:
    wasender_token = os.environ.get("WASENDER_TOKEN")
    print(f"⚠️ Usando token del .env: {wasender_token[:10] if wasender_token else 'NONE'}...")

# Obtener todos los group_ids únicos
res = supabase.table("group_data").select("group_id, group_name").execute()
groups = {}
for r in res.data:
    gid = r.get('group_id')
    gname = r.get('group_name')
    if gid not in groups:
        groups[gid] = set()
    groups[gid].add(gname or 'NULL')

print(f"\n=== Grupos encontrados: {len(groups)} ===")
for gid, names in groups.items():
    print(f"  {gid}: {names}")

# Para cada grupo, obtener nombre real y actualizar si es necesario
for gid in groups:
    current_names = groups[gid]
    
    # Consultar API de WaSender
    try:
        meta_url = f"https://wasenderapi.com/api/groups/{gid}/metadata"
        headers = {'Authorization': f'Bearer {wasender_token}'}
        meta_res = requests.get(meta_url, headers=headers, timeout=10)
        
        if meta_res.status_code == 200:
            real_name = meta_res.json().get('data', {}).get('subject')
            print(f"\n🌐 Nombre REAL del grupo {gid}: '{real_name}'")
            
            # Verificar si algún registro tiene nombre incorrecto
            needs_update = False
            for n in current_names:
                if n != real_name:
                    needs_update = True
                    break
            
            if needs_update and real_name:
                print(f"  ⚡ Actualizando todos los registros de {gid} → '{real_name}'")
                update_res = supabase.table("group_data").update(
                    {"group_name": real_name}
                ).eq("group_id", gid).execute()
                print(f"  ✅ Actualizados {len(update_res.data)} registros")
            else:
                print(f"  ✅ Nombre correcto, no requiere actualización")
        else:
            print(f"\n❌ Error API para {gid}: {meta_res.status_code} - {meta_res.text[:100]}")
    except Exception as e:
        print(f"\n❌ Excepción para {gid}: {e}")

print("\n🏁 Corrección completada")
