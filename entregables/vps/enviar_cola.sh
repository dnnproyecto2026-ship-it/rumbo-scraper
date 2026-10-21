#!/bin/bash
# Envía la tanda del día de cada campaña aprobada en data/mailing/cola.txt.
# Una línea por campaña:  <carpeta de la campaña> <contactos.csv>   (las líneas con # se ignoran).
# Solo se manda lo que una persona puso en la cola; el cupo diario y lo ya enviado los controla rumbo_scraper.mailing.
set -uo pipefail
cd "$(dirname "$0")/../.."
COLA=data/mailing/cola.txt
LOG=data/mailing/envios.log
[ -f "$COLA" ] || exit 0
grep -vE '^\s*(#|$)' "$COLA" | while read -r campana contactos; do
  echo "### $(date '+%F %H:%M') $campana" >> "$LOG"
  PYTHONPATH=. .venv/bin/python -m rumbo_scraper.mailing "$campana" "$contactos" --apply >> "$LOG" 2>&1
done
