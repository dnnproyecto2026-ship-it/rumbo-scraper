"""Give USPT's careers the duration its own site states, and the degree its
Ministry resolution names.

The USPT's site is built in the browser from a public service that lists
every career with its duration ("4 año/s", "2 años y medio", "4"):

    https://api.uspt.edu.ar/public/carreras/

A career gets it only if it has none and its name is the service's, letter
for letter but for accents and case. Its plans there are scanned PDFs, not
read here.

Each career also links the Ministry resolution that recognises it
(``resolution_url``), which names the degree in a fixed formula: "validez
nacional para el título de CONTADOR/A PÚBLICO, efectuada por ..." or "para
los títulos de LICENCIADO/A EN CIENCIA DE DATOS y TÉCNICO/A UNIVERSITARIO/A
EN CIENCIA DE DATOS, efectuada por ...". Of two, the one of the career's
kind (a licenciatura's "Licenciado/a") is taken. A scanned resolution gives
no text and no degree.

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


_EN_LA_RESOLUCION = re.compile(r"(?is)validez\s+nacional\s+(?:para|a)\s+(?:el|los)\s+t[íi]tulos?\s+de\s+(.+?),?\s+efectuada")
_TIPOS = (("licenciatura", "licenciad"), ("profesorado", "profesor"), ("tecnicatura", "tecnic"), ("ingenieria", "ingenier"))


def titulo_de_la_resolucion(texto: str, carrera: str) -> str | None:
    from rumbo_scraper.parsers.guias_nacionales import con_tildes

    dicho = _EN_LA_RESOLUCION.search(texto or "")
    if not dicho:
        return None
    titulos = [" ".join(t.split()) for t in re.split(r"\s+y\s+(?=[A-ZÁÉÍÓÚ]{3,})", dicho.group(1))]
    clave = comparison_key(carrera)
    tipo = next((t for c, t in _TIPOS if clave.startswith(c)), None)
    if tipo:
        titulos = [t for t in titulos if comparison_key(t).startswith(tipo)]
    if len(titulos) != 1 or not titulos[0].isupper() or len(titulos[0]) > 90:
        return None
    titulo = con_tildes(titulos[0])
    return titulo[0].upper() + titulo[1:]


def _texto_del_pdf(url: str) -> str:
    import subprocess
    import tempfile

    import httpx

    respuesta = httpx.get(url, timeout=60, headers={"User-Agent": "RumboScraper/1.0 (+https://www.rumboi.com)"})
    if not respuesta.content.startswith(b"%PDF"):
        return ""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as archivo:
        archivo.write(respuesta.content)
        archivo.flush()
        return subprocess.run(["pdftotext", archivo.name, "-"], capture_output=True, text=True, timeout=60).stdout


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
    for carrera in select_all(client.table("carreras").select("id,nombre_carrera,duracion_anios,titulo_otorgado")
                              .eq("universidad_id", universidad["id"])):
        dicha = por_nombre.get(comparison_key(carrera["nombre_carrera"]))
        duracion = None if carrera["duracion_anios"] else dicha and duracion_de(dicha.get("duration"))
        titulo = None
        if dicha and not carrera["titulo_otorgado"] and dicha.get("resolution_url"):
            titulo = titulo_de_la_resolucion(_texto_del_pdf(dicha["resolution_url"]), carrera["nombre_carrera"])
        if duracion or titulo:
            hallados.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"],
                             "duracion": duracion, "titulo": titulo})
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
            if h.get("duracion"):
                client.table("carreras").update({"duracion_anios": h["duracion"]}).eq(
                    "id", h["carrera_id"]).is_("duracion_anios", "null").execute()
            if h.get("titulo"):
                client.table("carreras").update({"titulo_otorgado": h["titulo"]}).eq(
                    "id", h["carrera_id"]).is_("titulo_otorgado", "null").execute()
        print(f"Duraciones: {sum(1 for h in hallados if h.get('duracion'))}; "
              f"títulos: {sum(1 for h in hallados if h.get('titulo'))}")
        return
    hallados = leer(client)
    for h in hallados:
        print(f"{h['carrera'][:60]:60} | {h['duracion'] or '':4} | {h['titulo'] or ''}")
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Con duración: {sum(1 for h in hallados if h['duracion'])}; con título: "
          f"{sum(1 for h in hallados if h['titulo'])} — vista previa en {HALLADOS}")


if __name__ == "__main__":
    main()
