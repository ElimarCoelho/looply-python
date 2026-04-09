import os, json, requests
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("WASENDER_TOKEN") or "802f0eb2f10b2dd4776553d81f717a2c50aa70645da57ebdcbf086396ce7bf82"
group_jid = "120363423203306499@g.us"

print(f"Token: {token[:10]}...")
print(f"Group JID: {group_jid}")

url = f"https://wasenderapi.com/api/groups/{group_jid}/metadata"
headers = {'Authorization': f'Bearer {token}'}

try:
    res = requests.get(url, headers=headers, timeout=10)
    print(f"\nStatus: {res.status_code}")
    print(f"Response: {json.dumps(res.json(), indent=2, ensure_ascii=False)}")
    
    if res.status_code == 200:
        data = res.json().get('data', {})
        subject = data.get('subject')
        name = data.get('name')
        print(f"\n=== RESULTADO ===")
        print(f"  subject: {subject}")
        print(f"  name: {name}")
except Exception as e:
    print(f"Error: {e}")
