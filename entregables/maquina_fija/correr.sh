#!/bin/bash
# Lanzador permanente: arranca una sesión de Claude Code por ciclo, con el prompt de prompt.md.
# Cada sesión es nueva (el estado vive en maquina_fija/estado.md y bitacora.md), así que no depende del largo del contexto.
# Se corta creando el archivo maquina_fija/PARAR.
# OJO: --dangerously-skip-permissions deja que Claude ejecute comandos sin pedir permiso. Usalo solo en esta máquina dedicada.
cd "$(dirname "$0")/../.." || exit 1
mkdir -p maquina_fija
while [ ! -f maquina_fija/PARAR ]; do
  echo "### ciclo $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
  claude -p "$(cat entregables/maquina_fija/prompt.md)" --dangerously-skip-permissions >> maquina_fija/lanzador.log 2>&1
  sleep 300
done
echo "### parado $(date '+%F %H:%M')" >> maquina_fija/lanzador.log
