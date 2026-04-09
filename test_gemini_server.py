import google.generativeai as genai
key = 'AIzaSyCPM24wkORvg6jMpIFF2yvhygxmFoymktM'
print('Configurando con key:', key[:15] + '...')
genai.configure(api_key=key)
model = genai.GenerativeModel('gemini-2.0-flash')
try:
    r = model.generate_content('Di solo hola')
    print('EXITO:', r.text)
except Exception as e:
    print('ERROR:', type(e).__name__, str(e))
