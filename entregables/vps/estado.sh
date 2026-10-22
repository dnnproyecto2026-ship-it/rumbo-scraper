#!/bin/bash
# Muestra de un vistazo cómo anda el VPS: operador, ciclo en curso, cuota de Claude, bitácora y mailing.
#   bash ~/rumbo-scraper/entregables/vps/estado.sh
cd "$(dirname "$0")/../.." || exit 1
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
LOG=maquina_fija/lanzador.log

echo "== Operador: $(systemctl --user is-active rumbo-operador)"
[ -f maquina_fija/PARAR ] && echo "   (hay maquina_fija/PARAR: termina el ciclo y se detiene)"
if pgrep -f "claude -p" >/dev/null; then
  echo "   ciclo en curso desde $(grep '^### ciclo' "$LOG" | tail -1 | cut -c11-)"
  trabajo=$(pgrep -af "rumbo_scraper" | grep -v pgrep | sed 's/.*-m //' | head -1)
  [ -n "$trabajo" ] && echo "   corriendo: $trabajo"
else
  echo "   esperando el próximo ciclo"
fi

echo "== Cuota de Claude"
ultimo=$(grep -E '^### (SIN CUOTA|ciclo)' "$LOG" | tail -1)
case "$ultimo" in
  "### SIN CUOTA"*) echo "   SIN CUOTA: ${ultimo#\#\#\# SIN CUOTA }" ;;
  *) echo "   ok (último aviso de límite: $(grep '^### SIN CUOTA' "$LOG" | tail -1 | cut -c15-30 || true))" ;;
esac
echo "   ciclos hoy: $(grep -c "^### ciclo $(date +%F)" "$LOG")  ·  sin cuota hoy: $(grep -c "^### SIN CUOTA $(date +%F)" "$LOG")"

echo "== Últimas entradas de la bitácora"
tail -8 maquina_fija/bitacora.md 2>/dev/null || echo "   (todavía vacía)"

echo "== Mailing"
echo "   próximo envío: $(systemctl --user list-timers rumbo-mailing.timer --no-pager | sed -n 2p | awk '{print $1, $2, $3}')"
echo "   campañas en cola: $(grep -cvE '^\s*(#|$)' data/mailing/cola.txt 2>/dev/null || echo 0)  ·  enviados hoy: $(grep -c "$(date +%F)" data/mailing/enviados.csv 2>/dev/null || echo 0)"
