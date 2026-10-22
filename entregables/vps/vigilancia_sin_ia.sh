#!/bin/bash
# Vigilancia sin Claude: mientras no hay cuota del plan, el lanzador corre esto en vez de esperar.
# Cada llamada re-corre UN spider dedicado (rotando por el que hace más que no se corre) a data/vigilancia/,
# sin tocar data/<x>_completo.json ni ninguna base, y anota en maquina_fija/vigilancia.md qué secciones
# crecieron o cayeron contra el archivo vigente. El próximo ciclo con Claude lee ese informe y decide.
cd "$(dirname "$0")/../.." || exit 1
mkdir -p data/vigilancia maquina_fija
SPIDERS="austral itba palermo uade uai ub uba uca ucema uces udesa umsa usal utdt utn"
ROTACION=maquina_fija/vigilancia_rotacion.txt
touch "$ROTACION"

# El que no figura en la rotación, o el que figura hace más tiempo.
elegido=""
for s in $SPIDERS; do grep -q "^$s " "$ROTACION" || { elegido=$s; break; }; done
if [ -z "$elegido" ]; then
  read -r elegido ultima < <(sort -k2 -n "$ROTACION" | head -1)
  # Cortesía: un sitio se re-lee como mucho una vez por día.
  if [ $(( $(date +%s) - ultima )) -lt 86400 ]; then
    echo "vigilancia: los $(wc -l < "$ROTACION") spiders ya corrieron en las últimas 24 h"
    exit 0
  fi
fi

salida="data/vigilancia/${elegido}_completo.json"
inicio=$(date '+%F %H:%M')
timeout 3600 env PYTHONPATH=. .venv/bin/python -m "rumbo_scraper.spiders.$elegido" --output "$salida" \
  > "data/vigilancia/${elegido}.log" 2>&1
codigo=$?
grep -v "^$elegido " "$ROTACION" > "$ROTACION.tmp"; echo "$elegido $(date +%s)" >> "$ROTACION.tmp"; mv "$ROTACION.tmp" "$ROTACION"

informe=$(PYTHONPATH=. .venv/bin/python - "data/${elegido}_completo.json" "$salida" "$codigo" <<'PY'
import json, sys
vigente, nuevo, codigo = sys.argv[1], sys.argv[2], int(sys.argv[3])
def conteos(path):
    try:
        datos = json.load(open(path)).get("datos", {})
    except Exception:
        return None
    return {k: len(v) for k, v in datos.items() if isinstance(v, list)}
antes, ahora = conteos(vigente), conteos(nuevo)
if ahora is None:
    print(f"falló (salida {codigo}), sin archivo nuevo")
elif antes is None:
    print("sin archivo vigente para comparar: " + ", ".join(f"{k} {v}" for k, v in ahora.items() if v))
else:
    cambios = []
    for k in sorted(set(antes) | set(ahora)):
        a, b = antes.get(k, 0), ahora.get(k, 0)
        if a != b:
            marca = " CAYÓ" if a and b < a * 0.8 else ""
            cambios.append(f"{k} {a}→{b}{marca}")
    print("; ".join(cambios) if cambios else "sin cambios en los conteos")
PY
)
echo "- $inicio $elegido: $informe" >> maquina_fija/vigilancia.md
echo "vigilancia $elegido: $informe"
