#!/bin/bash
# Instala el scraper de Rumbo en el VPS (Ubuntu 24.04) y deja corriendo el operador permanente y el envío diario de mails.
# Se corre una vez, como el usuario dueño del repo (no root), desde la carpeta del repo:
#   bash entregables/vps/instalar.sh
# Se puede volver a correr: cada paso se saltea si ya está hecho.
# Las claves viven en ~/rumbo-secrets.env (permisos 600); el repo solo tiene un enlace .env que apunta ahí.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO="$(pwd)"

echo "== paquetes del sistema"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip poppler-utils tesseract-ocr tesseract-ocr-spa git curl

echo "== entorno de Python y Chromium"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium

echo "== claves"
if [ ! -f "$HOME/rumbo-secrets.env" ]; then
  echo "Falta $HOME/rumbo-secrets.env (SUPABASE_URL, SUPABASE_SECRET_KEY y, para mails, SMTP_*). Crealo y volvé a correr." >&2
  exit 1
fi
chmod 600 "$HOME/rumbo-secrets.env"
[ -L .env ] || ln -s "$HOME/rumbo-secrets.env" .env

echo "== pruebas"
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -q

echo "== conexión a la base del scraper (solo lectura)"
PYTHONPATH=. .venv/bin/python - <<'PY'
from rumbo_scraper.database.supabase import get_supabase_client
get_supabase_client().table("universidades").select("id").limit(1).execute()
print("OK: lee la base del scraper")
PY

echo "== Claude Code (lo usa el operador en cada ciclo)"
if ! command -v claude >/dev/null && [ ! -x "$HOME/.local/bin/claude" ]; then
  curl -fsSL https://claude.ai/install.sh | bash
fi

echo "== servicios"
mkdir -p "$HOME/.config/systemd/user" maquina_fija data/mailing
for f in rumbo-operador.service rumbo-mailing.service rumbo-mailing.timer; do
  sed "s#__REPO__#$REPO#g" "entregables/vps/$f" > "$HOME/.config/systemd/user/$f"
done
sudo loginctl enable-linger "$USER"   # que los servicios sigan con la sesión SSH cerrada
systemctl --user daemon-reload
systemctl --user enable --now rumbo-mailing.timer

cat <<EOF

Listo. Falta una sola cosa a mano:
  1. Iniciá sesión en Claude Code:  claude   (después /exit)
  2. Arrancá el operador:           systemctl --user enable --now rumbo-operador
Ver qué hace:   tail -f $REPO/maquina_fija/lanzador.log
Pararlo:        touch $REPO/maquina_fija/PARAR   (termina el ciclo en curso)
EOF
