"""The plans a career links only as a scanned document, read by OCR.

`planes_documentos` finds each career's plan document and checks it is the
career's whole plan, but a scanned document has no text and gives nothing.
This runs the same search with two differences, and only for such
documents: the document's text is tesseract's (`parsers.ocr.texto`), and the
plan is only the subjects it names that some university already publishes
(`parsers.ocr.plan_escaneado`), written as those are. Everything else (one
career per document, the document names the career, the whole plan) is
`planes_documentos`'s.

The preview keeps its own file (``data/planes_escaneados.json``): another
tool writes ``data/planes_documentos.json``.

    python -m rumbo_scraper.database.planes_escaneados UNRN UADER
    python -m rumbo_scraper.database.planes_escaneados --apply
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from rumbo_scraper.database import planes_documentos as pd
from rumbo_scraper.parsers import ocr

HALLADOS = Path("data/planes_escaneados.json")
SIN_TEXTO = 100   # characters a document's first pages have when it is only images


def _vocabulario(client: Any) -> dict[str, str]:
    from rumbo_scraper.database.supabase import select_all

    return ocr.vocabulario({m["nombre_materia"] for m in select_all(client.table("materias").select("nombre_materia"))
                            if m["nombre_materia"]})


def leer(client: Any, solo: set[str]) -> dict[str, dict[str, Any]]:
    conocidas = _vocabulario(client)
    escaneados: set[str] = set()
    texto_propio, leer_propio = pd._texto, pd._leer_documento

    def texto(archivo: Path) -> str:
        propio = texto_propio(archivo)
        return propio if len(propio.strip()) >= SIN_TEXTO else ocr.texto(archivo)[:20000]

    def leer_documento(archivo: Path, documento: str) -> list[tuple[str, int | None]]:
        if len(texto_propio(archivo).strip()) >= SIN_TEXTO:
            return []
        escaneados.add(documento)
        return ocr.plan_escaneado(ocr.texto(archivo), conocidas)

    pd._texto, pd._leer_documento = texto, leer_documento
    try:
        planes = pd.leer(client, solo)
    finally:
        pd._texto, pd._leer_documento = texto_propio, leer_propio
    return {cid: plan for cid, plan in planes.items() if plan.get("documento") in escaneados}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes publicados como documento escaneado")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    parser.add_argument("universidades", nargs="*", help="Nombres cortos; todas si se omite")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        planes = json.loads(HALLADOS.read_text())
    else:
        planes = leer(client, set(args.universidades))
        HALLADOS.write_text(json.dumps(planes, ensure_ascii=False, indent=1) + "\n")

    filas = []
    for plan in planes.values():
        carrera = plan["carrera"]
        print(f"{plan['universidad']:8} {carrera['nombre_carrera'][:48]:48} {len(plan['materias']):3} "
              f"{dict(Counter(anio for _, anio in plan['materias']))}", flush=True)
        vistas: set[str] = set()
        for materia, anio in plan["materias"]:
            if materia.lower() not in vistas:
                vistas.add(materia.lower())
                filas.append({"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                              "nombre_materia": materia, "anio_cursada": anio})
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        pd.guardar_las_fuentes(planes.values())
    print(f"Planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}", flush=True)


if __name__ == "__main__":
    main()
