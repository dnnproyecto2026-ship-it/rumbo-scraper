"""Give the UTN's careers the duration and degree its own catalogue states.

The UTN's page for a career (``estudiar-utn?...&idSeleccion=3``) is filled
in the browser from a public service that lists every career of a kind with
its fields:

    www.utn.edu.ar/modules/mod_oferta_acad/web-oferta.php?tipo_busqueda=carreras&id_tipos_carreras=1

``duracion`` says how long it takes ("Años: 5½", "dos (2) años", "2 años y
1/2"; a count of hours alone is not a duration). ``info`` and ``alcance``
sometimes say the degree ("el título que otorga es el de Licenciado/a en
..."); it is taken only if it is the one degree they give and its words are
the career's: the service calls the Licenciatura en Automatización y
Control's degree "Licenciado/a en Administración y Control".

Only careers with no duration or no degree are touched. The preview keeps
what it found in ``data/utn_hallados.json``; ``--apply`` writes from it.

    python -m rumbo_scraper.database.completar_utn
    python -m rumbo_scraper.database.completar_utn --apply
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.parsers.duracion import duraciones_en
from rumbo_scraper.parsers.titulo import titulos_en

SERVICIO = ("https://www.utn.edu.ar/modules/mod_oferta_acad/web-oferta.php"
            "?tipo_busqueda=carreras&id_tipos_carreras={}")
# Grado, ciclos de licenciatura, pregrado (posgrado states no duration).
TIPOS = (1, 2, 3)
HALLADOS = Path("data/utn_hallados.json")
_VACIAS = frozenset("de del la las los el y e en a con para por licenciatura licenciado licenciada tecnicatura "
                    "tecnico tecnica universitario universitaria ingenieria ingeniero ingeniera ciclo "
                    "complementacion curricular".split())


def _plano(html: str | None) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", html or ""))


def duracion_de(texto: str | None) -> float | None:
    """ "Años: 5½" -> 5.5; "dos (2) años" -> 2; "2 años y 1/2" -> 2.5."""
    texto = _plano(texto)
    campo = re.search(r"(?i)a[ñn]os:\s*(\d{1,2})\s*(½|1/2)?", texto)
    if campo:
        valor = int(campo.group(1)) + (0.5 if campo.group(2) else 0)
        return valor if 1.5 <= valor <= 7 else None
    # "dos (2) años", "5 (CINCO) años": the brackets repeat the figure;
    # "y 1/2" after the unit.
    texto = re.sub(r"\s*\([^)]*\)", "", texto)
    texto = re.sub(r"(?i)(a[ñn]os)\s+y\s+(?:1/2|½)", r"y medio \1", texto)
    halladas = duraciones_en(texto) or duraciones_en("Duración: " + texto)
    return halladas.pop() if len(halladas) == 1 else None


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]{3,}", comparison_key(texto)) if p not in _VACIAS}


def titulo_de(carrera: dict[str, Any]) -> str | None:
    """The one degree ``info`` and ``alcance`` give, if its words are the career's."""
    hallados: list[str] = []
    for campo in ("info", "alcance"):
        texto = _plano(carrera.get(campo))
        # 'el título que otorga es el de "Licenciado/a en ..."'
        texto = re.sub(r'(?i)t[íi]tulo que (?:se )?otorga es el de\s*["“]?([^"”.]+)["”]?', r"Título: \1.", texto)
        for titulo in titulos_en(texto):
            if comparison_key(titulo) not in {comparison_key(h) for h in hallados}:
                hallados.append(titulo)
    if len(hallados) != 1:
        return None
    nombre = re.sub(r"(?i)\s*[-–(].*$", "", carrera.get("nombre_carreras") or "")
    propias = _palabras(nombre)
    return hallados[0] if propias and propias <= _palabras(hallados[0]) else None


def del_servicio() -> dict[str, dict[str, Any]]:
    import httpx

    por_id: dict[str, dict[str, Any]] = {}
    for tipo in TIPOS:
        respuesta = httpx.get(SERVICIO.format(tipo), timeout=30,
                              headers={"User-Agent": "RumboScraper/1.0 (+https://www.rumboi.com)"})
        respuesta.raise_for_status()
        for carrera in respuesta.json():
            por_id[str(carrera["id_carreras"])] = carrera
    return por_id


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.supabase import select_all

    utn = next(u for u in select_all(client.table("universidades").select("id,nombre_corto"))
               if u.get("nombre_corto") == "UTN")
    carreras = {c["id"]: c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,duracion_anios,titulo_otorgado")) if c["universidad_id"] == utn["id"]}
    servicio = del_servicio()
    hallados, vistos = [], set()
    for oferta in select_all(client.table("ofertas_academicas").select("carrera_id,url_oficial")):
        carrera = carreras.get(oferta["carrera_id"])
        if not carrera or carrera["id"] in vistos:
            continue
        seleccion = parse_qs(urlparse(oferta["url_oficial"] or "").query).get("idSeleccion")
        fuente = servicio.get(seleccion[0]) if seleccion else None
        if not fuente:
            continue
        vistos.add(carrera["id"])
        duracion = None if carrera["duracion_anios"] else duracion_de(fuente.get("duracion"))
        titulo = None if carrera["titulo_otorgado"] else titulo_de(fuente)
        if duracion or titulo:
            print(f"{carrera['nombre_carrera'][:60]:60} | {duracion or '':4} | {titulo or ''}", flush=True)
            hallados.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"],
                             "duracion": duracion, "titulo": titulo, "url": oferta["url_oficial"]})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar la duración y el título de las carreras de la UTN")
    parser.add_argument("--apply", action="store_true", help=f"Escribir lo que dejó la vista previa en {HALLADOS}")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client
    client = get_supabase_client()
    if args.apply:
        hallados = json.loads(HALLADOS.read_text())
        for h in hallados:
            if h["duracion"]:
                client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                    "id", h["carrera_id"]).is_("duracion_anios", "null").execute()
            if h["titulo"]:
                client.table("carreras").update({"titulo_otorgado": h["titulo"]}).eq(
                    "id", h["carrera_id"]).is_("titulo_otorgado", "null").execute()
        print(f"Duraciones: {sum(1 for h in hallados if h['duracion'])}; "
              f"títulos: {sum(1 for h in hallados if h['titulo'])}")
        return
    hallados = leer(client)
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Con duración: {sum(1 for h in hallados if h['duracion'])}; "
          f"con título: {sum(1 for h in hallados if h['titulo'])} — vista previa en {HALLADOS}")


if __name__ == "__main__":
    main()
