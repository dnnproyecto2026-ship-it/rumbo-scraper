"""How complete production is, read-only: a snapshot per day and its change since the last one.

    python -m rumbo_scraper.database.avance_produccion [--cola-terciarios]

Counts the published degree and pre-degree offers with a current plan, a title and a
duration, by kind of institution, by province and by institution. It writes
``data/avance/AAAA-MM-DD.json`` and prints what changed since the snapshot before it.
With ``--cola-terciarios`` it also writes the work queue for the tertiary institutes:
``entregables/avance/cola_terciarios.csv`` (province, institute, offers without a plan,
site), the biggest gaps first.

``DATABASE_URL`` comes from the environment or from the Rumbo app's ``.env`` (it is never
printed). Only SELECTs run, each with a statement timeout.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

AVANCE = Path("data/avance")
COLA = Path("entregables/avance/cola_terciarios.csv")
ENV_DE_LA_APP = Path.home() / "Desktop" / "Rumbo" / ".env"

CON_PLAN = ("exists (select 1 from planes_estudio pe join planes_materias pm on pm.plan_id = pe.id "
            "where pe.oferta_id = o.id and pe.vigente)")
BASE = ("from ofertas_publicadas op join ofertas o on o.id = op.oferta_id "
        "join carreras c on c.id = o.carrera_id join universidades u on u.id = o.universidad_id "
        "where c.nivel in ('grado', 'pregrado')")
PROVINCIA = ("join sedes s on s.id = o.sede_id join localidades l on l.id = s.localidad_id "
             "join provincias p on p.id = l.provincia_id")
CUENTAS = (f"count(*) as ofertas, count(*) filter (where {CON_PLAN}) as con_plan, "
           "count(*) filter (where coalesce(o.titulo_otorgado, '') <> '') as con_titulo, "
           "count(*) filter (where o.duracion_anios is not null) as con_duracion")


def url_de_la_base() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url and ENV_DE_LA_APP.exists():
        for linea in ENV_DE_LA_APP.read_text().splitlines():
            coincidencia = re.match(r"\s*DATABASE_URL\s*=\s*(.+)", linea)
            if coincidencia:
                url = coincidencia.group(1).strip().strip("'\"")
    if not url:
        raise SystemExit("Falta DATABASE_URL (entorno o .env de la app)")
    return url


def consultar(conexion: Any, sql: str) -> list[dict[str, Any]]:
    with conexion.cursor() as cursor:
        cursor.execute(sql)
        columnas = [c.name for c in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def instantanea(conexion: Any) -> dict[str, Any]:
    conexion.execute("set statement_timeout = 120000")
    por_tipo = consultar(conexion, f"select coalesce(u.tipo_institucion, '?') as clave, {CUENTAS} "
                                   f"{BASE} group by 1 order by 2 desc")
    por_provincia = consultar(conexion, f"select p.nombre as clave, {CUENTAS} {BASE.replace('where', PROVINCIA + ' where', 1)} "
                                        "group by 1 order by 2 desc")
    por_institucion = consultar(conexion, f"select u.nombre_corto as clave, {CUENTAS} {BASE} group by 1 order by 2 desc")
    totales = consultar(conexion, "select (select count(*) from universidades) as instituciones, "
                                  "(select count(*) from ofertas_publicadas) as ofertas_publicadas, "
                                  "(select count(*) from carreras) as carreras, "
                                  "(select count(*) from planes_estudio where vigente) as planes, "
                                  "(select count(*) from planes_materias) as materias")[0]
    return {"fecha": date.today().isoformat(), "totales": totales, "por_tipo": por_tipo,
            "por_provincia": por_provincia, "por_institucion": por_institucion}


def diferencia(nueva: dict[str, Any], vieja: dict[str, Any] | None) -> list[str]:
    """Lines saying what moved since the previous snapshot."""
    if not vieja:
        return ["(primera instantánea: sin comparación)"]
    lineas = []
    for clave in ("instituciones", "ofertas_publicadas", "carreras", "planes", "materias"):
        antes, ahora = vieja["totales"].get(clave, 0), nueva["totales"][clave]
        lineas.append(f"{clave}: {antes} -> {ahora} ({ahora - antes:+d})")
    for grupo, titulo in (("por_tipo", "tipo"), ("por_provincia", "provincia")):
        anteriores = {f["clave"]: f for f in vieja[grupo]}
        for fila in nueva[grupo]:
            antes = anteriores.get(fila["clave"], {"con_plan": 0, "ofertas": 0})
            if fila["con_plan"] != antes["con_plan"] or fila["ofertas"] != antes["ofertas"]:
                lineas.append(f"{titulo} {fila['clave']}: con plan {antes['con_plan']} -> {fila['con_plan']} "
                              f"({fila['con_plan'] - antes['con_plan']:+d}), ofertas {antes['ofertas']} -> {fila['ofertas']}")
    return lineas


def anterior(hoy: str) -> dict[str, Any] | None:
    previas = sorted(p for p in AVANCE.glob("*.json") if p.stem < hoy)
    return json.loads(previas[-1].read_text()) if previas else None


def cola_terciarios(conexion: Any) -> int:
    filas = consultar(conexion, f"""
        select coalesce(p.nombre, '(sin provincia)') as provincia, u.nombre_oficial as instituto,
               u.sitio_web, count(*) as ofertas,
               count(*) filter (where not {CON_PLAN}) as sin_plan
        from ofertas_publicadas op join ofertas o on o.id = op.oferta_id
        join carreras c on c.id = o.carrera_id join universidades u on u.id = o.universidad_id
        left join sedes s on s.id = o.sede_id left join localidades l on l.id = s.localidad_id
        left join provincias p on p.id = l.provincia_id
        where c.nivel in ('grado', 'pregrado') and u.tipo_institucion = 'instituto_terciario'
        group by 1, 2, 3 having count(*) filter (where not {CON_PLAN}) > 0
        order by 1, 5 desc""")
    COLA.parent.mkdir(parents=True, exist_ok=True)
    with COLA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow(["provincia", "instituto", "ofertas", "sin_plan", "sitio_web"])
        for f in filas:
            escritor.writerow([f["provincia"], f["instituto"], f["ofertas"], f["sin_plan"], f["sitio_web"] or ""])
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cola-terciarios", action="store_true")
    argumentos = parser.parse_args()
    import psycopg

    with psycopg.connect(url_de_la_base(), autocommit=True) as conexion:
        nueva = instantanea(conexion)
        hoy = nueva["fecha"]
        vieja = anterior(hoy)
        AVANCE.mkdir(parents=True, exist_ok=True)
        (AVANCE / f"{hoy}.json").write_text(json.dumps(nueva, ensure_ascii=False, indent=1, default=str) + "\n")
        print("\n".join(diferencia(nueva, vieja)))
        if argumentos.cola_terciarios:
            print(f"cola de terciarios: {cola_terciarios(conexion)} institutos con ofertas sin plan -> {COLA}")


if __name__ == "__main__":
    main()
