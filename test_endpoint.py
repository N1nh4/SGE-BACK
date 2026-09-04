import json
import urllib.request
from app.auth import criar_token

token = criar_token(9)
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

for path in ("/api/notificacoes", "/api/notificacoes/quantidade"):
    req = urllib.request.Request(
        f"http://localhost:8000{path}", headers=headers, method="GET"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(path, "->", resp.status, resp.read().decode())
    except urllib.error.HTTPError as e:
        print(path, "-> ERRO", e.code, e.read().decode())
    except Exception as e:
        print(path, "-> ERRO", repr(e))