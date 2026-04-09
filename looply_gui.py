import os
import json
import threading
import requests
import webbrowser
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv, set_key
from supabase import create_client, Client
import google.generativeai as genai
import customtkinter as ctk

# Cargar variables de entorno
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# --- CONFIGURACIÓN FLASK ---
app = Flask(__name__, static_folder='.')
CORS(app)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = 'gemini-2.0-flash'
WASENDER_TOKEN_DEFAULT = os.getenv('WASENDER_TOKEN')
MANAGE_BOT_URL = 'https://moneymaze.es/apps/looply/manage_bot.php'
SETTINGS_PHP_URL = 'https://moneymaze.es/apps/looply/user_settings.php'

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase_client: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Error Supabase: {e}")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- LÓGICA DE BACKEND (Replicada de app.py) ---

def send_whatsapp_message(to, text, token=None):
    final_token = token or WASENDER_TOKEN_DEFAULT
    if not final_token: return
    url = "https://wasenderapi.com/api/send-message"
    headers = {'Authorization': f'Bearer {final_token}', 'Content-Type': 'application/json'}
    try: requests.post(url, json={'to': to, 'text': text}, headers=headers)
    except Exception as e: print(f"Error WaSender: {e}")

def get_gemini_response(message, history=[], api_key=None, custom_prompt=None):
    final_key = api_key or os.getenv('GEMINI_API_KEY')
    if not final_key: return "Error: No API Key."
    system_prompt = custom_prompt or "Eres un experto vendedor de Looply. Responde profesional y corto."
    try:
        model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=system_prompt)
        chat_history = [{'role': 'user' if m['role'] == 'user' else 'model', 'parts': [m['content']]} for m in history]
        chat = model.start_chat(history=chat_history)
        return chat.send_message(message).text
    except Exception as e: return f"Error Gemini: {e}"

@app.route('/')
def serve_index(): return send_from_directory('.', 'dashboard_new.html')

@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    body = request.json
    try:
        event = body.get('event')
        data = body.get('data', {})
        if event in ['messages.upsert', 'message.received', 'messages.received', 'messages-group.received'] and data.get('messages'):
            msg = data['messages']
            if msg.get('key', {}).get('fromMe'): return "OK", 200
            
            remote_jid = msg.get('key', {}).get('remoteJid', '')
            is_group = '@g.us' in remote_jid
            sender_id = msg.get('key', {}).get('cleanedSenderPn') or msg.get('key', {}).get('cleanedParticipantPn') or msg.get('key', {}).get('participant')
            if is_group and sender_id: sender_id = sender_id.split('@')[0]
            
            message_text = msg.get('messageBody') or msg.get('message', {}).get('conversation') or \
                           msg.get('message', {}).get('extendedTextMessage', {}).get('text') or ''
            
            target_id = remote_jid if is_group else (sender_id or remote_jid.split('@')[0])
            
            if target_id and message_text and supabase_client:
                # FLUJO GRUPOS: Solo procesar si contiene "lista de materiales"
                if is_group and 'lista de materiales' not in message_text.lower():
                    print(f"ℹ️ Mensaje de grupo ignorado (no es lista): {message_text[:30]}...")
                    return "OK", 200

                # Lógica simplificada de guardado y respuesta
                res = supabase_client.table('leads').select('id').eq('whatsapp_id', target_id).execute()
                lead = res.data[0] if res.data else None
                if not lead:
                    res = supabase_client.table('leads').insert({'whatsapp_id': target_id, 'platform': 'whatsapp_group' if is_group else 'whatsapp'}).execute()
                    lead = res.data[0] if res.data else None
                
                if not lead: return "OK", 200

                supabase_client.table('conversations').insert({'lead_id': lead['id'], 'role': 'user', 'content': message_text}).execute()
                history = supabase_client.table('conversations').select('role, content').eq('lead_id', lead['id']).order('created_at').limit(10).execute().data
                
                # Config desde PHP
                try:
                    user_config = requests.get(SETTINGS_PHP_URL).json().get('data', {})
                except:
                    user_config = {}
                
                ia_reply = get_gemini_response(message_text, history, user_config.get('gemini_api_key'), user_config.get('bot_prompt'))
                
                if ia_reply:
                    supabase_client.table('conversations').insert({'lead_id': lead['id'], 'role': 'agent', 'content': ia_reply}).execute()
                    send_whatsapp_message(remote_jid if is_group else f"+{target_id}", ia_reply, user_config.get('wasender_token'))
    except Exception as e: print(f"Webhook error: {e}")
    return "OK", 200

@app.route('/api/bot-status')
def get_status(): return jsonify(requests.get(MANAGE_BOT_URL).json())

@app.route('/api/bot-toggle', methods=['POST'])
def toggle():
    active = request.json.get('active')
    return jsonify(requests.get(f"{MANAGE_BOT_URL}?action=toggle&status={1 if active else 0}").json())

@app.route('/api/user-config', methods=['GET', 'POST'])
def u_config():
    if request.method == 'GET': return jsonify(requests.get(SETTINGS_PHP_URL).json())
    return jsonify(requests.post(SETTINGS_PHP_URL, json=request.json).json())

@app.route('/api/env-config', methods=['GET', 'POST'])
def e_config():
    if request.method == 'GET':
        return jsonify({'success': True, 'data': {'supabase_url': os.getenv('SUPABASE_URL', ''), 'supabase_key': os.getenv('SUPABASE_KEY', '')}})
    data = request.json
    set_key(env_path, "SUPABASE_URL", data.get('supabase_url'))
    set_key(env_path, "SUPABASE_KEY", data.get('supabase_key'))
    return jsonify({'success': True})

@app.route('/ask', methods=['POST'])
def ask(): return jsonify({'reply': get_gemini_response(request.json.get('message'))})

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- INTERFAZ GRÁFICA (CustomTkinter) ---

class LooplyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Looply AI - Local Engine")
        self.geometry("400x500")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # UI Elements
        self.label_title = ctk.CTkLabel(self, text="Looply AI Engine", font=("Outfit", 24, "bold"), text_color="#00ff88")
        self.label_title.pack(pady=20)

        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(pady=10, padx=20, fill="x")
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="Estado: Iniciando...", font=("Outfit", 14))
        self.status_label.pack(pady=10)

        self.btn_dashboard = ctk.CTkButton(self, text="Abrir Dashboard HTML", command=self.open_dashboard, fg_color="#9d50bb", hover_color="#7a3e95")
        self.btn_dashboard.pack(pady=10, padx=40, fill="x")

        self.log_box = ctk.CTkTextbox(self, height=200)
        self.log_box.pack(pady=20, padx=20, fill="both", expand=True)
        self.log_box.insert("0.0", "Esperando peticiones...\n")

        # Iniciar Flask en hilo separado
        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()
        
        self.after(2000, self.check_status)

    def open_dashboard(self):
        webbrowser.open("http://localhost:5000")

    def check_status(self):
        try:
            res = requests.get("http://localhost:5000/api/bot-status", timeout=1).json()
            active = res.get('active')
            status_text = "ACTIVO" if active else "APAGADO"
            color = "#00ff88" if active else "#ff4757"
            self.status_label.configure(text=f"Estado del Bot: {status_text}", text_color=color)
        except:
            self.status_label.configure(text="Error de conexión con el motor", text_color="#ff4757")
        self.after(5000, self.check_status)

if __name__ == "__main__":
    gui = LooplyApp()
    gui.mainloop()
