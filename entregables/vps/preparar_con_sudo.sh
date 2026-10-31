#!/bin/bash
# Lo que en el VPS necesita sudo y no puede hacer el operador. Se corre a mano, un paso por vez:
#   bash ~/rumbo-scraper/entregables/vps/preparar_con_sudo.sh swap      # 4 GB de memoria de respaldo
#   bash ~/rumbo-scraper/entregables/vps/preparar_con_sudo.sh usuario   # crea tu usuario del panel de Postal
#   bash ~/rumbo-scraper/entregables/vps/preparar_con_sudo.sh estado    # qué corre en Postal y qué puertos escuchan
# sudo pide la contraseña de agustin; nada de acá la guarda ni la imprime.
set -euo pipefail
POSTAL=/opt/rumbo-mail/compose.yaml

case "${1:-}" in
  swap)
    if swapon --show | grep -q /swapfile; then echo "La swap ya está activa."; free -h; exit 0; fi
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    free -h
    ;;
  usuario)
    # Pregunta mail, nombre, apellido y contraseña. La contraseña de Postal es solo del panel: inventá una nueva.
    sudo docker compose -f "$POSTAL" run --rm runner postal make-user
    echo "Listo. Entrá en https://smtp.rumboi.com con ese mail y esa contraseña."
    ;;
  estado)
    sudo docker compose -f "$POSTAL" --profile sending ps
    ss -ltn | grep -E ':(25|587|465|2525|80|443) ' || echo "ningún puerto de mail escuchando"
    ;;
  *)
    sed -n '2,6p' "$0"
    exit 2
    ;;
esac
