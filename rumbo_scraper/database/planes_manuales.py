"""The plans people copied by hand from each career's official plan.

Where no reader can take a plan whole (a resolution of seventy pages, a plan
published as an image), people of the team copy it into the sheet of pending
careers (``entregables/planes_caba_pendientes.csv``): the link of the plan
they copied from, one subject per line ("2 | Derecho Civil I", or the name
alone when the plan gives no year), who copied it and who checked it.

A row is taken only when:

- its career exists and has no subjects yet;
- the link is on the university's own site (``verificacion.es_oficial``);
- two different people copied and checked it, or the AI reader proposed it
  (``cargado_por`` "IA ...") or a common reader did (``cargado_por``
  "lector ..."), which then needs every name in the document;
- every subject is written in that document, read as the verifier reads it
  (a picture by OCR; a misspelt name is sent back with its name); a picture
  whose OCR misses a name is taken only on two people's word, kept in
  ``data/planes_revisados_a_mano.json`` for the verifier;
- the plan reads as a whole plan (``_parece_el_plan_entero``; a completion
  cycle's own plan counts as whole).

Every row's verdict goes to ``data/planes_manuales_resultado.csv``, with the
reason a row was sent back. Preview by default; ``--apply`` writes.

    python -m rumbo_scraper.database.planes_manuales entregables/planes_caba_pendientes.csv [--apply]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rumbo_scraper import verificacion as v
from rumbo_scraper.database.planes_documentos import (_TERMINA_CORTADA, _parece_el_plan_entero,
                                                      guardar_las_fuentes)

RESULTADO = Path("data/planes_manuales_resultado.csv")
REVISADOS = Path("data/planes_revisados_a_mano.json")
COLUMNA_MATERIAS = "materias (una por renglón: año | nombre)"
_IMAGEN = re.compile(r"(?i)\.(?:png|jpe?g|webp|gif)$")


def materias_de(texto: str) -> list[tuple[str, int | None]] | str:
    """The subjects a cell lists, one per line ("2 | Derecho Civil I" or the
    name alone); the reason, when a line cannot be read."""
    materias: list[tuple[str, int | None]] = []
    for numero, linea in enumerate((texto or "").splitlines(), 1):
        linea = " ".join(linea.split())
        if not linea:
            continue
        partes = [p.strip() for p in linea.split("|")]
        if len(partes) == 2 and partes[0].isdigit() and 1 <= int(partes[0]) <= 7 and partes[1]:
            materias.append((partes[1], int(partes[0])))
        elif len(partes) == 1:
            materias.append((partes[0], None))
        else:
            return f"renglón {numero} no se entiende: '{linea}' (va 'año | nombre' o solo el nombre)"
    anios = {a for _, a in materias}
    if None in anios and len(anios) > 1:
        return "algunas materias tienen año y otras no: o todas o ninguna"
    return materias


def _plan_corto_entero(materias: list[tuple[str, int | None]], duracion: float | None,
                       carrera: str = "") -> bool:
    """A short plan the readers' minimum refuses (twenty subjects without
    years, ten with): a profesorado or a one-year title names fewer. Here a
    person or a reader took it from the document and every name is in it, so
    the minimum is twelve names without years, five for a title of a year and
    a half or less, three for a profesorado; the names must not be cut (a connector at the end,
    a lower-case start) and the years, if any, run from the first with no gap."""
    # (A profesorado that completes a degree names its pedagogical subjects
    # alone: UBA's Profesorado en Psicología has four, en Sociología three.)
    if re.match(r"(?i)profesor", carrera):
        minimo = 3
    else:
        minimo = 5 if duracion and duracion <= 1.5 else 12
    if len(materias) < minimo:
        return False
    if any(nombre[:1].islower() or (_TERMINA_CORTADA.search(nombre) and not re.search(r"\s[A-Z]$", nombre))
           for nombre, _ in materias):
        return False
    anios = [anio for _, anio in materias if anio]
    if not anios:
        return True
    return set(anios) == set(range(1, max(anios) + 1)) and (not duracion or max(anios) >= math.ceil(duracion))


def revisar(fila: dict[str, str], carrera: dict[str, Any] | None, universidad: dict[str, Any] | None,
            con_materias: set[str], fuentes: Any) -> tuple[str, list[tuple[str, int | None]], bool]:
    """The reason a row is sent back ("" when it is taken), its subjects, and
    whether its plan is an image taken on the two people's word."""
    if not carrera or not universidad:
        return "la carrera no está en la base (no tocar carrera_id)", [], False
    if carrera["id"] in con_materias:
        return "la carrera ya tiene materias", [], False
    link = (fila.get("link_del_plan_usado") or "").strip()
    if not link:
        return "falta el link del plan usado", [], False
    if not v.es_oficial(link, universidad["sitio_web"]):
        return f"el link no es del sitio oficial ({urlparse(link).netloc})", [], False
    cargo, reviso = (fila.get("cargado_por") or "").strip(), (fila.get("revisado_por") or "").strip()
    # A row an AI reader or a common reader proposed needs no second person: every name is in the document.
    por_ia = cargo.lower().startswith(("ia", "lector"))
    if not por_ia and (not cargo or not reviso or cargo.lower() == reviso.lower()):
        return "faltan dos personas distintas en cargado_por y revisado_por", [], False
    materias = materias_de(fila.get(COLUMNA_MATERIAS) or "")
    if isinstance(materias, str):
        return materias, [], False
    imagen = bool(_IMAGEN.search(urlparse(link).path))
    # The document read as the verifier reads it (a picture, by OCR); every
    # subject must be written in it. Only a picture copied by two people may
    # go on their word when its OCR does not read a name.
    leida = fuentes.leer(link)
    faltan = [n for n, _ in materias if not v.dice(leida["texto"], n)] if leida["ok"] else []
    if not (imagen and not por_ia):
        if not leida["ok"]:
            return "no se pudo leer el link (¿es el documento del plan?)", materias, False
        if faltan:
            return "no figuran en el documento: " + "; ".join(faltan[:5]) + (" …" if len(faltan) > 5 else ""), \
                materias, False
    # A picture whose OCR reads every name needs no one's word.
    imagen = imagen and bool(faltan or not leida["ok"])
    # A completion cycle's own plan, copied from it, is judged as a cycle:
    # the readers refuse one because its page may show the whole degree's
    # plan, which whoever copied it saw it was not; its stored duration may
    # be the degree's.
    nombre, duracion = carrera["nombre_carrera"], carrera.get("duracion_anios")
    marca = re.compile(r"(?i)\s*[–-]?\s*(?:ciclo de complementaci[óo]n curricular|\(ccc\))")
    # A document that opens by saying it is a completion cycle ("Licenciatura
    # en Hotelería y Turismo (Ciclo de Complementación Curricular)", UB's
    # virtual licenciaturas) is one, whatever the career's name says.
    inicio = (leida.get("texto") or "")[:1500] if leida["ok"] else ""
    del_documento = bool(re.search(r"ciclo (?:de )?complementaci\w+(?: curricular)?|ciclo complementario|\bccc\b", inicio))
    if marca.search(nombre) or del_documento:
        nombre, duracion = "Ciclo " + marca.sub("", nombre), None
    if not (_parece_el_plan_entero(nombre, materias, duracion) or _plan_corto_entero(materias, duracion, nombre)):
        return "no parece el plan completo (pocas materias o faltan años)", materias, imagen
    return "", materias, imagen


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar los planes copiados a mano")
    parser.add_argument("planilla", type=Path)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.database.verificar_catalogo import Fuentes

    filas = [f for f in csv.DictReader(args.planilla.open(encoding="utf-8-sig"), delimiter=";")
             if (f.get(COLUMNA_MATERIAS) or "").strip()]
    client = get_supabase_client()
    universidades = {u["id"]: u for u in select_all(client.table("universidades").select("id,nombre_corto,sitio_web"))}
    carreras = {c["id"]: c for c in select_all(client.table("carreras").select(
        "id,universidad_id,nombre_carrera,duracion_anios"))}
    con_materias = {m["carrera_id"] for m in select_all(client.table("materias").select("carrera_id")) if m["carrera_id"]}

    resultado, insertar, planes = [], [], []
    revisados = json.loads(REVISADOS.read_text()) if REVISADOS.exists() else {}
    por_sitio: dict[str, Any] = {}
    for fila in filas:
        carrera = carreras.get((fila.get("carrera_id") or "").strip())
        universidad = universidades.get(carrera["universidad_id"]) if carrera else None
        sitio = universidad["sitio_web"] if universidad else ""
        fuentes = por_sitio.setdefault(sitio, Fuentes(sitio))
        motivo, materias, imagen = revisar(fila, carrera, universidad, con_materias, fuentes)
        resultado.append({**fila, "estado": "rechazada" if motivo else ("aceptada (imagen, revisión a mano)"
                                                                       if imagen else "aceptada"),
                          "motivo": motivo})
        print(f"{fila.get('universidad', ''):8} {fila.get('carrera', '')[:50]:50} "
              f"{'OK' if not motivo else 'NO'} {len(materias):3} {motivo}", flush=True)
        if motivo:
            continue
        con_materias.add(carrera["id"])
        corto, link = universidad["nombre_corto"], fila["link_del_plan_usado"].strip()
        vistas: set[str] = set()
        for nombre, anio in materias:
            if nombre.lower() not in vistas:
                vistas.add(nombre.lower())
                insertar.append({"universidad_id": universidad["id"], "carrera_id": carrera["id"],
                                 "nombre_materia": nombre, "anio_cursada": anio})
        planes.append({"universidad": corto, "documento": link, "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
        if imagen:
            revisados.setdefault(corto.lower(), {})[carrera["nombre_carrera"]] = {
                "url": link, "cargado_por": fila["cargado_por"].strip(), "revisado_por": fila["revisado_por"].strip()}
    for fuentes in por_sitio.values():
        fuentes.close()

    RESULTADO.parent.mkdir(parents=True, exist_ok=True)
    if resultado:
        with RESULTADO.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=list(resultado[0]), delimiter=";")
            escritor.writeheader()
            escritor.writerows(resultado)
    if args.apply and insertar:
        for inicio in range(0, len(insertar), 500):
            client.table("materias").insert(insertar[inicio:inicio + 500]).execute()
        guardar_las_fuentes(planes)
        REVISADOS.write_text(json.dumps(revisados, ensure_ascii=False, indent=1) + "\n")
    aceptadas = sum(1 for r in resultado if not r["motivo"])
    print(f"Filas completas: {len(resultado)}; aceptadas: {aceptadas}; rechazadas: {len(resultado) - aceptadas}; "
          f"materias {'cargadas' if args.apply else 'a cargar'}: {len(insertar)} — detalle en {RESULTADO}")


if __name__ == "__main__":
    main()
