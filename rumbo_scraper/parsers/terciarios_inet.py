"""The higher technical degrees each institute gives, province by province,
from INET's national catalogue of degrees (catalogo-inet.educacion.gob.ar).

The catalogue searches its degrees by province and level (64, "Superior
Técnico") with a query of the page's table (``/planes``, read-only), and
gives, for a degree and a province, a spreadsheet of the institutes giving
it (``/instituciones/<degree>/<province>``): CUE, name, sector, degree,
address, town, department, phone, mail and site.

    python -m rumbo_scraper.parsers.terciarios_inet    (writes data/terciarios_inet.json)
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

INET = "https://catalogo-inet.educacion.gob.ar"
PROVINCIAS = ("02", "06", "10", "14", "18", "22", "26", "30", "34", "38", "42", "46", "50", "54", "58", "62",
              "66", "70", "74", "78", "82", "86", "90", "94")
SALIDA = Path("data/terciarios_inet.json")
PAUSA = 1.0
_COLUMNAS = ("Id", "Title", "Level")


def _consulta(provincia: str, texto: str) -> dict[str, str]:
    datos = {"draw": "1", "start": "0", "length": "1000", "order[0][column]": "1", "order[0][dir]": "asc",
             "search[value]": "", "search[regex]": "false", "province": str(int(provincia)), "searchText": texto,
             "department": "0", "location": "0", "level": "64", "management": "0"}
    for numero, columna in enumerate(_COLUMNAS):
        datos |= {f"columns[{numero}][data]": columna, f"columns[{numero}][name]": "",
                  f"columns[{numero}][searchable]": "false",
                  f"columns[{numero}][orderable]": "true", f"columns[{numero}][search][value]": "",
                  f"columns[{numero}][search][regex]": "false"}
    return datos


def filas_de_la_planilla(contenido: bytes) -> list[dict[str, str]]:
    """The institutes of an INET spreadsheet: the rows under its header
    ("CUE", "Nombre", ...)."""
    import openpyxl

    # (Read whole: in read-only mode the sheet, which states no size, comes out empty.)
    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
    filas, encabezado = [], None
    for fila in hoja.iter_rows(values_only=True):
        valores = [str(v).strip() if v is not None else "" for v in fila]
        if encabezado is None:
            if valores and valores[0] == "CUE":
                encabezado = valores
            continue
        if any(valores):
            filas.append(dict(zip(encabezado, valores)))
    return filas


def main() -> None:
    import warnings

    from rumbo_scraper.spiders.visitante import Visitante

    warnings.filterwarnings("ignore")
    avance = SALIDA.with_suffix(".avance.json")
    estado = json.loads(avance.read_text()) if avance.exists() else {"titulos": {}, "filas": {}}
    with Visitante(timeout=60) as visitante:
        for provincia in PROVINCIAS:
            if provincia in estado["titulos"]:
                continue
            titulos: dict[str, str] = {}
            for vocal in "aeiou":
                try:
                    datos = visitante.client.post(f"{INET}/planes", data=_consulta(provincia, vocal)).json()
                except Exception:
                    datos = {}
                titulos |= {str(t["Id"]): t["Title"] for t in datos.get("data") or []}
                time.sleep(PAUSA)
            estado["titulos"][provincia] = titulos
            avance.write_text(json.dumps(estado, ensure_ascii=False))
            print(f"provincia {provincia}: {len(titulos)} títulos", flush=True)
        for provincia, titulos in estado["titulos"].items():
            for titulo in titulos:
                clave = f"{provincia}_{titulo}"
                if clave in estado["filas"]:
                    continue
                try:
                    respuesta = visitante.client.get(
                        f"{INET}/instituciones/{titulo}/{int(provincia)}?departamento=0&localidad=0")
                    estado["filas"][clave] = filas_de_la_planilla(respuesta.content) if respuesta.status_code == 200 else []
                except Exception:
                    continue
                time.sleep(PAUSA)
                if len(estado["filas"]) % 25 == 0:
                    avance.write_text(json.dumps(estado, ensure_ascii=False))
    avance.write_text(json.dumps(estado, ensure_ascii=False))
    SALIDA.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n")
    print(f"INET: {sum(len(f) for f in estado['filas'].values())} filas — {SALIDA}")


if __name__ == "__main__":
    main()
