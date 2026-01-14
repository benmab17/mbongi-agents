import os
from google import genai

DEFAULT_MODEL = "gemini-2.0-flash"


def _client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY manquante (variable d’environnement).")
    return genai.Client(api_key=api_key)


def resume_contribution(titre: str, contenu: str) -> str:
    """
    Résumé institutionnel (qualité admin / traçabilité), sans inventer.
    """
    prompt = f"""
Nous sommes dans un portail interne d’agents de l’État.
Tâche: résumer la contribution ci-dessous pour un supérieur hiérarchique.

Contraintes:
- Français, style institutionnel
- Pas d’invention (si info manquante: "Non précisé")
- Format:
  1) Résumé (3-5 lignes)
  2) Points clés (3-6 puces)
  3) Urgence suggérée: Faible / Normal / Élevé (1 phrase justification)

Titre: {titre}
Texte:
{contenu}
""".strip()

    client = _client()
    resp = client.models.generate_content(model=DEFAULT_MODEL, contents=prompt)
    return (resp.text or "").strip()
