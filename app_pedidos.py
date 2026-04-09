import os
import sys
import json
from flask import Flask, render_template_string, send_from_directory
from dotenv import load_dotenv
from supabase import create_client, Client
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

load_dotenv()

app = Flask(__name__)

# Serve logo from imagen folder
@app.route('/imagen/logo.jpg')
def serve_logo():
    return send_from_directory('imagen', 'logo.jpg')

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    try:
        # Fetch all messages from backend to avoid any frontend CORS or network issues
        response = supabase.table("group_data").select("*").order("created_at", desc=True).limit(1000).execute()
        data = response.data
        data_json = json.dumps(data)
        
        with open('pedidos.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        return render_template_string(html_content, group_data_json=data_json)
    except Exception as e:
        return f"Error loading pedidos.html: {e}", 500

if __name__ == '__main__':
    # run on port 8447 as requested
    port = int(os.environ.get('PORT', 8447))
    print(f"Server for pedidos running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
