# 🤖 Looply Bot - WhatsApp Automation with AI

Bot inteligente para automatizar conversaciones en WhatsApp usando IA (Gemini) y almacenamiento en Supabase.

## ✨ Características Principales

- 🤖 **IA Conversacional**: Responde automáticamente con Google Gemini
- 💬 **WhatsApp Integration**: Recibe y envía mensajes vía WaSender
- 📊 **Base de Datos**: Almacena conversaciones en Supabase
- 🎛️ **Dashboard**: Control visual del bot en tiempo real
- 🔄 **Historial**: Mantiene contexto de conversaciones anteriores
- 👥 **Multi-lead**: Gestiona múltiples clientes simultáneamente
- 📱 **Grupos y Chats**: Funciona en ambos tipos de conversaciones
- 🔐 **Seguro**: Variables de entorno para credenciales

## 🚀 Quick Start

### 1. Instalación
```bash
# Clonar proyecto
git clone <tu-repo>
cd looply-bot

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración
```bash
# Copiar y editar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales
```

### 3. Ejecutar
```bash
python app.py
```

Abre: http://localhost:8080

## 📖 Documentación Completa

Para una guía paso a paso de instalación, ve a [SETUP.md](./SETUP.md)

## 🏗️ Arquitectura

```
Usuario WhatsApp
        ↓
    WaSender API
        ↓
    Flask Server (app.py)
        ↓
    ├─→ Supabase (guardar datos)
    └─→ Google Gemini (generar respuesta)
        ↓
    WaSender API
        ↓
    Usuario WhatsApp (respuesta)
```

## 📁 Archivos Principales

| Archivo | Descripción |
|---------|-------------|
| `app.py` | Backend Flask con toda la lógica |
| `dashboard_new.html` | Frontend para controlar el bot |
| `.env` | Variables de entorno (secretos) |
| `requirements.txt` | Dependencias Python |
| `SETUP.md` | Guía completa de instalación |

## 🔄 Flujo de Funcionamiento

### Recibir Mensaje
1. WaSender envía POST a `/webhook/whatsapp`
2. Se extrae texto, remitente e ID de chat
3. Se crea o busca el "lead" en Supabase
4. Se guarda el mensaje del usuario

### Procesar y Responder
5. Se obtiene historial de conversación anterior
6. Se envía a Google Gemini con el contexto
7. Gemini genera una respuesta personalizada
8. Se guarda la respuesta en Supabase
9. Se envía la respuesta por WhatsApp

### Control
- Dashboard permite ver estado, logs y controlar el bot
- Todos los datos se guardan para análisis posterior

## ⚙️ API Endpoints

### Estado y Control
- `GET /health` - Health check
- `GET /api/bot-status` - Estado actual del bot
- `POST /api/bot-toggle` - Activar/desactivar bot

### Configuración
- `GET /api/env-config` - Obtener configuración actual
- `POST /api/env-config` - Actualizar configuración Supabase
- `GET /api/user-config` - Obtener config del usuario
- `POST /api/user-config` - Actualizar config del usuario

### Testing
- `POST /ask` - Test directo de Gemini

### Webhooks
- `POST /webhook/whatsapp` - Recibir mensajes de WaSender

## 🔑 Variables de Entorno Requeridas

```env
GEMINI_API_KEY=     # API Key de Google Gemini
WASENDER_TOKEN=     # Token de WaSender
SUPABASE_URL=       # URL de tu proyecto Supabase
SUPABASE_KEY=       # API Key anón de Supabase
```

## 📊 Bases de Datos

### Tabla: leads
```sql
id              BIGINT PRIMARY KEY
whatsapp_id     VARCHAR(20) UNIQUE
platform        VARCHAR(50)  -- 'whatsapp' o 'whatsapp_group'
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### Tabla: conversations
```sql
id              BIGINT PRIMARY KEY
lead_id         BIGINT FK → leads.id
role            VARCHAR(50)  -- 'user' o 'agent'
content         TEXT
created_at      TIMESTAMP
```

## 🎯 Casos de Uso

### 📱 Ventas
- Responder preguntas de clientes automáticamente
- Calificar leads según sus respuestas
- Agendar consultas

### 🏢 Soporte Técnico
- Responder preguntas frecuentes
- Crear tickets automáticos
- Escalar a humanos si es necesario

### 📣 Marketing
- Enviar mensajes de seguimiento
- Recopilar información de clientes
- Automatizar campañas

### 🏗️ Construcción (caso actual de Looply)
- Responder consultas de construcción
- Agendar visitas
- Cualificar proyectos

## 🛠️ Customización

### Cambiar el Prompt del Bot
En `app.py`, modifica `default_prompt`:

```python
default_prompt = """
Tu nuevo prompt aquí.
Personaliza el comportamiento del bot.
"""
```

O usa la configuración de moneymaze.es para cambiar dinámicamente.

### Agregar Nuevos Endpoints
Añade nuevas rutas Flask en `app.py`:

```python
@app.route('/api/nueva-ruta', methods=['GET', 'POST'])
def nueva_funcion():
    return jsonify({'mensaje': 'Tu respuesta'})
```

## 🚨 Debugging

### Ver Logs en Consola
```bash
python app.py
# Los logs aparecerán con prefijos como ✅ ❌ ⚠️
```

### Ver Logs en Dashboard
Abre http://localhost:8080 y los logs aparecen en tiempo real.

### Endpoint de Test
```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"message":"Hola, soy un test"}'
```

## 🔐 Seguridad

⚠️ **IMPORTANTE:**
- **NUNCA** compartas el archivo `.env`
- **NUNCA** hardcodees credenciales
- Añade `.env` a `.gitignore`
- Regenera claves si accidentalmente las expones

## 📈 Performance

- Respuestas en <5 segundos típicamente
- Soporta 100+ conversaciones simultáneas
- Almacenamiento ilimitado en Supabase
- Sin límite de mensajes (sí limites de API de Gemini)

## 💰 Costos

- **Gemini API**: $0.075 por millón de input tokens (gratis inicialmente)
- **WaSender**: Depende del plan ($15-200/mes)
- **Supabase**: $25/mes (plan Pro) o gratis (plan Free)

## 🐛 Problemas Comunes

### "Bot no responde"
1. Verifica estado en dashboard
2. Checa GEMINI_API_KEY en .env
3. Verifica webhook URL en WaSender
4. Mira los logs en el dashboard

### "No se guardan los mensajes"
1. Verifica SUPABASE_URL y KEY
2. Confirma que las tablas existen
3. Checa los permisos en Supabase

### "WaSender no conecta"
1. Verifica WASENDER_TOKEN
2. Comprueba que el teléfono está registrado
3. Mira logs de WaSender en su panel

## 📞 Soporte

Para problemas o sugerencias:
1. Revisa los logs del servidor
2. Consulta la guía de setup completa
3. Contacta al equipo de Looply

## 📄 Licencia

Proyecto propietario de Looply. Todos los derechos reservados.

## 🤝 Contribuciones

Si trabajas en Looply y tienes mejoras:
1. Crea una rama: `git checkout -b feature/mejora`
2. Commit tus cambios: `git commit -m "Descripción"`
3. Push: `git push origin feature/mejora`
4. Abre un Pull Request

---

**Versión**: 1.0  
**Última actualización**: Marzo 2024  
**Desarrollado por**: Looply Team  
**Soporte**: support@looply.com
