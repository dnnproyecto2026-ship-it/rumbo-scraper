"""Read the plans of the careers an adapter found but did not read the plan of.

Fifteen universities are read by an adapter of their own, and several of them
stop at the list of careers: UCEMA and USAL name every career and link its
page, and store no subject at all. The general reader knows how to read a plan
off any page -- the years, the lines under each, the PDF the page offers when
it has no list -- so it is pointed here at the exact page each adapter already
recorded for each career, with no crawling and no guessing which page is whose.

Only a programme that has no subject stored gets any. A programme that has
some was read by its adapter, which looked at that site, and this does not
second-guess it. Nothing is ever deleted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper.catalogo import Universidad
from rumbo_scraper.normalizers.text import clean_text
from rumbo_scraper.parsers import generico
from rumbo_scraper.spiders.generico import Lector, _planes_de

DEFAULT_DIR = Path("data")


def programas_del_adaptador(dataset: dict[str, Any]) -> list[generico.Programa]:
    """Each career and postgraduate an adapter recorded, with its own page."""
    data = dataset["datos"]
    programas: dict[str, generico.Programa] = {}
    for fila in data.get("ofertas") or []:
        url, nombre = clean_text(fila.get("url_oficial")), clean_text(fila.get("carrera_nombre"))
        if url and nombre and url not in programas:
            programas[url] = generico.Programa(nombre, "Grado", None, url)
    for fila in data.get("posgrados") or []:
        url, nombre = clean_text(fila.get("url_oficial")), clean_text(fila.get("nombre_programa"))
        if url and nombre and url not in programas:
            programas[url] = generico.Programa(nombre, "Posgrado",
                                               fila.get("tipo_posgrado"), url)
    return list(programas.values())


def _universidad(dataset: dict[str, Any], programas: list[generico.Programa]) -> Universidad:
    fila = dataset["datos"]["universidades"][0]
    hosts = sorted({(urlparse(p.url).netloc or "").lower() for p in programas})
    raices = sorted({h[4:] if h.startswith("www.") else h for h in hosts if h})
    return Universidad(
        fila["nombre_oficial"], fila.get("nombre_corto") or "", fila.get("tipo_gestion") or "",
        fila.get("sitio_web") or "", raices[0] if raices else "", "", "", "",
        dominios_extra=tuple(raices[1:]),
    )


def leer(dataset: dict[str, Any]) -> dict[str, Any]:
    programas = programas_del_adaptador(dataset)
    universidad = _universidad(dataset, programas)
    lector = Lector(universidad)
    try:
        paginas = lector.get_many([p.url for p in programas])
        planes = _planes_de(lector, programas, paginas)
    finally:
        lector.close()
    return {
        "universidad": universidad.nombre_oficial,
        "planes": [{"nombre": p.nombre, "nivel": p.nivel, "url": p.url,
                    "materias": planes[p.url]}
                   for p in programas if planes.get(p.url)],
        "programas_leidos": len(programas),
        "paginas_obtenidas": len(paginas),
        "errores_descarga": lector.errores,
    }


def aplicar(lectura: dict[str, Any], client: Any) -> dict[str, int]:
    from rumbo_scraper.database.load_utdt import _insert_chunks
    from rumbo_scraper.database.supabase import select_all

    universidad = client.table("universidades").select("id").eq(
        "nombre_oficial", lectura["universidad"]).execute().data
    if not universidad:
        return {"universidad_no_encontrada": 1}
    uid = universidad[0]["id"]
    carreras = {f["nombre_carrera"]: f["id"] for f in select_all(
        client.table("carreras").select("id,nombre_carrera").eq("universidad_id", uid))}
    posgrados = {f["nombre_programa"]: f["id"] for f in select_all(
        client.table("posgrados").select("id,nombre_programa").eq("universidad_id", uid))}
    con_materias = set()
    for fila in select_all(client.table("materias").select("carrera_id,posgrado_id")
                           .eq("universidad_id", uid)):
        con_materias.add(fila["carrera_id"] or fila["posgrado_id"])

    counts = {"programas_completados": 0, "materias": 0,
              "ya_tenian_materias": 0, "sin_fila_en_la_base": 0}
    filas: list[dict[str, Any]] = []
    for plan in lectura["planes"]:
        carrera_id = carreras.get(plan["nombre"]) if plan["nivel"] != "Posgrado" else None
        posgrado_id = posgrados.get(plan["nombre"]) if plan["nivel"] == "Posgrado" else None
        destino = carrera_id or posgrado_id
        if not destino:
            counts["sin_fila_en_la_base"] += 1
            continue
        if destino in con_materias:
            counts["ya_tenian_materias"] += 1
            continue
        counts["programas_completados"] += 1
        filas.extend({
            "universidad_id": uid, "carrera_id": carrera_id, "posgrado_id": posgrado_id,
            "nombre_materia": materia["nombre"],
            "anio_cursada": materia["anio"],
            "turno": None, "area_tematica_id": None, "descripcion_breve": None,
            "regimen": None, "carga_horaria_semanal": None,
        } for materia in plan["materias"])
    counts["materias"] = _insert_chunks(client, "materias", filas) if filas else 0
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Leer los planes de las carreras que un adaptador dejó sin materias")
    parser.add_argument("universidad", help="Sigla del artefacto del adaptador, p. ej. ucema")
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    sigla = args.universidad.lower()
    dataset = json.loads((DEFAULT_DIR / f"{sigla}_completo.json").read_text(encoding="utf-8"))
    lectura = leer(dataset)
    salida = DEFAULT_DIR / f"{sigla}_planes.json"
    salida.write_text(json.dumps(lectura, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    materias = sum(len(p["materias"]) for p in lectura["planes"])
    print(f"{lectura['universidad']}: {lectura['programas_leidos']} programas, "
          f"{len(lectura['planes'])} con plan, {materias} materias")
    if args.apply:
        from rumbo_scraper.database.supabase import get_supabase_client
        print("CARGADO", aplicar(lectura, get_supabase_client()))
    print(f"Archivo: {salida}")


if __name__ == "__main__":
    main()
