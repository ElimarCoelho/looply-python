import os
import json
import requests
import threading
import traceback
import sqlite3
import logging
import sys
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv, set_key
from supabase import create_client, Client
import google.generativeai as genai
from datetime import datetime

# Configurar logging para Gunicorn
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

load_dotenv()
app = Flask(__name__, static_folder='.')
CORS(app)

# --- CONFIG ---
DB_PATH = '/root/looply-python/msg_deduplication.db'
def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
            conn.commit()
    except Exception as e: logger.error(f"❌ DB INITIALIZATION ERROR: {e}")

init_db()
processed_lock = threading.Lock()

GEMINI_API_KEY_DEFAULT = os.getenv('GEMINI_API_KEY') or "AIzaSyB3a07b-IW0YDEzeuZ6M-whQn7UQW-9lGA"
WASENDER_TOKEN_DEFAULT = os.getenv('WASENDER_TOKEN') or "802f0eb2f10b2dd4776553d81f717a2c50aa70645da57ebdcbf086396ce7bf82"
MANAGE_BOT_URL = 'https://moneymaze.es/apps/looply/manage_bot.php'
SETTINGS_PHP_URL = 'https://moneymaze.es/apps/looply/user_settings.php'
HERR_URL = 'https://moneymaze.es/apps/looply/inventario.php'

OPENAI_API_KEY_DEFAULT = os.getenv('OPENAI_API_KEY')
AI_PROVIDER_DEFAULT = os.getenv('AI_PROVIDER') or 'gemini'

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase successfully connected")
    except Exception as e: logger.error(f"❌ Supabase Connection Failed: {e}")

def clean_phone(raw):
    if not raw: return None
    digits = ''.join(filter(str.isdigit, str(raw)))
    return digits if digits else None

# Caché en memoria para nombres de grupos (evita llamar la API en cada mensaje)
_group_name_cache = {}

def get_group_name(group_jid, token=None):
    """Obtiene el nombre real del grupo de WhatsApp vía la API de WaSender."""
    # Revisar caché primero
    if group_jid in _group_name_cache:
        cached = _group_name_cache[group_jid]
        logger.info(f"📋 Nombre de grupo desde caché: '{cached}' para {group_jid}")
        return cached

    final_token = token or WASENDER_TOKEN_DEFAULT
    if not final_token:
        logger.warning(f"⚠️ get_group_name: Sin token disponible para {group_jid}")
        return None
    try:
        url = f"https://wasenderapi.com/api/groups/{group_jid}/metadata"
        logger.info(f"🌐 Consultando metadata del grupo {group_jid} (token: {final_token[:8]}...)")
        res = requests.get(url, headers={'Authorization': f'Bearer {final_token}'}, timeout=8)
        logger.info(f"🌐 Respuesta metadata grupo: Status {res.status_code}")
        if res.status_code == 200:
            data = res.json().get('data', {})
            name = data.get('subject') or data.get('name')
            if name:
                _group_name_cache[group_jid] = name
                logger.info(f"✅ Nombre del grupo obtenido: '{name}' para {group_jid}")
                return name
            else:
                logger.warning(f"⚠️ API devolvió 200 pero sin subject/name para {group_jid}: {res.json()}")
        else:
            logger.error(f"❌ Error API metadata grupo: {res.status_code} - {res.text[:200]}")
    except Exception as e:
        logger.error(f"❌ Excepción en get_group_name para {group_jid}: {e}")
    return None

def get_dynamic_config():
    config = {
        'gemini_api_key': GEMINI_API_KEY_DEFAULT,
        'openai_api_key': OPENAI_API_KEY_DEFAULT,
        'ai_provider': AI_PROVIDER_DEFAULT,
        'wasender_token': WASENDER_TOKEN_DEFAULT,
        'bot_prompt': None
    }
    try:
        res = requests.get(SETTINGS_PHP_URL, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('success'):
                db_data = data.get('data', {})
                if db_data.get('gemini_api_key'): config['gemini_api_key'] = db_data['gemini_api_key']
                if db_data.get('openai_api_key'): config['openai_api_key'] = db_data['openai_api_key']
                if db_data.get('ai_provider'): config['ai_provider'] = db_data['ai_provider']
                if db_data.get('wasender_token'): config['wasender_token'] = db_data['wasender_token']
                if db_data.get('bot_prompt'): config['bot_prompt'] = db_data['bot_prompt']
    except Exception as e:
        logger.error(f"❌ Error fetching dynamic config: {e}")

    has_gemini = "YES" if config.get('gemini_api_key') else "NO"
    has_openai = "YES" if config.get('openai_api_key') else "NO"
    logger.info(f"⚙️ Config Final -> Gemini: {has_gemini}, OpenAI: {has_openai}")

    return config

def is_bot_active():
    try:
        res = requests.get(MANAGE_BOT_URL, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data.get('active') == 1 or str(data.get('active')) == "1"
    except Exception as e:
        logger.error(f"⚠️ Error verificando estado del bot: {e}")
    return True

def send_whatsapp(to, text, token=None):
    cfg = get_dynamic_config()
    final_token = token or cfg['wasender_token']
    if not final_token:
        logger.error("❌ WaSender Aborted: MISSING TOKEN")
        return False

    to_send = to if '@' in str(to) else clean_phone(to)
    if not to_send:
        logger.error(f"❌ WaSender Aborted: INVALID Recipient ({to})")
        return False

    url = "https://wasenderapi.com/api/send-message"
    headers = {'Authorization': f'Bearer {final_token}', 'Content-Type': 'application/json'}
    payload = {'to': to_send, 'text': text}

    logger.info(f"📤 WaSender START: Attempting to send message to {to_send}")
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        logger.info(f"📬 WaSender RESPONSE: Status {res.status_code} | Body: {res.text[:150]}")
        return res.status_code in [200, 201]
    except Exception as e:
        logger.error(f"❌ WaSender CRITICAL ERROR: {e}")
        return False

def send_typing(to, token=None):
    cfg = get_dynamic_config()
    final_token = token or cfg['wasender_token']
    if not final_token: return False

    to_send = to if '@' in str(to) else clean_phone(to)
    if not to_send: return False
    if '@' not in to_send: to_send = f"{to_send}@s.whatsapp.net"

    url = "https://wasenderapi.com/api/send-presence-update"
    headers = {'Authorization': f'Bearer {final_token}', 'Content-Type': 'application/json'}
    payload = {'jid': to_send, 'presence': 'composing'}

    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
        return True
    except:
        return False

def get_gemini(message, history=None, api_key=None, prompt=None):
    try:
        genai.configure(api_key=api_key or GEMINI_API_KEY_DEFAULT)
        now = datetime.now()
        dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        dia_semana = dias_semana[now.weekday()]
        mes = meses[now.month - 1]
        fecha_contexto = (
            f"Fecha y hora actual: {dia_semana}, {now.day} de {mes} de {now.year}, "
            f"{now.strftime('%H:%M')} horas.\n\n"
        )
        now_str = f"{dia_semana}, {now.day} de {mes} de {now.year}, {now.strftime('%H:%M')}"
        base_prompt = (prompt or "Sé profesional.").replace("{{ $now }}", now_str)
        full_prompt = f"{fecha_contexto}\n\n{base_prompt}"

        model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest', system_instruction=full_prompt)
        chat_history = []
        for h in (history or []):
            role = 'user' if h.get('role') == 'user' else 'model'
            if h.get('content'): chat_history.append({'role': role, 'parts': [h['content']]})
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(message)
        return response.text if response else None
    except Exception as e:
        logger.error(f"❌ GEMINI ERROR: {e}")
        return "Lo siento, hubo un problema."

def get_openai_response(message, history=None, api_key=None, prompt=None):
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or OPENAI_API_KEY_DEFAULT}"
        }

        system_content = prompt or "Sé profesional."
        messages = [{"role": "system", "content": system_content}]

        for h in (history or []):
            role = "user" if h.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": h.get("content", "")})

        messages.append({"role": "user", "content": message})

        payload = {
            "model": "gpt-4o",
            "messages": messages,
            "temperature": 0.7
        }

        res = requests.post(url, json=payload, headers=headers, timeout=60)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        else:
            logger.error(f"❌ OpenAI Error: {res.text}")
            return "Lo siento, hubo un problema con OpenAI."
    except Exception as e:
        logger.error(f"❌ OpenAI Exception: {e}")
        return "Lo siento, hubo un problema."

def get_ai_response(message, history=None, config=None, prompt=None):
    provider = config.get('ai_provider', 'gemini')
    gemini_key = config.get('gemini_api_key')
    openai_key = config.get('openai_api_key')

    if provider == 'openai' and not openai_key and gemini_key:
        logger.info("⚠️ Provider es OpenAI pero falta Key. Cambiando a Gemini automáticamente.")
        provider = 'gemini'
    elif provider == 'gemini' and not gemini_key and openai_key:
        logger.info("⚠️ Provider es Gemini pero falta Key. Cambiando a OpenAI automáticamente.")
        provider = 'openai'
    elif not gemini_key and openai_key:
        provider = 'openai'

    if provider == 'openai' and openai_key:
        logger.info("🤖 Iniciando respuesta con OpenAI (GPT-4o)")
        res = get_openai_response(message, history, openai_key, prompt)
        if "lo siento, hubo un problema" in res.lower() and gemini_key:
            logger.warning("🔄 OpenAI falló, intentando Gemini como backup...")
            return get_gemini(message, history, gemini_key, prompt)
        return res

    if gemini_key:
        logger.info("🤖 Iniciando respuesta con Gemini")
        res = get_gemini(message, history, gemini_key, prompt)
        if "lo siento, hubo un problema" in res.lower() and openai_key:
            logger.warning("🔄 Gemini falló, intentando OpenAI como backup...")
            return get_openai_response(message, history, openai_key, prompt)
        return res

    logger.error("❌ Error: No hay ninguna API Key configurada (Gemini ni OpenAI)")
    return "Lo siento, configura una clave de IA (Gemini o OpenAI) en los ajustes para que pueda responder."


# ─────────────────────────────────────────────
# FUNCIÓN CENTRALIZADA: detectar mensajes basura
# ─────────────────────────────────────────────
def is_placeholder_message(msg, text):
    """
    Devuelve True si el mensaje es un placeholder de WhatsApp que NO debe procesarse.

    Casos cubiertos:
      1. messageStubType presente  → notificación de sistema (añadir al grupo, cambio de nombre, etc.)
      2. type == 'protocol'        → mensaje de protocolo interno de WhatsApp
      3. Texto contiene patrones de "mensaje en espera" en ES/EN
         — "Esperando el mensaje"  (WhatsApp Desktop, español)
         — "Waiting for this message" (WhatsApp Desktop, inglés)
         — "Revisa tu teléfono" / "Revisa tu telefono"
         — "This message was deleted" / "Este mensaje fue eliminado"
         — Otros marcadores de cifrado
    """
    # 1. Stub / protocol
    if msg.get('messageStubType') is not None:
        return True
    if msg.get('type') == 'protocol':
        return True

    # 2. Patrones de texto  (todo en minúsculas para comparación)
    text_lower = text.lower()
    placeholder_patterns = [
        # --- Español ---
        "esperando el mensaje",       # ← BUG ORIGINAL: "esperando mensaje" no matcheaba esto
        "esperando mensaje",
        "revisa tu teléfono",
        "revisa tu telefono",
        "este mensaje fue eliminado",
        "esto puede tomar tiempo",
        "más información",
        # --- Inglés ---
        "waiting for this message",
        "this may take a while",
        "this message was deleted",
        "learn more",
        # --- Técnicos ---
        "cipher",
        "decryption",
        "@628",                        # artefacto de número de grupo en algunos payloads
    ]

    for pattern in placeholder_patterns:
        if pattern in text_lower:
            return True

    return False


# --- WEBHOOK ---

@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    try:
        body = request.json
        if not body:
            logger.warning("📩 Incoming Webhook IGNORED: Empty Body")
            return "OK", 200

        logger.info(f"📩 Webhook INCOMING: Evento={body.get('event', 'unknown')} | BodyLen={len(str(body))}")

        def process_task(payload):
            try:
                # 1. Extracción de Datos
                data = payload.get('data', {})
                messages = data.get('messages')
                msg = messages[0] if isinstance(messages, list) and messages else (messages if isinstance(messages, dict) else (data if data.get('key') else None))

                if not msg:
                    logger.warning("⚠️ Extracción fallida: No se encontró el objeto de mensaje en el payload")
                    return

                key = msg.get('key', {})
                if key.get('fromMe'):
                    logger.info("ℹ️ Mensaje ignorado: de origen propio (fromMe:True)")
                    return

                msg_id = key.get('id')
                remote_jid = key.get('remoteJid', '')
                participant = key.get('participant') or msg.get('participant')
                is_group = '@g.us' in remote_jid or participant is not None

                sender_raw = key.get('participant') or key.get('cleanedParticipantPn') or key.get('cleanedSenderPn') or remote_jid
                sender_id = clean_phone(sender_raw.split('@')[0])

                text = (
                    msg.get('messageBody') or
                    msg.get('message', {}).get('conversation') or
                    msg.get('message', {}).get('extendedTextMessage', {}).get('text') or
                    msg.get('message', {}).get('text', {}).get('body') or
                    msg.get('message', {}).get('imageMessage', {}).get('caption') or
                    ''
                ).strip()

                if not text:
                    logger.info("ℹ️ Mensaje ignorado: No tiene contenido textual")
                    return

                # ── FILTRO MEJORADO: placeholder / "Esperando el mensaje" ──
                if is_placeholder_message(msg, text):
                    logger.info(f"ℹ️ Mensaje placeholder/sistema IGNORADO: '{text[:60]}'")
                    return

                # Deduplicación
                try:
                    with processed_lock:
                        with sqlite3.connect(DB_PATH, timeout=5) as conn:
                            conn.execute('INSERT INTO messages (msg_id) VALUES (?)', (msg_id,))
                            conn.commit()
                except sqlite3.IntegrityError:
                    logger.info(f"ℹ️ Mensaje duplicado OMITIDO: {msg_id}")
                    return
                except Exception as e:
                    logger.warning(f"⚠️ Error SQLite (Deduplicación): {e}")

                logger.info(f"📥 PROCESANDO: {sender_id} | {text[:50]}...")

                # VERIFICAR SI EL BOT ESTÁ ENCENDIDO
                if not is_bot_active():
                    logger.info(f"⏹️ Bot APAGADO (Status 0): Ignorando mensaje de {sender_id}")
                    return

                cfg = get_dynamic_config()

                logger.info(f"🔍 DEBUG: msg_id={msg_id} | is_group={is_group} | remote_jid={remote_jid} | sender_id={sender_id}")

                if is_group:
                    # GUARDAR SIEMPRE EN GROUP_DATA PARA ANÁLISIS DE PRESUPUESTOS
                    if supabase:
                        try:
                            # EL NOMBRE DEL GRUPO (LA OBRA)
                            # 1. Intentar obtenerlo del payload (raro en WaSender pero posible)
                            g_name = data.get('groupName') or payload.get('groupName') or data.get('name')
                            
                            # 2. Verificar que el nombre no sea un JID ni placeholder
                            if not g_name or '@' in str(g_name) or g_name == 'Grupo WhatsApp':
                                logger.info(f"🔍 Nombre de grupo en payload: '{g_name}' → consultando API de WaSender para {remote_jid}...")
                                # Usar el token dinámico (el de la BD remota), NO el hardcodeado
                                api_token = cfg.get('wasender_token')
                                logger.info(f"🔑 Token para metadata: {api_token[:8] if api_token else 'NONE'}...")
                                g_name = get_group_name(remote_jid, api_token)
                            
                            # 3. Fallback final: nunca guardar None
                            if not g_name:
                                g_name = f"Grupo {remote_jid.split('@')[0]}"
                                logger.warning(f"⚠️ No se pudo obtener nombre real del grupo {remote_jid}, usando fallback: {g_name}")
                            
                            logger.info(f"📝 Nombre del grupo a guardar: '{g_name}'")
                            
                            row_group = {
                                'group_id': remote_jid,
                                'sender_id': sender_id,
                                'sender_name': msg.get('pushName') or sender_id, # Nombre de la persona
                                'message_text': text,
                                'group_name': g_name, # Nombre del grupo/obra
                                'created_at': datetime.now().isoformat(),
                                'metadata': {
                                    'msg_id': msg_id,
                                    'participant': participant
                                }
                            }
                            supabase.table('group_data').insert(row_group).execute()
                            logger.info(f"✅ Mensaje de GRUPO guardado en group_data ({remote_jid}) - Obra: {g_name}")
                        except Exception as e:
                            logger.error(f"❌ Error guardando en group_data: {e}\n{traceback.format_exc()}")

                    # Lógica de respuesta automática si se desea (opcional)
                    if 'lista de materiales' in text.lower():
                        logger.info(f"📦 Detectada 'Lista de materiales' en {remote_jid}")
                        send_typing(remote_jid, cfg['wasender_token'])
                        send_whatsapp(remote_jid, "✅ Entendido. He registrado estos materiales para la auditoría de presupuesto. 🏗️", cfg['wasender_token'])

                else:
                    # FLUJO PRIVADOS
                    history = []
                    knowledge = ""

                    if supabase:
                        try:
                            search_id = str(sender_id)
                            kb_res = supabase.table('base_conocimiento').select('knowledge_base').eq('phone_number', search_id).execute()

                            if not kb_res.data and len(search_id) > 9:
                                suffix = search_id[-9:]
                                logger.info(f"🔍 No hay match total con {search_id}, intentando con sufijo: {suffix}")
                                kb_res = supabase.table('base_conocimiento').select('knowledge_base').eq('phone_number', suffix).execute()

                            if kb_res.data:
                                knowledge = kb_res.data[0].get('knowledge_base', '')
                                logger.info(f"🧠 Base de conocimiento ACTIVADA para {sender_id}")
                            else:
                                logger.info(f"❓ Sin base de conocimiento para {sender_id}")

                            hist_res = supabase.table('conversations').select('role, content').eq('whatsapp_id', str(sender_id)).order('created_at', desc=True).execute()
                            history = list(reversed(hist_res.data or []))
                            logger.info(f"📚 Historial cargado: {len(history)} mensajes para {sender_id}")

                            supabase.table('conversations').insert({
                                'whatsapp_id': str(sender_id),
                                'role': 'user',
                                'content': text,
                                'metadata': {'msg_id': msg_id},
                                'created_at': datetime.now().isoformat()
                            }).execute()
                        except Exception as e:
                            logger.error(f"❌ Error Supabase (Privados): {e}")

                    base_personality = cfg.get('bot_prompt') or "Sé profesional."

                    if knowledge:
                        logger.info(f"💡 Aplicando Base de Conocimiento al Agente para {sender_id}")
                        custom_prompt = (
                            f"TU IDENTIDAD Y REGLAS (ASISTENTE COMERCIAL):\n"
                            f"{base_personality}\n\n"
                            f"DATOS DEL CLIENTE CON EL QUE ESTÁS HABLANDO (NO ERES TÚ):\n"
                            f"IMPORTANTE: La siguiente información describe el negocio del CLIENTE/LEAD. "
                            f"Usa estos datos para entender sus puntos débiles y venderle nuestras soluciones. "
                            f"NUNCA digas que eres de esta empresa externa. Tú eres el asistente de venta contactando a esta empresa:\n"
                            f"-------------------------------------------\n"
                            f"{knowledge}\n"
                            f"-------------------------------------------\n"
                        )
                    else:
                        custom_prompt = base_personality

                    send_typing(remote_jid, cfg['wasender_token'])

                    ia_rep = get_ai_response(text, history, cfg, custom_prompt)

                    if ia_rep:
                        if supabase:
                            try:
                                supabase.table('conversations').insert({
                                    'whatsapp_id': str(sender_id),
                                    'role': 'agent',
                                    'content': ia_rep,
                                    'created_at': datetime.now().isoformat()
                                }).execute()
                                logger.info(f"✅ Respuesta IA GUARDADA en Supabase para {sender_id}")
                            except Exception as e: logger.error(f"❌ Error Supabase (Guardado IA): {e}")

                        success = send_whatsapp(sender_id, ia_rep, cfg['wasender_token'])
                        if success:
                            logger.info(f"✅ FIN: Mensaje enviado con éxito a {sender_id}")
                        else:
                            logger.error(f"❌ FIN: Fallo el envío final a {sender_id}")
                    else:
                        logger.warning(f"⚠️ IA no devolvió respuesta para {sender_id}")

            except Exception as e:
                logger.error(f"❌ TASK EXECUTION FAILED: {e}\n{traceback.format_exc()}")

        threading.Thread(target=process_task, args=(body,), daemon=True).start()

    except Exception as e:
        logger.error(f"❌ WEBHOOK ROOT ERROR: {e}")

    return "OK", 200


# --- DASHBOARD APIS ---
@app.route('/')
def home(): return send_from_directory('.', 'dashboard_new.html')

@app.route('/imagen/<path:filename>')
def serve_imagen(filename):
    return send_from_directory('imagen', filename)

@app.route('/descargar_proyecto')
def download(): return send_file('looply_python_production.zip', as_attachment=True)

@app.route('/api/bot-status')
def bot_status_route():
    try:
        active = is_bot_active()
        return jsonify({'success': True, 'active': 1 if active else 0})
    except:
        return jsonify({'success': True, 'active': 1})

@app.route('/api/bot-toggle', methods=['POST'])
def bot_toggle_route():
    active = request.json.get('active', False)
    requests.get(f"{MANAGE_BOT_URL}?action=toggle&status={1 if active else 0}", timeout=5)
    return jsonify({'success': True})

@app.route('/api/user-config', methods=['GET', 'POST'])
def user_cfg_route():
    try:
        if request.method == 'GET': return jsonify(requests.get(SETTINGS_PHP_URL).json())
        return jsonify(requests.post(SETTINGS_PHP_URL, json=request.json).json())
    except: return jsonify({'error': 'Config Error'})

@app.route('/api/env-config', methods=['GET', 'POST'])
def env_cfg_route():
    env_p = os.path.join(os.path.dirname(__file__), '.env')
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'data': {
                'supabase_url': os.getenv('SUPABASE_URL', ''),
                'supabase_key': os.getenv('SUPABASE_KEY', ''),
                'gemini_api_key': os.getenv('GEMINI_API_KEY', ''),
                'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
                'ai_provider': os.getenv('AI_PROVIDER', 'gemini'),
                'wasender_token': os.getenv('WASENDER_TOKEN', '')
            }
        })
    else:
        d = request.json or {}
        set_key(env_p, "SUPABASE_URL", d.get('supabase_url', ''))
        set_key(env_p, "SUPABASE_KEY", d.get('supabase_key', ''))
        set_key(env_p, "GEMINI_API_KEY", d.get('gemini_api_key', ''))
        set_key(env_p, "OPENAI_API_KEY", d.get('openai_api_key', ''))
        set_key(env_p, "AI_PROVIDER", d.get('ai_provider', 'gemini'))
        set_key(env_p, "WASENDER_TOKEN", d.get('wasender_token', ''))
        for k in ["SUPABASE_URL", "SUPABASE_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_PROVIDER", "WASENDER_TOKEN"]:
            if d.get(k.lower()): os.environ[k] = d[k.lower()]
        return jsonify({'success': True})

@app.route('/api/save-knowledge', methods=['POST'])
def save_knowledge_route():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    data = request.json
    phone = clean_phone(data.get('phone_number'))
    kb = data.get('knowledge_base', '')

    if not phone: return jsonify({'error': 'Phone number required'}), 400

    try:
        res = supabase.table('base_conocimiento').upsert({
            'phone_number': phone,
            'knowledge_base': kb,
            'updated_at': datetime.now().isoformat()
        }, on_conflict='phone_number').execute()
        return jsonify({'success': True, 'data': res.data})
    except Exception as e:
        logger.error(f"Error saving KB: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-knowledge', methods=['GET'])
def get_knowledge_route():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    phone_raw = request.args.get('phone_number')
    try:
        if phone_raw == 'all':
            # Recuperar todos los perfiles para el directorio
            res = supabase.table('base_conocimiento').select('*').order('created_at', desc=True).execute()
            return jsonify({'success': True, 'data': res.data})
        
        phone = clean_phone(phone_raw)
        if not phone: return jsonify({'error': 'Phone number required'}), 400
        
        # Buscar perfil específico
        res = supabase.table('base_conocimiento').select('*').eq('phone_number', phone).execute()
        return jsonify({'success': True, 'data': res.data[0] if res.data else None})
    except Exception as e:
        logger.error(f"❌ Error en get_knowledge: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_route():
    m = request.json.get('message', '')
    c = get_dynamic_config()
    return jsonify({'reply': get_ai_response(m, [], c, c['bot_prompt'])})

@app.route('/api/chats', methods=['GET'])
def get_chats_route():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    try:
        res = supabase.table('conversations').select('*').order('created_at', desc=True).limit(200).execute()

        unique_chats = {}
        for msg in res.data:
            wid = msg.get('whatsapp_id')
            if wid and wid not in unique_chats:
                unique_chats[wid] = msg

        return jsonify({'success': True, 'data': list(unique_chats.values())})
    except Exception as e:
        logger.error(f"Error fetching chats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/<whatsapp_id>', methods=['GET'])
def get_contact_messages_route(whatsapp_id):
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    try:
        res = supabase.table('conversations').select('*').eq('whatsapp_id', whatsapp_id).order('created_at', desc=False).execute()
        return jsonify({'success': True, 'data': res.data})
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tools/analyze', methods=['POST'])
def analyze_tool_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    img_bytes = file.read()

    import uuid
    import os
    os.makedirs('imagen/tools', exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    with open(f"imagen/tools/{filename}", "wb") as f:
        f.write(img_bytes)
    image_url = f"/imagen/tools/{filename}"

    config = get_dynamic_config()
    gemini_key = config.get('gemini_api_key')
    openai_key = config.get('openai_api_key')

    prompt_user = (
        "Necesito catalogar esta herramienta para mi inventario de obra. "
        "Por favor, describe lo que ves en la imagen y completa esta ficha técnica en formato JSON: "
        "{ \"name\": \"tipo de herramienta\", \"brand\": \"fabricante\", \"model\": \"referencia o modelo si es visible\", \"color\": \"color principal\", \"category\": \"categoría (Eléctrica, Manual, Medición, etc.)\" }. "
        "Si algún dato no es visible, escribe 'No visible'. Responde SOLO con el JSON."
    )

    prompt_system = (
        "Eres un asistente de gestión de inventario para una empresa de construcción. "
        "Tu trabajo es ayudar a catalogar herramientas y equipos a partir de fotos que los empleados suben. "
        "Debes extraer la información visible de cada herramienta para rellenar fichas de inventario."
    )

    logger.info(f"🔍 Análisis Iniciado - Gemini Key: {'Valid' if gemini_key else 'None'}, OpenAI Key: {'Valid' if openai_key else 'None'}")

    if gemini_key:
        try:
            import google.generativeai as genai
            from PIL import Image
            from io import BytesIO
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            img = Image.open(BytesIO(img_bytes))
            response = model.generate_content([prompt_user, img])
            raw_json = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(raw_json)
            data['image_url'] = image_url
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            logger.error(f"⚠️ Fallo Gemini: {e}")

    if openai_key:
        try:
            import base64
            base64_image = base64.b64encode(img_bytes).decode('utf-8')

            headers = {
                'Authorization': f'Bearer {openai_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': 'gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': prompt_system},
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': prompt_user},
                            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{base64_image}'}}
                        ]
                    }
                ],
                'max_tokens': 500
            }

            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                resp_data = response.json()
                content = resp_data['choices'][0]['message']['content']
                refusal = resp_data['choices'][0]['message'].get('refusal')
                logger.info(f"✅ OpenAI respondió: {content[:200] if content else 'NONE'}")
                if refusal:
                    logger.error(f"⚠️ OpenAI rechazó la petición: {refusal}")
                elif content:
                    clean = content.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean)
                    data['image_url'] = image_url
                    return jsonify({'success': True, 'data': data})
                else:
                    logger.error(f"⚠️ OpenAI content vacío")
            else:
                logger.error(f"⚠️ OpenAI API error: {response.status_code} - {response.text[:300]}")
        except Exception as e:
            logger.error(f"⚠️ Fallo OpenAI Vision: {e}")

    return jsonify({'error': 'No hay API keys configuradas válidas para el análisis'}), 500

@app.route('/api/tools/save', methods=['POST'])
def save_tool_data():
    try:
        HERR_URL = "https://moneymaze.es/apps/looply/inventario.php"
        data = request.json
        res = requests.post(HERR_URL, json=data, timeout=10)
        return jsonify(res.json())
    except Exception as e:
        logger.error(f"❌ Error guardando herramienta en MoneyMaze: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tools/list', methods=['GET'])
def list_tool_data():
    try:
        HERR_URL = "https://moneymaze.es/apps/looply/inventario.php"
        res = requests.get(HERR_URL, timeout=10)
        return jsonify(res.json())
    except Exception as e:
        logger.error(f"❌ Error listando desde MoneyMaze: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/groups/list', methods=['GET'])
def list_groups():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    try:
        # Obtenemos grupos de la tabla group_data
        res = supabase.table('group_data').select('group_id, group_name').execute()
        
        # Eliminamos duplicados y nulos de forma eficiente
        groups_dict = {}
        for row in res.data:
            gid = row.get('group_id')
            # Priorizar el nombre real si existe, sino el ID
            gname = row.get('group_name')
            if not gname or '@' in str(gname) or 'Obra ' in str(gname):
                # Si el nombre guardado es el JID o nulo, usamos el ID como clave
                # pero el dashboard mostrará 'id' si name no es convincente
                pass 
            
            if gid and gid not in groups_dict:
                groups_dict[gid] = gname or gid
            elif gid and gname and gname != gid and not gname.startswith('1203'):
                # Si encontramos un nombre mejor (no ID), actualizamos
                groups_dict[gid] = gname
        
        data_list = [{'id': k, 'name': v} for k, v in groups_dict.items()]
        return jsonify({'success': True, 'data': data_list})
    except Exception as e:
        logger.error(f"❌ Error en list_groups: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fix-groups', methods=['GET'])
def fix_groups():
    """Endpoint manual para forzar la corrección de nombres de grupos en la BD"""
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    try:
        cfg = get_dynamic_config()
        token = cfg.get('wasender_token')
        
        # Obtener IDs únicos
        res = supabase.table('group_data').select('group_id').execute()
        unique_jids = list(set([r['group_id'] for r in res.data if r.get('group_id')]))
        
        results = []
        for jid in unique_jids:
            real_name = get_group_name(jid, token)
            if real_name and not real_name.startswith('Grupo '):
                # Actualizar en Supabase
                upd = supabase.table('group_data').update({'group_name': real_name}).eq('group_id', jid).execute()
                results.append({'jid': jid, 'new_name': real_name, 'updated': len(upd.data)})
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/budgets/compare', methods=['POST'])
def compare_budget():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    
    csv_file = request.files.get('file')
    whatsapp_id = request.form.get('whatsapp_id')
    start_date = request.form.get('start_date') or "No definida"
    end_date = request.form.get('end_date') or "No definida"
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    if not csv_file or not whatsapp_id:
        return jsonify({'error': 'Missing file or whatsapp_id'}), 400
        
    csv_content = csv_file.read().decode('utf-8')
    
    # 1. Obtener historial con fechas desde group_data (Limitado a 100 mensajes para evitar SIGKILL/OOM)
    try:
        hist_res = supabase.table('group_data').select('message_text, created_at').eq('group_id', whatsapp_id).order('created_at', desc=True).limit(100).execute()
        # Invertir para que estén en orden cronológico ascendente
        sorted_data = sorted(hist_res.data, key=lambda x: x['created_at'])
        chat_context = "\n".join([f"[{msg['created_at'][:10]}] {msg['message_text']}" for msg in sorted_data if msg.get('message_text')])
    except Exception as e:
        logger.error(f"❌ Error fetching chat history from group_data: {e}")
        return jsonify({'error': f"Error fetching chat history: {e}"}), 500
        
    # 1.5. Pre-procesar CSV en Python para calcular el Total exacto
    # 1.5. Pre-procesar CSV en Python de forma 100% DINÁMICA
    import csv, io
    python_calculated_total = 0
    csv_headers = []
    csv_rows = []
    try:
        f = io.StringIO(csv_content)
        first_line = f.readline()
        f.seek(0)
        delim = '\t' if '\t' in first_line else (';' if ';' in first_line else ',')
        
        reader = csv.DictReader(f, delimiter=delim)
        csv_headers = reader.fieldnames or []
        for row in reader:
            csv_rows.append(row)
            try:
                item_total = 0
                qty = 0
                price = 0
                for k, v in row.items():
                    if not k or not v: continue
                    k_low = k.lower()
                    v_clean = str(v).replace(',', '.').replace('€', '').strip()
                    if 'total' in k_low: 
                        try: item_total = float(v_clean)
                        except: pass
                    if 'cant' in k_low: 
                        qty = float(v_clean)
                    if 'precio' in k_low or 'unit' in k_low: 
                        price = float(v_clean)
                
                if item_total > 0: python_calculated_total += item_total
                elif qty > 0 and price > 0: python_calculated_total += (qty * price)
            except: pass
    except Exception as e:
        logger.warning(f"⚠️ Dynamic CSV Pre-process failed: {e}")

    # 2. IA con Interpretación de Archivo Dinámico
    config = get_dynamic_config()
    prompt = f"""
    Eres un AUDITOR JEFE experto en descifrar tablas de construcción.
    TE HE PASADO UN DOCUMENTO CSV Y UN HISTORIAL DE CHAT.

    PRESUPUESTO TOTAL CALCULADO: {python_calculated_total:.2f} €.

    ESTRUCTURA DEL CSV:
    {csv_content}

    WHATSAPP:
    {chat_context}

    REGLAS:
    1. Usa TODAS las columnas del CSV para identificar cada material (Partida, Unidad, etc.).
    2. Cruza con los pedidos de WhatsApp para calcular 'requested_qty'.
    
    DEVOLVER JSON:
    {{
      "headers": {json.dumps(csv_headers)},
      "summary": {{ 
        "total_budget": {python_calculated_total:.2f}, 
        "total_spent": 0, 
        "remaining": 0, 
        "consumption_percentage": 0 
      }},
      "ai_insights": ["Insight 1", "Insight 2", ...],
      "top_risks": [
        {{ "item": "Nombre del riesgo", "reason": "Por qué es un riesgo", "severity": "high/medium" }}
      ],
      "items": [
        {{ 
          "original_row": {{ ... }}, // Copia exacta de la fila del CSV
          "requested_qty": 0, 
          "total_requested": 0, 
          "progress": 0, 
          "status": "ok/alerta/critico", 
          "notes": "explicación" 
        }}
      ]
    }}
    Responde UNICAMENTE el JSON.
    """
    
    res_ai = get_ai_response(prompt, [], config, "Eres un experto en logística de obras.")
    try:
        clean_json = res_ai.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_json)
        return jsonify({'success': True, 'data': data})
    except:
        return jsonify({'error': 'La IA no pudo procesar la comparación correctamente', 'raw': res_ai}), 500


@app.route('/api/groups/requests', methods=['GET'])
def list_group_requests():
    if not supabase: return jsonify({'error': 'Supabase not connected'}), 500
    group_id = request.args.get('group_id')
    if not group_id: return jsonify({'error': 'Missing group_id'}), 400
    
    try:
        # Buscamos historial en group_data
        res = supabase.table('group_data').select('message_text').eq('group_id', group_id).execute()
        chat_context = "\n".join([msg['message_text'] for msg in res.data if msg.get('message_text')])
        
        if not chat_context.strip():
            return jsonify({'success': True, 'data': []})
            
        config = get_dynamic_config()
        prompt = f"""
        Analiza este historial de chat de una obra y extrae una lista JSON de todos los materiales que han sido solicitados.
        HISTORIAL:
        {chat_context}
        
        FORMATO JSON ESPERADO:
        [{{ "item": "Nombre material", "qty": 0, "unit": "uds/kg/etc", "date": "YYYY-MM-DD" }}]
        Responde SOLO con el JSON.
        """
        
        res_ai = get_ai_response(prompt, [], config, "Eres un gestor de almacén de obra.")
        clean_json = res_ai.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_json)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"❌ Error en list_group_requests: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)