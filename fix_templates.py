from pathlib import Path

base_dir = Path("accounts/templates/accounts")
base_dir.mkdir(parents=True, exist_ok=True)

content = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>{% block title %}MBONGI-AGENTS{% endblock %}</title>
  {% load static %}
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
</head>
<body>
  <h1>MBONGI-AGENTS</h1>
  {% block content %}{% endblock %}
</body>
</html>
"""

(base_dir / "base.html").write_text(content, encoding="utf-8")

print("OK : base.html créé dans", (base_dir / "base.html").resolve())
