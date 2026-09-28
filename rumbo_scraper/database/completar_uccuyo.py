"""Give the Universidad Católica de Cuyo's careers their degree and duration.

The home's Inertia data (the same `planes_uccuyo` reads) gives each career
its duration in semesters ("10": five years; the site filters careers by
"1 a 3 sem.", "4 a 6 sem.") and its plan as a PDF whose first line is the
degree ("Título: Contador/a Público/a"). Only grado and pregrado careers,
matched by name as `planes_uccuyo` matches them, and only where the career
has none.

    python -m rumbo_scraper.database.completar_uccuyo           (preview)
    python -m rumbo_scraper.database.completar_uccuyo --apply
"""

from __future__ import annotations

import argparse
import html as entidades
import io
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers import guias_nacionales as gn
from rumbo_scraper.parsers.titulo import titulos_en

HALLADOS = Path("data/uccuyo_hallados.json")


def anios(semestres: Any) -> float | None:
    try:
        valor = int(str(semestres).strip()) / 2
    except ValueError:
        return None
    return valor if 1.5 <= valor <= 7 else None


def leer(client: Any) -> list[dict[str, Any]]:
    import pdfplumber

    from rumbo_scraper.database.supabase import select_all
    from rumbo_scraper.spiders.visitante import Visitante

    universidad = client.table("universidades").select("id").eq("nombre_corto", "UCCuyo").execute().data[0]["id"]
    carreras = {comparison_key(c["nombre_carrera"]): c for c in select_all(client.table("carreras").select(
        "id,nombre_carrera,duracion_anios,titulo_otorgado").eq("universidad_id", universidad))}
    hallados, vistas = [], set()
    with Visitante(timeout=40) as visitante:
        datos = re.search(r'data-page="([^"]+)"', visitante.get(gn.UCCUYO) or "")
        sedes = json.loads(entidades.unescape(datos.group(1)))["props"].get("universidades") or [] if datos else []
        for sede in sedes:
            for facultad in sede.get("facultades") or []:
                for item in facultad.get("carreras") or []:
                    if item.get("tipo_titulo") not in ("Grado", "Pregrado"):
                        continue
                    guia = gn._carrera(item.get("nombre") or "", "", gn.UCCUYO)
                    carrera = carreras.get(comparison_key(guia.nombre)) if guia else None
                    if not carrera or carrera["id"] in vistas:
                        continue
                    vistas.add(carrera["id"])
                    duracion = None if carrera["duracion_anios"] else anios(item.get("duracion"))
                    titulo = None
                    if not carrera["titulo_otorgado"] and item.get("plan_estudio"):
                        try:
                            respuesta = visitante.client.get(gn.UCCUYO + quote(item["plan_estudio"]))
                            with pdfplumber.open(io.BytesIO(respuesta.content)) as pdf:
                                primera = pdf.pages[0].extract_text() or ""
                        except Exception:
                            primera = ""
                        dichos = titulos_en(primera)
                        titulo = dichos[0] if len(dichos) == 1 else None
                    if duracion or titulo:
                        hallados.append({"carrera_id": carrera["id"], "carrera": carrera["nombre_carrera"],
                                         "duracion": duracion, "titulo": titulo})
    return hallados


def main() -> None:
    parser = argparse.ArgumentParser(description="Completar título y duración de las carreras de la UCCuyo")
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
