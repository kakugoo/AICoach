"""Create a private local environment file without displaying its password."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = (root / ".env.example").read_text(encoding="utf-8")
password = secrets.token_urlsafe(36)
if "POSTGRES_PASSWORD=\n" not in template or "REPLACE_WITH_UNIQUE_PASSWORD" not in template:
    raise SystemExit("Environment template is missing the expected placeholders.")
content = template.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={password}\n", 1)
content = content.replace("REPLACE_WITH_UNIQUE_PASSWORD", password, 1)
try:
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError as exc:
    raise SystemExit(".env already exists; it was not changed.") from exc
with os.fdopen(fd, "w", encoding="utf-8") as file:
    file.write(content)
print("Created a private .env with a unique local password.")
