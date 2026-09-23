"""Read the postgraduates of a university whose adapter reads only its careers.

UCES's adapter reads its thirty careers and never looked at its postgraduate
catalogue, which the site keeps under ``/posgrados``. Pointing the general
reader at the whole site would also read the careers, under names that need
not match the adapter's, and the general loader retires what a reading does
not find. So here the reader walks out from the postgraduate index alone and
only postgraduates are kept and written. Nothing the adapter stored is
touched, and nothing is deleted.

Preview by default; ``--apply`` writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rumbo_scraper.catalogo import Universidad
from rumbo_scraper.database.load_generico import LOADABLE_KINDS
from rumbo_scraper.parsers import generico
from rumbo_scraper.spiders.generico import Lector, Navegador, _documento_del_plan

DEFAULT_DIR = Path("data")
# Where each such university publishes its postgraduates, and the part of the
# address every page of that catalogue shares.
INDICES: dict[str, tuple[Universidad, str]] = {
    "uces": (Universidad(
        "Universidad de Ciencias Empresariales y Sociales", "UCES", "Privada",
        "https://www.uces.edu.ar", "uces.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
        semillas=("https://www.uces.edu.ar/posgrados",),
    ), "/carreras-posgrados/"),
}


def leer(universidad: Universidad, prefijo: str) -> dict[str, Any]:
    """Walk the catalogue two levels down from its index, in a browser.

    UCES builds its index, each area's list and each programme's page in the
    visitor's browser from data the server does not put in the page, so every
    page is read as a visitor sees it. The walk keeps to the addresses under
    the catalogue's own prefix: the menus link everywhere else.
    """
    from urllib.parse import urlparse

    def del_catalogo(url: str) -> bool:
        return urlparse(url).path.startswith(prefijo)

    lector = Lector(universidad)
    navegador = Navegador()
    try:
        etiquetas: dict[str, str] = {}
        areas: list[str] = []
        for semilla in universidad.semillas:
            for url, etiqueta in generico.enlaces_con_etiqueta(
                    navegador.get(semilla), semilla, lector.dominios):
                if del_catalogo(url) and url not in areas:
                    areas.append(url)
                    etiquetas.setdefault(url, etiqueta)
        paginas: dict[str, str] = {}
        for area in areas:
            paginas[area] = navegador.get(area)
            for url, etiqueta in generico.enlaces_con_etiqueta(
                    paginas[area], area, lector.dominios):
                if del_catalogo(url) and url not in paginas and url not in areas:
                    etiquetas.setdefault(url, etiqueta)
        for url in [u for u in etiquetas if u not in paginas and u not in areas]:
            paginas[url] = navegador.get(url)

        programas: list[generico.Programa] = []
        planes: dict[str, list[dict[str, Any]]] = {}
        for url, html in paginas.items():
            if url in areas or not html:
                continue
            programa = (generico.leer_programa(html, url)
                        or generico.leer_programa_por_etiqueta(html, url, etiquetas.get(url, "")))
            if programa is None or programa.nivel != "Posgrado":
                continue
            programas.append(programa)
            materias = generico.leer_plan(html)
            if not materias:
                documento = _documento_del_plan(html, url, lector.dominios)
                if documento:
                    materias = generico.leer_plan_documento(
                        lector.get_documento(documento), programa.nombre,
                        universidad.nombre_oficial)
            if materias:
                planes[url] = materias
        return generico.build_dataset(universidad, programas, paginas, planes,
                                      lector.errores, descubiertas=len(paginas))
    finally:
        navegador.close()
        lector.close()


def aplicar(dataset: dict[str, Any], client: Any) -> dict[str, int]:
    from rumbo_scraper.database.load_utdt import _insert_chunks, _upsert_one
    from rumbo_scraper.database.supabase import select_all

    data = dataset["datos"]
    nombre = data["universidades"][0]["nombre_oficial"]
    fila = client.table("universidades").select("id").eq("nombre_oficial", nombre).execute().data
    if not fila:
        return {"universidad_no_encontrada": 1}
    uid = fila[0]["id"]
    facultades = {f["nombre_facultad"]: f["id"] for f in select_all(
        client.table("facultades").select("id,nombre_facultad").eq("universidad_id", uid))}

    ids: dict[str, str] = {}
    for row in data["posgrados"]:
        if row["tipo_posgrado"] not in LOADABLE_KINDS:
            continue
        guardado = _upsert_one(client, "posgrados", {
            "universidad_id": uid,
            "facultad_id": facultades.get(str(row["facultad_nombre"])),
            "nombre_programa": row["nombre_programa"],
            "tipo_posgrado": row["tipo_posgrado"],
            "titulo_otorgado": row["titulo_otorgado"], "sede_id": None,
            "modalidad": row["modalidad"], "duracion_meses": row["duracion_meses"],
            "requiere_tesis_trabajo_final": None,
            "requisito_titulo_previo": row["requisito_titulo_previo"],
            "cohorte_inicio": row["cohorte_inicio"],
            "costo_total_programa": None, "moneda": None,
            "descripcion_breve": row["descripcion_breve"],
            "url_oficial": row["url_oficial"],
        }, "universidad_id,nombre_programa")
        ids[row["nombre_programa"]] = guardado["id"]

    con_materias = {f["posgrado_id"] for f in select_all(
        client.table("materias").select("posgrado_id").eq("universidad_id", uid))}
    materias = [{
        "universidad_id": uid, "carrera_id": None,
        "posgrado_id": ids[row["carrera_o_programa"]],
        "nombre_materia": row["nombre_materia"], "anio_cursada": row["anio_cursada"],
        "turno": None, "area_tematica_id": None, "descripcion_breve": None,
        "regimen": None, "carga_horaria_semanal": None,
    } for row in data["materias"]
        if row["carrera_o_programa"] in ids
        and ids[row["carrera_o_programa"]] not in con_materias]
    return {"posgrados": len(ids),
            "materias": _insert_chunks(client, "materias", materias) if materias else 0}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Leer los posgrados de una universidad cuyo adaptador lee solo carreras")
    parser.add_argument("universidad", choices=sorted(INDICES))
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()
    dataset = leer(*INDICES[args.universidad])
    salida = DEFAULT_DIR / f"{args.universidad}_posgrados.json"
    salida.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    data = dataset["datos"]
    print(f"- posgrados: {len(data['posgrados'])}")
    print(f"- materias: {len(data['materias'])}")
    for row in data["posgrados"][:200]:
        print(f"  {row['tipo_posgrado']:16} {row['nombre_programa']}")
    if args.apply:
        from rumbo_scraper.database.supabase import get_supabase_client
        print("CARGADO", aplicar(dataset, get_supabase_client()))
    print(f"Archivo: {salida}")


if __name__ == "__main__":
    main()
