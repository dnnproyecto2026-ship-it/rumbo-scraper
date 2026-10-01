"""The degrees the national guide (DNGU, ``data/guia_dngu.json``) lists for
a university that the catalogue does not have.

A degree is named by its title ("Ingeniero Químico"), a career by its
programme ("Ingeniería Química"): they are compared by the stems of the
words that tell one degree from another ("quimi"), the degree's kind
("Ingeniero", "Licenciado en") left out unless nothing else is left
("Abogado" is "aboga", as in "Abogacía"). Intermediate titles are the
waypoints of another degree and are not counted.

    python -m rumbo_scraper.database.faltantes_dngu   # writes data/faltantes_dngu.json
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key

GUIA = Path("data/guia_dngu.json")
SALIDA = Path("data/faltantes_dngu.json")
_GENERICAS = {"ingeniero", "ingeniera", "licenciado", "licenciada", "tecnico", "tecnica", "profesor",
              "profesora", "universitario", "universitaria", "superior", "en", "de", "del", "la", "las",
              "los", "el", "y", "e", "con", "para", "a", "al", "orientacion", "o", "as", "os"}


def raices(texto: str, sin_genericas: bool = True) -> set[str]:
    palabras = re.findall(r"[a-z0-9]+", comparison_key(re.sub(r"(?<=\w)/(?:a|as|o|os)\b", "", texto)))
    propias = [p for p in palabras if p not in _GENERICAS] if sin_genericas else palabras
    return {p[:5] for p in (propias or palabras) if len(p) > 1}


def la_tiene(titulo: str, carreras: list[set[str]]) -> bool:
    buscadas = raices(titulo)
    return any(buscadas <= c for c in carreras)


# The guide's name for a university the catalogue names otherwise.
_LLAMADA = {
    "Pontificia Universidad Católica Argentina Santa María de los Buenos Aires": "UCA",
    "Universidad Empresarial Siglo 21": "Siglo 21",
    "Universidad Salesiana Argentina": "UNISAL",
    "Instituto Universitario Escuela Argentina de Negocios": "UEAN",
    "Universidad de San Pablo - T": "USPT",
    "Universidad Nacional José C. Paz": "UNPAZ",
    "Instituto Universitario Escuela Superior de Economía y Administración de Empresas": "ESEADE",
    "Instituto Universitario de Ciencias de la Salud de la Fundación Barceló": "IUCSB",
}


def universidad_de(nombre: str, nuestras: dict[str, str], por_corto: dict[str, str]) -> str | None:
    """Our university for the guide's name: the same name, or the one the
    guide calls otherwise. Never a guess: a near name can be another
    university ("Universidad Nacional de San Juan" and "... de la Patagonia
    San Juan Bosco")."""
    if nombre in _LLAMADA:
        return por_corto.get(_LLAMADA[nombre])
    return nuestras.get(comparison_key(nombre))


def main() -> None:
    from rumbo_scraper.database.supabase import get_supabase_client, select_all

    client = get_supabase_client()
    universidades = select_all(client.table("universidades").select("id,nombre_oficial,nombre_corto"))
    nuestras = {comparison_key(u["nombre_oficial"]): u["id"] for u in universidades}
    corto = {u["id"]: u["nombre_corto"] for u in universidades}
    por_corto = {u["nombre_corto"]: u["id"] for u in universidades}
    carreras: dict[str, list[set[str]]] = defaultdict(list)
    for c in select_all(client.table("carreras").select("universidad_id,nombre_carrera")):
        carreras[c["universidad_id"]].append(raices(c["nombre_carrera"], sin_genericas=False))

    guia = json.loads(GUIA.read_text())
    por_universidad: dict[str, dict[str, Any]] = {}
    sin_par: set[str] = set()
    vistos: set[tuple[str, str]] = set()
    for fila in guia:
        if comparison_key(fila["tipo"]).startswith("titulo intermedio"):
            continue
        # A completion course, a first cycle or a distance edition of a
        # degree is not a degree of its own ("... - Ciclo de Complementación
        # Curricular", "CBC - ...", "... - MD").
        if re.search(r"(?i)ciclo de (complementaci|licenciatura)|^cbc\b|^ciclo b[áa]sico|t[íi]tulo de base", fila["titulo"]):
            continue
        titulo = re.sub(r"\s+-\s*(MD|\d+a|Presencial)\b.*$", "", fila["titulo"]).strip()
        if (fila["universidad"], comparison_key(titulo)) in vistos:
            continue
        vistos.add((fila["universidad"], comparison_key(titulo)))
        fila = {**fila, "titulo": titulo}
        uid = universidad_de(fila["universidad"], nuestras, por_corto)
        if not uid:
            sin_par.add(fila["universidad"])
            continue
        datos = por_universidad.setdefault(corto[uid], {"guia": 0, "faltan": []})
        datos["guia"] += 1
        if not la_tiene(fila["titulo"], carreras[uid]):
            datos["faltan"].append({k: fila[k] for k in ("titulo", "tipo", "facultad", "duracion")})
    SALIDA.write_text(json.dumps({"universidades": por_universidad, "sin_par": sorted(sin_par)},
                                 ensure_ascii=False, indent=1) + "\n")
    total = sum(d["guia"] for d in por_universidad.values())
    faltan = sum(len(d["faltan"]) for d in por_universidad.values())
    print(f"Títulos de la guía: {total} · no están en el catálogo: {faltan} · universidades sin par: {len(sin_par)}")
    for nombre, d in sorted(por_universidad.items(), key=lambda kv: -len(kv[1]["faltan"]))[:40]:
        print(f"{nombre:12} {len(d['faltan']):4}/{d['guia']:4}  " + "; ".join(f["titulo"] for f in d["faltan"][:4]))


if __name__ == "__main__":
    main()
