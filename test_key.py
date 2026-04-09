import google.generativeai as genai
import os

key = "AIzaSyB3a07b-IW0YDEzeuZ6M-whQn7UQW-9lGA"
genai.configure(api_key=key)

print("Listing models with the provided key:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")

print("\nTrying to generate content with gemini-1.5-flash:")
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hola")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error generating content: {e}")
