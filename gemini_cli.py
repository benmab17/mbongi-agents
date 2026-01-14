import os
from google import genai

MODEL = "gemini-2.0-flash"

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY manquante")
        return

    client = genai.Client(api_key=api_key)

    print("=== GEMINI CLI LOCAL ===")
    print("Colle ton prompt, puis appuie sur Entrée.")
    print("Termine avec une ligne vide.\n")

    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            break
        lines.append(line)

    prompt = "\n".join(lines)

    if not prompt.strip():
        print("❌ Prompt vide.")
        return

    print("\n--- Gemini répond ---\n")
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )
    print((resp.text or "").strip())

if __name__ == "__main__":
    main()
