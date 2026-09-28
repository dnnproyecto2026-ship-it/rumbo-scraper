"""Give USPT's careers the duration its own site states.

The USPT's site is built in the browser from a public service that lists
every career with its duration ("4 año/s", "2 años y medio", "4"):

    https://api.uspt.edu.ar/public/carreras/

A career gets it only if it has none and its name is the service's, letter
for letter but for accents and case. Its plans there are scanned PDFs, not
read here.

    python -m rumbo_scraper.database.completar_uspt           (preview)
    python -m rumbo_scraper.database.completar_uspt --apply
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key

SERVICIO = "https://api.uspt.edu.ar/public/carreras/"
HALLADOS = Path("data/uspt_hallados.json")


def duracion_de(texto: Any) -> float | None:
    """ "4 año/s" -> 4; "2 años y medio" -> 2.5; "4" -> 4."""
    dicho = re.match(r"(?i)\s*(\d{1,2})\s*(?:a[ñn]os?(?:/s)?)?\s*(y\s+medio)?\s*$", str(texto or ""))
    if not dicho:
        return None
    valor = int(dicho.group(1)) + (0.5 if dicho.group(2) else 0)
    return valor if 1.5 <= valor <= 7 else None


def leer(client: Any) -> list[dict[str, Any]]:
    import httpx

    from rumbo_scraper.database.supabase import select_all

    respuesta = httpx.get(SERVICIO, timeout=30, headers={"User-Agent": "RumboScraper/1.0 (+https://www.rumboi.com)"})
    respuesta.raise_for_status()
    datos = respuesta.json()
    carreras_dichas = datos if isinstance(datos, list) else datos.get("data") or []
    por_nombre = {comparison_key(c["name"]): c for c in carreras_dichas if c.get("name")}
    universidad = client.table("universidades").select("id").eq("nombre_corto", "USPT").execute().data[0]
    hallados = []
    for carrera in select_all(client.table("carreras").select("id,nombre_carrera,duracion_anios")
                              .eq("universidad_id", universidad["id"])):
        dicha = por_nombre.get(comparison_key(carrera["nombre_carrera"]))
        duracion = dicha and duracion_de(dicha.get("duration"))
        if not carrera["duracion_anios"] and duracion:
            hallados.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"], "duracion": duracion})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar la duración de las carreras de la USPT")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        hallados = json.loads(HALLADOS.read_text())
        for h in hallados:
            client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                "id", h["carrera_id"]).is_("duracion_anios", "null").execute()
        print(f"Carreras con duración: {len(hallados)}")
        return
    hallados = leer(client)
    for h in hallados:
        print(f"{h['carrera'][:70]:70} {h['duracion']}")
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Con duración: {len(hallados)} — vista previa en {HALLADOS}")


if __name__ == "__main__":
    main()
