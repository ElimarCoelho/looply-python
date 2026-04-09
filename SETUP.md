# 🚀 Guía de Instalación y Setup - Looply Bot

## 📋 Requisitos Previos

- Python 3.8 o superior instalado
- pip (Python Package Manager)
- Git (opcional, para clonar el repo)
- Acceso a Internet

## 🔧 Paso 1: Instalación Inicial

### 1.1 Clonar o descargar el proyecto
```bash
# Opción A: Con Git
git clone <tu-repo-url>
cd looply-bot

# Opción B: Descargar ZIP y extraer
# Luego abre una terminal en la carpeta del proyecto
```

### 1.2 Crear un entorno virtual (recomendado)
```bash
# En Windows
python -m venv venv
venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 1.3 Instalar dependencias
```bash
pip install -r requirements.txt
```

## 🔑 Paso 2: Obtener Credenciales

### 2.1 GEMINI API KEY (Google)
1. Ve a: https://ai.google.dev/
2. Haz clic en "Get API Key"
3. Selecciona "Create API Key" en Google Cloud Console
4. Copia la clave generada

### 2.2 WASENDER TOKEN
1. Crea cuenta en: https://wasender.com/
2. Ve a tu panel: https://app.wasender.com/
3. En Settings -> API, genera un token
4. Copia el token

### 2.3 SUPABASE
1. Crea cuenta en: https://supabase.com/
2. Crea un nuevo proyecto
3. Ve a: Settings -> API Keys
4. Copia:
   - **Project URL** (como SUPABASE_URL)
   - **anon public key** (como SUPABASE_KEY)

### 2.4 Crear tabla en Supabase
Copia y ejecuta este SQL en el SQL Editor de Supabase:

```sql
-- Tabla de leads
CREATE TABLE leads (
  id BIGSERIAL PRIMARY KEY,
  whatsapp_id VARCHAR(20) NOT NULL UNIQUE,
  platform VARCHAR(50),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabla de conversaciones
CREATE TABLE conversations (
  id BIGSERIAL PRIMARY KEY,
  lead_id BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  role VARCHAR(50) NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para mejor rendimiento
CREATE INDEX idx_leads_whatsapp ON leads(whatsapp_id);
CREATE INDEX idx_conv_lead ON conversations(lead_id);
CREATE INDEX idx_conv_created ON conversations(created_at);
```

## ⚙️ Paso 3: Configurar Variables de Entorno

### 3.1 Editar el archivo `.env`
En la raíz del proyecto, edita el archivo `.env` y rellena tus credenciales:

```env
# Google Gemini
GEMINI_API_KEY=tu_gemini_api_key_aqui

# WaSender
WASENDER_TOKEN=tu_wasender_token_aqui

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=tu_supabase_anon_key_aqui
```

### 3.2 Verificar que el archivo existe
```bash
# En Windows
type .env

# En macOS/Linux
cat .env
```

## 🚀 Paso 4: Ejecutar el Servidor

### 4.1 Iniciar la aplicación
```bash
python app.py
```

Deberías ver algo como:
```
============================================================
🚀 Iniciando servidor Flask
============================================================
📍 Host: 0.0.0.0:8080
🔧 Debug mode: ON
✅ Supabase: Conectado
✅ Gemini: Configurado
✅ WaSender: Configurado
============================================================
```

### 4.2 Acceder al Dashboard
Abre tu navegador y ve a:
```
http://localhost:8080
```

## 🔗 Paso 5: Configurar WaSender

### 5.1 Obtener tu URL pública
Si usas `localhost`, necesitas hacer que sea accesible públicamente:

**Opción A: Usar ngrok (fácil)**
```bash
# Descargar ngrok: https://ngrok.com/download
# En otra terminal:
ngrok http 8080

# Copia la URL que te da (ejemplo: https://xxxx-xx-xxx-xx.ngrok.io)
```

**Opción B: Servidor en la nube**
- Usa AWS EC2, Heroku, DigitalOcean, etc.
- Tu URL sería: `https://tudominio.com`

### 5.2 Configurar Webhook en WaSender
1. Ve a tu panel de WaSender
2. En Webhooks o Settings, agrega:
   - **URL del webhook**: `https://tudominio.com/webhook/whatsapp`
   - **Método**: POST
   - **Eventos**: messages.received, messages.upsert

## 🧪 Paso 6: Pruebas

### 6.1 Test básico
En el dashboard, haz clic en "Test Gemini" para verificar que todo funciona.

### 6.2 Test de mensajes
Envía un mensaje de WhatsApp a tu número vinculado en WaSender.
El bot debería responder automáticamente.

### 6.3 Verificar logs
En el dashboard, verás los logs en tiempo real de cada acción.

## 🐛 Solución de Problemas

### Problema: "ModuleNotFoundError: No module named 'flask'"
**Solución:**
```bash
pip install -r requirements.txt
```

### Problema: "GEMINI_API_KEY not found"
**Verificar:**
1. El archivo `.env` existe en la raíz del proyecto
2. El campo `GEMINI_API_KEY` está relleno
3. Reinicia el servidor después de cambiar `.env`

### Problema: "Cannot connect to Supabase"
**Verificar:**
1. `SUPABASE_URL` y `SUPABASE_KEY` están correctos
2. La clave es la "anon public key", no la de servicio
3. Tu proyecto en Supabase está activo
4. Las tablas `leads` y `conversations` existen

### Problema: "Bot no responde a mensajes"
1. Verifica que el bot esté "Activo" en el dashboard
2. Checa el webhook en WaSender apunta a tu URL correcta
3. Revisa los logs del servidor (consola)
4. Asegúrate de que WaSender tiene el número configurado

### Problema: "WaSender no envía mensajes"
1. Verifica que `WASENDER_TOKEN` es correcto
2. Checa que el teléfono está vinculado en WaSender
3. Revisa los logs de WaSender en su panel

## 📁 Estructura del Proyecto

```
looply-bot/
├── app.py                 # Aplicación principal (Flask)
├── dashboard_new.html     # Frontend del dashboard
├── .env                   # Configuración (NO compartir)
├── .env.example           # Ejemplo de configuración
├── requirements.txt       # Dependencias Python
├── SETUP.md              # Esta guía
└── README.md             # Documentación general
```

## 🔐 Seguridad

⚠️ **IMPORTANTE:**

1. **NUNCA compartas el archivo `.env`**
   - Agrega a `.gitignore`: `echo ".env" >> .gitignore`

2. **Si expones accidentalmente una clave:**
   - Regenera inmediatamente en el panel correspondiente
   - Actualiza el `.env` con la nueva clave

3. **Usa variables de entorno en producción**
   - No hardcodees credenciales en el código
   - Usa environment variables del servidor

4. **Habilita HTTPS en producción**
   - Los webhooks deben ser HTTPS seguro
   - Usa Let's Encrypt para certificados gratuitos

## 📊 Monitoreo

### Ver logs en tiempo real
```bash
# Mientras el servidor está corriendo
# Los logs aparecerán en el dashboard (http://localhost:8080)
```

### Endpoints útiles
- `GET /health` - Health check del servidor
- `GET /api/bot-status` - Estado actual del bot
- `POST /api/bot-toggle` - Activar/desactivar bot
- `GET /api/env-config` - Ver configuración actual
- `POST /ask` - Test directo de Gemini

## 🚀 Deploy en Producción

### Opción 1: Heroku
```bash
# 1. Crea cuenta en https://heroku.com
# 2. Instala Heroku CLI
# 3. En tu proyecto:
heroku login
heroku create tu-app-name
git push heroku main
# 4. Configura variables de entorno:
heroku config:set GEMINI_API_KEY=xxx
heroku config:set WASENDER_TOKEN=xxx
heroku config:set SUPABASE_URL=xxx
heroku config:set SUPABASE_KEY=xxx
```

### Opción 2: AWS EC2
1. Crea instancia Ubuntu
2. Instala Python, Git
3. Clona el proyecto
4. Sigue pasos 1-4 de esta guía
5. Usa Gunicorn + Nginx para servir
6. Configura SSL con Let's Encrypt

### Opción 3: DigitalOcean App Platform
1. Conecta tu GitHub
2. Selecciona este repo
3. Configura variables de entorno
4. Deploy automático

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs del servidor
2. Verifica que todas las credenciales son correctas
3. Prueba los endpoints de test
4. Contacta al soporte técnico

---

**Versión**: 1.0  
**Última actualización**: 2024  
**Mantenedor**: Looply Team
