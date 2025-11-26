"""
Script para testar e listar modelos disponíveis do Gemini
"""
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Configura API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

print("Listando modelos disponíveis:\n")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"Nome: {model.name}")
        print(f"Suporta: {model.supported_generation_methods}")
        print("-" * 50)
