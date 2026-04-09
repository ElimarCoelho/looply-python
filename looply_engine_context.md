# 🚀 Looply Engine - Master Context

## 🏢 Identidad y Objetivo
*   **Nombre**: Looply Engine
*   **Agencia**: Agencia Looply (Automatización IA para construcción).
*   **Objetivo**: Crear un asistente inteligente para ventas y gestión de leads vía WhatsApp.
*   **Estado Actual**: Backend operativo. IA Gemini funcionando. WhatsApp integrado con WaSenderAPI. Gestión de estado (ON/OFF) y configuración dinámica vía MySQL (IONOS). Memoria persistente en Supabase activa.

## 💻 Acceso al Servidor (IONOS)
*   **IP**: `87.106.255.70`
*   **Usuario**: `root`
*   **Contraseña**: `Ftygb5m8e2YcWG`
*   **Sistema**: Linux VPS (Ubuntu/Debian).
*   **Ruta Raíz**: `/root/looply-engine/backend/`

## 🌍 Red y Puertos
*   **Puerto de la App**: `http://87.106.255.70/` (Producción).
*   **Estado de Red**: 
    *   **Apache2/Plesk**: DESHABILITADOS (`systemctl disable apache2 && service psa stop`). Liberan el puerto 80 para Node.js.
    *   **Nginx**: DESHABILITADO.
    *   **SSH**: Acceso directo con contraseña (Puerto 22).

## 💻 Stack Tecnológico (Backend)
*   **Lenguaje**: Node.js (v22+).
*   **Framework**: Express.js.
*   **Gestión de Procesos**: PM2.
*   **Base de Datos Primaria (Config)**: MySQL (IONOS) vía PHP Bridge (`moneymaze.es`). 
*   **Base de Datos Memoria (Historial)**: Supabase.    

## ☁️ Supabase (Memoria y Leads)
*   **URL**: `https://vrincahxolhkorgeuhah.supabase.co`
*   **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZyaW5jYWh4b2xoa29yZ2V1aGFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIxOTkyNjUsImV4cCI6MjA4Nzc3NTI2NX0.Oq57CCM3YhW52QHrpSnnrjgM0mikPWLBZt85C4NgU28`
*   **Tablas utilizadas**:
    *   `leads`: Almacena el ID de WhatsApp (`whatsapp_id`) y otros datos del contacto.
    *   `conversations`: Almacena el historial con roles `user` y `agent`.
*   **Lógica de Memoria**: El bot recupera los últimos 10 mensajes antes de cada respuesta para mantener el hilo de la conversación.

## 🤖 Google Gemini (IA)
*   **Método de conexión**: API REST directa usando `fetch` nativo + `Contents` history.
*   **Endpoint**: `https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={API_KEY}`
*   **Modelo activo**: `gemini-2.5-flash`
*   **Configuración**: Se utiliza el campo `system_instruction` para el prompt del sistema y `contents` para el historial de mensajes.
*   **API Key Maestra**: `AIzaSyB3a07b-IW0YDEzeuZ6M-whQn7UQW-9lGA`

## 📲 WaSenderAPI (WhatsApp)
*   **Web**: https://wasenderapi.com/
*   **Token Maestro**: `802f0eb2f10b2dd4776553d81f717a2c50aa70645da57ebdcbf086396ce7bf82`
*   **Webhook Activo**: `http://87.106.255.70/webhook/whatsapp, http://87.106.255.70:8080/webhook/whatsapp`

## ⚙️ Configuración Dinámica y Estado
*   **Gestión de ON/OFF**: El bot consulta `https://moneymaze.es/apps/looply/manage_bot.php` antes de cada interacción.
*   **User Configs**: Las claves dinámicas se leen de `https://moneymaze.es/apps/looply/user_settings.php`.
*   **Dashboard**: Accesible en `http://87.106.255.70`. Permite chat de prueba, configuración de claves y toggle de estado real con cache-busting.

## 📂 Estructura de Archivos (VPS)
*   `server.js`: Lógica principal Node (Express + Supabase + Gemini).
*   `dashboard_new.html`: Frontend SPA (Lucide Icons, normalización de estado).
*   `.env`: Variables de entorno para Supabase y Gemini.
*   `package.json`: Módulos instalados (`express`, `@supabase/supabase-js`, `dotenv`).
*   **Backups Locales**: `e:\Apps\VPS_Ionos\04_programa\` (Versión más reciente).

## 📋 Reglas del Proyecto
1.  **NO instalar PHP en el VPS** (Se usa el bridge externo).
2.  **No usar SDKs** de Gemini/WaSender (Usar `fetch`).
3.  **Mantener cache-busting** en las peticiones del Dashboard (`?t=timestamp`).
4.  **Lucide**: Usar `lucide.createIcons()` (No `initIcons`).
5.  **Memoria**: Todos los mensajes (User/Agent) deben registrarse en Supabase.
