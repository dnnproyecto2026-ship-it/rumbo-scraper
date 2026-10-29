"""The higher non-university institutes the official register lists and ours does not.

    python -m rumbo_scraper.database.institutos_faltantes

``data/padron/padron_2026.xlsx`` (the Padrón Oficial de Establecimientos) marks the
ones that teach "SNU" (superior no universitario). Each is matched to
``relevamiento/terciarios.json`` by CUE, the first seven digits of its "Cueanexo"
(the register keeps nine for Buenos Aires, seven elsewhere). Córdoba's register
has no CUE, so its institutes are matched by name and number, which is weaker:
its count is an upper bound. The rest goes to
``entregables/avance/institutos_faltantes.csv``, the queue of what to look for.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

PADRON = Path("data/padron/padron_2026.xlsx")
REGISTRO = Path("relevamiento/terciarios.json")
SALIDA = Path("entregables/avance/institutos_faltantes.csv")
_ENCABEZADO = 12


def cue7(valor: Any) -> str | None:
    """The CUE of a code: nine digits (CUE and annex) cut to seven, a short one padded."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return None
    return digitos[:7] if len(digitos) >= 9 else digitos.zfill(7)


def _clave(nombre: str) -> str:
    plano = unicodedata.normalize("NFD", nombre or "").encode("ascii", "ignore").decode().lower()
    # ("N° 6", "Nro 6", "Nº 6" is the number 6.)
    plano = re.sub(r"\b(?:n|nro|numero)\s*[°º.]?\s*(?=\d)", " ", plano)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", plano).split())


def _ya_esta_por_nombre(nombre: str, conocidos: list[str]) -> bool:
    clave = _clave(nombre)
    numeros = set(re.findall(r"\d+", clave))
    return any(clave == c or (numeros and numeros <= set(re.findall(r"\d+", c)) and (clave in c or c in clave))
               for c in conocidos)


def faltantes() -> tuple[list[list[Any]], Counter, Counter]:
    import openpyxl

    registro = json.loads(REGISTRO.read_text())
    cues = {cue7(v.get("cue")) for v in registro.values()} - {None}
    sin_cue = {p: [_clave(n) for n, v in registro.items() if v.get("jurisdiccion") == p]
               for p in {v.get("jurisdiccion") for v in registro.values() if not v.get("cue")}}
    hoja = openpyxl.load_workbook(PADRON, read_only=True).worksheets[0]
    filas = hoja.iter_rows(values_only=True)
    for i, fila in enumerate(filas):
        if i == _ENCABEZADO:
            snu = [str(c) for c in fila].index("SNU")
            break
    faltan: list[list[Any]] = []
    total, sin_match = Counter(), Counter()
    for fila in filas:
        if fila[snu] not in (1, "1", 1.0):
            continue
        provincia = fila[0]
        total[provincia] += 1
        if (cue7(fila[7]) in cues) or (provincia in sin_cue and _ya_esta_por_nombre(fila[8], sin_cue[provincia])):
            continue
        sin_match[provincia] += 1
        faltan.append([provincia, fila[5], re.sub(r"\D", "", str(fila[7])).zfill(9), fila[8], fila[9], fila[12],
                       fila[11], fila[1]])
    return faltan, total, sin_match


def main() -> None:
    faltan, total, sin_match = faltantes()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow(["provincia", "localidad", "cueanexo", "nombre", "domicilio", "mail", "telefono", "sector"])
        escritor.writerows(sorted(faltan))
    print(f"Faltan {len(faltan)} de {sum(total.values())} establecimientos SNU -> {SALIDA}")
    for provincia, cuantos in sin_match.most_common():
        print(f"  {provincia:32} {cuantos:4} de {total[provincia]}")


if __name__ == "__main__":
    main()
