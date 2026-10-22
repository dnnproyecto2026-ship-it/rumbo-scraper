#!/bin/bash
# Lanzador permanente. Cada vuelta:
#   1. La parte que no depende de Claude: re-corre un spider dedicado (vigilancia_sin_ia.sh, cada sitio una vez por día).
#   2. Un ciclo de Claude Code con prompt.md, salvo que exista maquina_fija/SIN_CLAUDE o no haya cuota del plan.
# Cada sesión de Claude es nueva (el estado vive en maquina_fija/estado.md y bitacora.md).
# Se corta creando el archivo maquina_fija/PARAR.
# OJO: --dangerously-skip-permissions deja que Claude ejecute comandos sin pedir permiso. Usalo solo en esta máquina dedicada.
cd "$(dirname "$0")/../.." || exit 1
mkdir -p maquina_fija
SALIDA=maquina_fija/ultimo_ciclo.log
while [ ! -f maquina_fija/PARAR ]; do
  bash entregables/vps/vigilancia_sin_ia.sh >> maquina_fija/lanzador.log 2>&1

  if [ -f maquina_fija/SIN_CLAUDE ]; then
    sleep 900
    continue
  fi

  echo "### ciclo $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
  claude -p "$(cat entregables/maquina_fija/prompt.md)" --dangerously-skip-permissions > "$SALIDA" 2>&1
  codigo=$?
  cat "$SALIDA" >> maquina_fija/lanzador.log
  # Sin cuota del plan Claude contesta enseguida con el aviso del límite: se anota y la próxima vuelta
  # sigue solo con la parte sin Claude. Solo en salidas cortas: un ciclo normal puede hablar del "rate limit" de un sitio.
  if [ "$(wc -l < "$SALIDA")" -lt 6 ] && grep -qiE 'usage limit|limit reached|rate limit|out of (credits|usage)|resets (at )?[0-9]' "$SALIDA"; then
    echo "### SIN CUOTA $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
    sleep 1800
    continue
  fi
  [ "$codigo" -ne 0 ] && echo "### ciclo terminó con error $codigo $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
  sleep 300
done
echo "### parado $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
