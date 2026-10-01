"""Give careers the degree and duration the Ministry's national guide (DNGU) states.

The guide (``data/guia_dngu.json``, read by ``parsers/guia_dngu``) lists, per
university and faculty, each recognised degree ("Médico", "Licenciado en
Turismo") with its duration ("6 Años", "9 Cuatrimestres"). A career with no
degree or no duration gets the guide's when exactly one degree of its
university names the same field (the stems that tell it apart: "medic" for
Medicina and Médico, "quimi" for Ingeniería Química and Ingeniero Químico)
and the same kind (a licenciatura's "Licenciado", a tecnicatura's "Técnico",
an analista's "Analista"). The duration is taken only when every row of that
degree states the same one, and never above four years for a tecnicatura.
Intermediate titles, completion cycles, the CBC and postgraduate-only rows
are left out; universities are matched by name or a stated alias
(``faltantes_dngu.universidad_de``), never a guess.

Nothing is overwritten. The preview keeps its own file; ``--apply`` writes it.

    python -m rumbo_scraper.database.completar_dngu
    python -m rumbo_scraper.database.completar_dngu --apply
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key

GUIA = Path("data/guia_dngu.json")
HALLADOS = Path("data/dngu_hallados.json")
_TIPOS_DE_FILA = ("Grado", "Técnico Instrumental", "Otros Pregrados")

_TIPO = re.compile(r"^(?:licenciatura|licenciad\w*|profesorado|profesor\w*|tecnicatura|t[eé]cnic\w*|ingenier\w*|"
                   r"traductorado|traductor\w*|analista|universitari\w*|superior|publico\w*|nacional|de|en|del|la|"
                   r"las|los|el)\b\s*")
_CLASE = (("licenciatura", "licenciad"), ("profesorado", "profesor"), ("tecnicatura", "tecnic"), ("tecnic", "tecnic"),
          ("ingenieria", "ingenier"), ("traductorado", "traductor"), ("analista", "analista"))


def campo(texto: str) -> set[str]:
    """The stems of what tells a degree or career apart from others of its kind."""
    t = re.sub(r"/\w+", "", comparison_key(re.sub(r"\s*\(.*?\)", "", texto)))
    anterior = None
    while anterior != t:
        anterior, t = t, _TIPO.sub("", t)
    return {w[:5] for w in re.findall(r"[a-z]{3,}", t) if w not in ("con", "del", "las", "los", "para", "orientacion")}


def misma_clase(titulo: str, carrera: str) -> bool:
    kc, kt = comparison_key(carrera), comparison_key(titulo)
    for c, t in _CLASE:
        if kc.startswith(c):
            return kt.startswith(t)
    return True


def anios(texto: str | None) -> float | None:
    """ "6 Años" -> 6; "9 Cuatrimestres" -> 4.5; "18 Meses" -> 1.5."""
    dicho = re.fullmatch(r"\s*([\d.]+)\s*(Años|Cuatrimestres|Semestres|Meses)\s*", texto or "")
    if not dicho:
        return None
    valor, unidad = float(dicho.group(1)), dicho.group(2)
    valor = valor / 2 if unidad in ("Cuatrimestres", "Semestres") else valor / 12 if unidad == "Meses" else valor
    valor = round(valor * 2) / 2
    return valor if 1 <= valor <= 7 else None


def titulo_limpio(titulo: str) -> str:
    titulo = re.sub(r"\s*-\s*(MD|\d+a|Presencial)\b.*$", "", titulo)
    return re.sub(r"\s*\(Plan \d{4}\)", "", titulo).strip()


def hallar(carrera: dict[str, Any], filas: list[dict[str, Any]]) -> dict[str, Any] | None:
    propio = campo(carrera["nombre_carrera"])
    if not propio:
        return None
    candidatas = [f for f in filas if campo(f["titulo"]) == propio and misma_clase(f["titulo"], carrera["nombre_carrera"])]
    if len({comparison_key(f["titulo"]) for f in candidatas}) != 1:
        return None
    duraciones = {anios(f["duracion"]) for f in candidatas} - {None}
    titulo = None if carrera.get("titulo_otorgado") else candidatas[0]["titulo"]
    duracion = None if carrera.get("duracion_anios") else (duraciones.pop() if len(duraciones) == 1 else None)
    if duracion and re.match(r"(tecnic|analista)", comparison_key(carrera["nombre_carrera"])) and duracion > 4:
        duracion = None
    return {"titulo": titulo, "duracion": duracion} if titulo or duracion else None


def leer(client: Any) -> list[dict[str, Any]]:
    from rumbo_scraper.database.faltantes_dngu import universidad_de
    from rumbo_scraper.database.supabase import select_all

    universidades = select_all(client.table("universidades").select("id,nombre_oficial,nombre_corto"))
    nuestras = {comparison_key(u["nombre_oficial"]): u["id"] for u in universidades}
    por_corto = {u["nombre_corto"]: u["id"] for u in universidades}
    corto = {u["id"]: u["nombre_corto"] for u in universidades}
    filas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fila in json.loads(GUIA.read_text()):
        if fila["tipo"] not in _TIPOS_DE_FILA or re.search(r"(?i)ciclo de|^cbc\b|t[íi]tulo de base", fila["titulo"]):
            continue
        uid = universidad_de(fila["universidad"], nuestras, por_corto)
        if uid:
            filas[uid].append({**fila, "titulo": titulo_limpio(fila["titulo"])})
    hallados = []
    for carrera in select_all(client.table("carreras").select(
            "id,universidad_id,nombre_carrera,titulo_otorgado,duracion_anios").in_("nivel", ["Grado", "Pregrado"])):
        if carrera["titulo_otorgado"] and carrera["duracion_anios"]:
            continue
        dato = hallar(carrera, filas.get(carrera["universidad_id"], []))
        if dato:
            hallados.append({"carrera_id": carrera["id"], "universidad": corto[carrera["universidad_id"]],
                             "carrera": carrera["nombre_carrera"], **dato})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar título y duración desde la guía nacional (DNGU)")
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
    HALLADOS.write_text(json.dumps(hallados, ensure_ascii=False, indent=1) + "\n")
    print(f"Títulos: {sum(1 for h in hallados if h['titulo'])}; duraciones: "
          f"{sum(1 for h in hallados if h['duracion'])} {dict(Counter(h['universidad'] for h in hallados).most_common(10))}"
          f" — vista previa en {HALLADOS}")


if __name__ == "__main__":
    main()
