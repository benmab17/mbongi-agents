from pathlib import Path

root = Path(".")

patterns = ["Fermer", "fermer", "close", "Close"]

targets = []
targets += list(root.rglob("*.html"))
targets += list(root.rglob("*.js"))

for f in targets:
    try:
        txt = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    hits = [p for p in patterns if p in txt]
    if hits:
        print(f"{f} -> {', '.join(hits)}")
