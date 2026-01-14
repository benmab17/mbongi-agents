from pathlib import Path

root = Path(".")

patterns = [
    "SYSTÈME CLASSIFIÉ",
    "SYSTEME CLASSIFIE",
    "ACCÈS AUTORISÉ",
    "ACCES AUTORISE",
    "Déconnexion",
    "Deconnexion",
]

files = list(root.rglob("*.html")) + list(root.rglob("*.py"))

for f in files:
    try:
        txt = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    hits = [p for p in patterns if p in txt]
    if hits:
        print(f"{f} -> {', '.join(hits)}")
