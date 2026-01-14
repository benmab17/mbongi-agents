from google import genai

API_KEY = "AIzaSyBxVf1hTxzLT8c6ANfsfHC90K8PX1eVIWE"

client = genai.Client(api_key=API_KEY)

print("Connexion à Gemini (OK)...")

response = client.models.generate_content(
    model="models/gemini-2.5-flash-preview-09-2025",
    contents="Bonjour ! Est-ce que tu peux me répondre avec un texte simple ?"
)

print("-" * 40)
print("Réponse de Gemini :")
print(response.text)
print("-" * 40)

