#!/usr/bin/env python3
"""Script para arreglar la API key de Gemini en el servidor"""
import sys

app_path = '/root/looply-python/app.py'
env_path = '/root/looply-python/.env'
new_key = 'AIzaSyCPM24wkORvg6jMpIFF2yvhygxmFoymktM'

# Arreglar app.py
with open(app_path, 'r') as f:
    content = f.read()

# Reemplazar la linea GEMINI_API_KEY = ... (hardcoded o getenv)
lines = content.split('\n')
new_lines = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith('GEMINI_API_KEY =') and ('AIzaSy' in line or 'os.getenv' in line):
        # Mantener la indentacion original
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(f"{indent}GEMINI_API_KEY = '{new_key}'")
        print(f"[FIX app.py] Reemplazado: {stripped}")
    else:
        new_lines.append(line)

with open(app_path, 'w') as f:
    f.write('\n'.join(new_lines))

# Arreglar .env
with open(env_path, 'r') as f:
    env_content = f.read()

env_lines = env_content.split('\n')
new_env_lines = []
for line in env_lines:
    if line.startswith('GEMINI_API_KEY='):
        new_env_lines.append(f'GEMINI_API_KEY={new_key}')
        print(f"[FIX .env] Reemplazado: {line}")
    else:
        new_env_lines.append(line)

with open(env_path, 'w') as f:
    f.write('\n'.join(new_env_lines))

print("[DONE] API Key actualizada correctamente")
