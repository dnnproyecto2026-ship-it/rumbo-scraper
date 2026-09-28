"""Give UNDEF's careers the degree and duration its faculties' offer pages state.

UNDEF's careers point at their faculty's offer page (``undef.edu.ar/oferta-
academica/...``), a list of careers: the tools that read a career's own page
leave it alone. There each career is a folding block (``<details>``): its
name in the summary ("Licenciatura en Administración Naval (Formación
militar)"), and in its body "Título que otorga: Licenciado en ..." and
"Duración: 5 años.". A block is taken only if its name is the career's (the
bracketed note aside) and it states one degree and one duration.

Only careers with no degree or no duration are touched.

    python -m rumbo_scraper.database.completar_undef           (preview)
    python -m rumbo_scraper.database.completar_undef --apply
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.duracion import duraciones_en
from rumbo_scraper.parsers.titulo import titulos_en

HALLADOS = Path("data/undef_hallados.json")


def _clave(nombre: str) -> str:
    return comparison_key(re.sub(r"\s*\(.*?\)\s*", " ", nombre or ""))


def bloques(html: str) -> dict[str, dict[str, Any]]:
    """Each career block of an offer page by its name's key: the degree and
    duration it states, when it states one of each."""
    hallados: dict[str, dict[str, Any]] = {}
    for bloque in BeautifulSoup(html or "", "html.parser").find_all("details"):
        resumen = bloque.find("summary")
        if not resumen:
            continue
        nombre = clean_text(resumen.get_text(" "))
        cuerpo = bloque.get_text("\n")
        cuerpo = re.sub(r"(?i)(t[íi]tulos?[^:\n]{0,30})\n+\s*:\s*", r"\1: ", cuerpo)
        cuerpo = re.sub(r"(?i)(duraci[óo]n)\n+\s*:\s*", r"\1: ", cuerpo)
        titulos = titulos_en(cuerpo)
        duraciones = duraciones_en(cuerpo)
        hallados[_clave(nombre)] = {"nombre": nombre,
                                    "titulo": titulos[0] if len(titulos) == 1 else None,
                                    "duracion": duraciones.pop() if len(duraciones) == 1 else None}
    return hallados


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.spiders.visitante import Visitante

    from rumbo_scraper.database.exportar_catalogo import _urls_de_los_artefactos

    universidad = client.table("universidades").select("id,nombre_oficial").eq("nombre_corto", "UNDEF").execute().data[0]
    carreras = {c["id"]: c for c in select_all(client.table("carreras").select(
        "id,nombre_carrera,duracion_anios,titulo_otorgado").eq("universidad_id", universidad["id"]))}
    # Its careers' addresses are the readings' (it has no offers of its own here).
    artefactos = _urls_de_los_artefactos()
    paginas = {artefactos.get((universidad["nombre_oficial"], c["nombre_carrera"])) for c in carreras.values()}
    paginas = {p for p in paginas if p and "/oferta-academica/" in p}
    dichos: dict[str, dict[str, Any]] = {}
    with Visitante(timeout=30) as visitante:
        for pagina in sorted(paginas):
            dichos.update(bloques(visitante.get(pagina)))
            time.sleep(0.8)
    hallados = []
    for carrera in carreras.values():
        dicho = dichos.get(_clave(carrera["nombre_carrera"]))
        if not dicho:
            continue
        titulo = None if carrera["titulo_otorgado"] else dicho["titulo"]
        duracion = None if carrera["duracion_anios"] else dicho["duracion"]
        if titulo or duracion:
            hallados.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"],
                             "titulo": titulo, "duracion": duracion})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar título y duración de las carreras de la UNDEF")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        hallados = json.loads(HALLADOS.read_text())
        for h in hallados:
            if h["titulo"]:
                client.table("carreras").update({"titulo_otorgado": h["titulo"]}).eq(
                    "id", h["carrera_id"]).is_("titulo_otorgado", "null").execute()
            if h["duracion"]:
                client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                    "id", h["carrera_id"]).is_("duracion_anios", "null").execute()
        print(f"Títulos: {sum(1 for h in hallados if h['titulo'])}; duraciones: {sum(1 for h in hallados if h['duracion'])}")
        return
    hallados = leer(client)
    for h in hallados:
        print(f"{h['carrera'][:60]:60} | {h['duracion'] or '':4} | {h['titulo'] or ''}")
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Con título: {sum(1 for h in hallados if h['titulo'])}; con duración: "
          f"{sum(1 for h in hallados if h['duracion'])} — vista previa en {HALLADOS}")


if __name__ == "__main__":
    main()
