@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """
    Webhook para recibir mensajes de WhatsApp desde WaSender
    """
    try:
        body = request.json
        if not body:
            logger.warning("📩 Recibida petición POST vacía o no JSON en /webhook/whatsapp")
            return "No body", 400

        event = body.get('event')
        logger.info(f"📩 Webhook Recibido: {event}")

        def process_message(payload):
            try:
                data = payload.get('data', {})
                event_type = payload.get('event')

                logger.info(f"📥 Procesando evento '{event_type}' - Payload: {json.dumps(payload)[:200]}...")
                
                # Verificar si el bot está activo
                if not is_bot_active():
                    logger.warning('⏹️ Bot desactivado (moneymaze.es)')
                    return

                if event_type not in ['messages.upsert', 'message.received', 'messages.received', 'messages-group.received']:
                    logger.info(f"⏭️ Evento '{event_type}' no procesable, ignorando")
                    return

                # Extraer el primer mensaje (WaSender suele enviar una lista)
                messages = data.get('messages')
                if isinstance(messages, list) and len(messages) > 0:
                    msg = messages[0]
                elif isinstance(messages, dict):
                    msg = messages
                else:
                    logger.warning(f"⚠️ Estructura de 'messages' inesperada: {type(messages)}")
                    return

                # No procesar mensajes propios
                if msg.get('key', {}).get('fromMe', False):
                    logger.info("ℹ️ Mensaje propio recibido, ignorando")
                    return

                # Deduplicación: ignorar si ya procesamos este mensaje
                msg_id = msg.get('key', {}).get('id', '')
                if msg_id:
                    try:
                        with processed_lock:
                            conn = sqlite3.connect(DB_PATH, timeout=10)
                            try:
                                conn.execute('INSERT INTO messages (msg_id) VALUES (?)', (msg_id,))
                                conn.commit()
                            except sqlite3.IntegrityError:
                                logger.info(f"⚠️ Mensaje duplicado ignorado (SQLite): {msg_id}")
                                conn.close()
                                return
                            finally:
                                if conn: conn.close()
                    except Exception as db_err:
                        logger.error(f"⚠️ Error en deduplicación SQLite: {db_err}")

                # Extraer información del mensaje
                remote_jid = msg.get('key', {}).get('remoteJid', '')
                is_group = '@g.us' in remote_jid

                # Extraer ID del remitente
                key_data = msg.get('key', {})
                sender_id = (
                        key_data.get('cleanedSenderPn') or
                        key_data.get('cleanedParticipantPn') or
                        key_data.get('participant')
                )

                if is_group and sender_id:
                    sender_id = sender_id.split('@')[0]

                # Extraer texto del mensaje
                message_text = (
                        msg.get('messageBody') or
                        msg.get('message', {}).get('conversation') or
                        msg.get('message', {}).get('extendedTextMessage', {}).get('text') or
                        msg.get('message', {}).get('text', {}).get('body') or
                        msg.get('message', {}).get('imageMessage', {}).get('caption') or
                        ''
                )

                # Determinar el ID del chat destino
                target_id = remote_jid if is_group else (sender_id or remote_jid.split('@')[0])

                if not target_id or not message_text:
                    logger.warning("⚠️ Mensaje vacío o sin ID de destino")
                    return

                # ===== OBTENER CONFIGURACIÓN DEL USUARIO =====
                user_config = {
                    'gemini_api_key': None,
                    'wasender_token': None,
                    'bot_prompt': None
                }
                try:
                    logger.info(f"🌐 Consultando configuración dinámica en: {SETTINGS_PHP_URL}")
                    config_res = requests.get(SETTINGS_PHP_URL, timeout=5)
                    if config_res.status_code == 200:
                        config_json = config_res.json()
                        if config_json.get('success'):
                            user_config = config_json.get('data', user_config)
                            db_key = user_config.get('gemini_api_key')
                            if db_key:
                                logger.info(f"✅ Key recuperada de base de datos: {db_key[:8]}...")
                            else:
                                logger.warning("⚠️ DB devolvió éxito pero sin gemini_api_key")
                        else:
                            logger.warning(f"⚠️ Bridge de configuración devolvió éxito false")
                    else:
                        logger.error(f"❌ Bridge de configuración con código HTTP {config_res.status_code}")
                except Exception as e:
                    logger.error(f"⚠️ Error obteniendo configuración de DB: {e}")

                push_name = msg.get('pushName') or sender_id or 'Usuario'
                group_name = push_name  # Default fallback

                if is_group:
                    # Intentar obtener el nombre del grupo real vía API de WaSender
                    try:
                        was_token = user_config.get('wasender_token') or WASENDER_TOKEN_DEFAULT
                        if was_token:
                            meta_url = f"https://wasenderapi.com/api/groups/{remote_jid}/metadata"
                            meta_headers = {'Authorization': f'Bearer {was_token}'}
                            meta_res = requests.get(meta_url, headers=meta_headers, timeout=5)
                            if meta_res.status_code == 200:
                                meta_json = meta_res.json()
                                m_data = meta_json.get('data', {})
                                group_name = m_data.get('subject') or m_data.get('name') or meta_json.get('subject') or group_name
                                logger.info(f"🏢 Grupo: {group_name}")
                    except Exception as meta_err:
                        logger.error(f"⚠️ Error metadata grupo: {meta_err}")

                logger.info(f"💬 Mensaje recibido ({target_id}): '{message_text[:60]}'")

                if not supabase:
                    logger.error("❌ Supabase no disponible")
                    return


                # ===== FLUJO GRUPOS → group_data =====
                if is_group:
                    if 'lista de materiales' not in message_text.lower():
                        logger.info(f"⏭️ Mensaje de grupo ignorado")
                        return

                    try:
                        group_jid = remote_jid

                        # Deduplicación en Supabase
                        check_res = supabase.table('group_data').select('id').filter('metadata->>msg_id', 'eq', msg_id).execute()
                        if check_res.data:
                            logger.info(f"⚠️ Mensaje duplicado en Supabase")
                            return

                        # Guardar mensaje del usuario
                        supabase.table('group_data').insert({
                            'group_id': group_jid,
                            'sender_id': sender_id or push_name,
                            'sender_name': push_name,
                            'group_name': group_name,
                            'message_text': message_text,
                            'metadata': {'role': 'user', 'msg_id': msg_id},
                            'created_at': datetime.now().isoformat()
                        }).execute()

                        ia_reply = (
                            f"✅ ¡Gracias, {push_name}! "
                            f"Tu pedido ha sido recibido correctamente en el grupo {group_name}. 🏗️"
                        )

                        # Guardar respuesta del bot
                        supabase.table('group_data').insert({
                            'group_id': group_jid,
                            'sender_id': 'bot',
                            'sender_name': 'Bot',
                            'group_name': group_name,
                            'message_text': ia_reply,
                            'metadata': {'role': 'agent'},
                            'created_at': datetime.now().isoformat()
                        }).execute()

                        # Enviar respuesta
                        send_whatsapp_message(remote_jid, ia_reply, user_config.get('wasender_token'))

                    except Exception as e:
                        logger.error(f'❌ Error en flujo grupos: {e}')

                # ===== FLUJO PRIVADOS → conversations =====
                else:
                    try:
                        # Lead
                        res = supabase.table('leads').select('id').eq('whatsapp_id', str(target_id)).execute()
                        lead = res.data[0] if res.data else None
                        if not lead:
                            res = supabase.table('leads').insert({'whatsapp_id': str(target_id), 'platform': 'whatsapp'}).execute()
                            lead = res.data[0] if res.data else None

                        if not lead: return

                        lead_id = lead.get('id')

                        # Historial
                        res = supabase.table('conversations').select('role, content').eq('lead_id', lead_id).order('created_at').limit(10).execute()
                        history = res.data or []

                        # Guardar mensaje usuario
                        try:
                            supabase.table('conversations').insert({
                                'lead_id': lead_id,
                                'role': 'user',
                                'whatsapp_id': str(target_id),
                                'content': message_text,
                                'metadata': {'msg_id': msg_id},
                                'created_at': datetime.now().isoformat()
                            }).execute()
                        except Exception as e:
                            logger.error(f"⚠️ Error guardando en conversations: {e}")

                        # Respuesta IA
                        ia_reply = get_gemini_response(message_text, history, user_config.get('gemini_api_key'), user_config.get('bot_prompt'))
                        
                        if ia_reply:
                            try:
                                supabase.table('conversations').insert({
                                    'lead_id': lead_id,
                                    'role': 'agent',
                                    'whatsapp_id': str(target_id),
                                    'content': ia_reply,
                                    'metadata': {'role': 'agent'},
                                    'created_at': datetime.now().isoformat()
                                }).execute()
                            except Exception as e:
                                logger.error(f"⚠️ Error guardando respuesta IA: {e}")
                            
                            # Enviar respuesta
                            send_whatsapp_message(f"+{target_id}", ia_reply, user_config.get('wasender_token'))

                    except Exception as e:
                        logger.error(f'❌ Error en flujo privado: {e}')

            except Exception as e:
                logger.error(f'❌ Error general en process_message: {e}')

        # Lanzar proceso en segundo plano
        thread = threading.Thread(target=process_message, args=(body,))
        thread.daemon = True
        thread.start()

    except Exception as e:
        logger.error(f"⚠️ Error crítico en whatsapp_webhook: {e}")

    return "OK", 200
