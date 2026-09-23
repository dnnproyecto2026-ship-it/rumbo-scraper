"""Export the corrected catalogue, as the application's importer reads it.

The application (``~/Desktop/Rumbo``) imports the catalogue with
``database/scripts/importar_scraper.py``, which read the ``*_completo.json``
artifacts. Those are what each reading found, before the corrections applied
in this database afterwards: the sibling pages taken for careers, the lines
taken for addresses, the plans read later for the adapters, UCES's and
Favaloro's postgraduates. The database is the corrected catalogue, so this
writes it out whole in the shape the importer already understands, one entry
per university with the sections of the contract under ``datos``.

Student life, authorities and contacts go too, since the application's
migration 0028 gave them tables of their own.

    python -m rumbo_scraper.database.exportar_catalogo
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SALIDA = Path("data/catalogo_depurado.json")


def _urls_de_los_artefactos() -> dict[tuple[str, str], str]:
    """The page of each career, which only the readings kept.

    ``ofertas_academicas`` holds the address of the 663 offers that have a
    campus; the rest of the careers have theirs in the reading that found
    them, under the same name the database gives them.
    """
    urls: dict[tuple[str, str], str] = {}
    for archivo in glob.glob("data/*_completo.json"):
        try:
            datos = json.loads(Path(archivo).read_text(encoding="utf-8"))["datos"]
            universidad = datos["universidades"][0]["nombre_oficial"]
        except (KeyError, IndexError, ValueError):
            continue
        for oferta in datos.get("ofertas") or []:
            if oferta.get("url_oficial") and oferta.get("carrera_nombre"):
                urls.setdefault((universidad, oferta["carrera_nombre"]), oferta["url_oficial"])
    return urls


def exportar(client: Any) -> dict[str, Any]:
    from rumbo_scraper.database.supabase import select_all

    def todo(tabla: str, columnas: str = "*") -> list[dict[str, Any]]:
        return select_all(client.table(tabla).select(columnas))

    universidades = todo("universidades")
    sedes = todo("sedes")
    facultades = {f["id"]: f for f in todo("facultades")}
    carreras = todo("carreras")
    posgrados = todo("posgrados")
    ofertas = todo("ofertas_academicas")
    materias = todo("materias", "universidad_id,carrera_id,posgrado_id,nombre_materia,"
                                "anio_cursada,descripcion_breve")
    becas = todo("becas")
    localidades = {l["id"]: l["nombre_localidad"] for l in todo("localidades")}
    urls = _urls_de_los_artefactos()

    por_uni: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    sede_nombre = {s["id"]: s["nombre_sede"] for s in sedes}
    carrera_nombre = {c["id"]: c["nombre_carrera"] for c in carreras}
    posgrado_nombre = {p["id"]: p["nombre_programa"] for p in posgrados}
    nombre_uni = {u["id"]: u["nombre_oficial"] for u in universidades}

    for s in sedes:
        por_uni[s["universidad_id"]]["sedes"].append({
            "nombre_sede": s["nombre_sede"], "calle": s["calle"],
            "numero": str(s["numero"]) if s["numero"] is not None else None,
            "localidad": localidades.get(s["localidad_id"]),
        })
    for f in facultades.values():
        por_uni[f["universidad_id"]]["facultades"].append({
            "nombre_facultad": f["nombre_facultad"], "tipo_unidad": f["tipo_unidad"]})

    ofertas_por_carrera: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in ofertas:
        ofertas_por_carrera[o["carrera_id"]].append(o)

    for c in carreras:
        uid = c["universidad_id"]
        facultad = facultades.get(c["facultad_id"])
        facultad_nombre = facultad["nombre_facultad"] if facultad else None
        por_uni[uid]["carreras"].append({
            "nombre_carrera": c["nombre_carrera"],
            "denominacion_canonica": c["denominacion_canonica"],
            "nivel": c["nivel"], "titulo_otorgado": c["titulo_otorgado"],
            "duracion_anios": c["duracion_anios"],
            "descripcion_breve": c["descripcion_breve"],
            "facultad_nombre": facultad_nombre,
        })
        propias = ofertas_por_carrera.get(c["id"]) or [None]
        for o in propias:
            por_uni[uid]["ofertas"].append({
                "carrera_nombre": c["nombre_carrera"],
                "sede": sede_nombre.get(o["sede_id"]) if o else None,
                "facultad_nombre": facultad_nombre,
                "modalidad": o["modalidad"] if o else None,
                "regimen_ingreso": o["regimen_ingreso"] if o else None,
                "url_oficial": (o and o["url_oficial"])
                or urls.get((nombre_uni[uid], c["nombre_carrera"])),
            })

    for p in posgrados:
        facultad = facultades.get(p["facultad_id"])
        por_uni[p["universidad_id"]]["posgrados"].append({
            "nombre_programa": p["nombre_programa"], "tipo_posgrado": p["tipo_posgrado"],
            "titulo_otorgado": p["titulo_otorgado"], "modalidad": p["modalidad"],
            "duracion_meses": p["duracion_meses"], "url_oficial": p["url_oficial"],
            "descripcion_breve": p["descripcion_breve"], "sede": sede_nombre.get(p["sede_id"]),
            "facultad_nombre": facultad["nombre_facultad"] if facultad else None,
        })

    for m in materias:
        programa = carrera_nombre.get(m["carrera_id"]) or posgrado_nombre.get(m["posgrado_id"])
        if not programa:
            continue
        por_uni[m["universidad_id"]]["materias"].append({
            "nombre_materia": m["nombre_materia"], "carrera_o_programa": programa,
            "anio_cursada": m["anio_cursada"], "descripcion_breve": m["descripcion_breve"],
        })

    for b in becas:
        por_uni[b["universidad_id"]]["becas"].append({
            "nombre_beca": b["nombre_beca"], "tipo_beca": b["tipo_beca"],
            "cobertura_descripcion": b["cobertura_descripcion"],
            "porcentaje_maximo": b["porcentaje_maximo"], "requisitos": b["requisitos"],
            "proceso_postulacion": b["proceso_postulacion"], "fecha_cierre": b["fecha_cierre"],
            "url": b["url_postulacion"] or b["fuente_url"],
        })

    carrera_de = {c["id"]: c["nombre_carrera"] for c in carreras}
    for fila in todo("contactos"):
        facultad = facultades.get(fila["facultad_id"])
        por_uni[fila["universidad_id"]]["contactos"].append({
            "canal": fila["canal"], "valor": fila["usuario_o_direccion"],
            "facultad_nombre": facultad["nombre_facultad"] if facultad else None})
    for fila in todo("autoridades"):
        facultad = facultades.get(fila["facultad_id"])
        if not facultad:
            continue
        por_uni[facultad["universidad_id"]]["autoridades"].append({
            "nombre": fila["nombre_autoridad"], "cargo": fila["cargo"], "tipo": fila["tipo"],
            "facultad_nombre": facultad["nombre_facultad"]})
    for tabla, nombre in (("servicios_estudiantiles", "nombre_servicio"),
                          ("actividades_extracurriculares", "nombre_actividad")):
        for fila in todo(tabla):
            por_uni[fila["universidad_id"]][tabla].append({
                "nombre": fila[nombre], "categoria": fila["categoria"],
                "descripcion": fila["descripcion"], "url": fila["url"],
                "fuente_url": fila["fuente_url"]})
    for fila in todo("programas_internacionales"):
        por_uni[fila["universidad_id"]]["programas_internacionales"].append({
            "nombre": fila["nombre_programa"], "tipo": fila["tipo_programa"],
            "nivel": fila["nivel"], "requisitos": fila["requisitos"],
            "reconocimiento_academico": fila["reconocimiento_academico"],
            "url": fila["url"], "fuente_url": fila["fuente_url"]})
    for fila in todo("convenios_intercambio"):
        por_uni[fila["universidad_id"]]["convenios_intercambio"].append({
            "carrera_origen": fila["programa_origen"] or carrera_de.get(fila["carrera_id"]),
            "universidad_destino": fila["universidad_destino"], "pais": fila["pais"],
            "ciudad": fila["ciudad"], "fuente_url": fila["fuente_url"]})
    for fila in todo("alojamientos"):
        por_uni[fila["universidad_id"]]["alojamientos"].append({
            "tipo": fila["tipo_alojamiento"], "descripcion": fila["descripcion"],
            "residencia_propia": fila["residencia_propia"], "url": fila["url"],
            "fuente_url": fila["fuente_url"]})

    salida = []
    for u in sorted(universidades, key=lambda u: u["nombre_oficial"]):
        datos = por_uni[u["id"]]
        salida.append({"datos": {
            "universidades": [{
                "nombre_oficial": u["nombre_oficial"], "nombre_corto": u["nombre_corto"],
                "tipo_gestion": u["tipo_gestion"], "sitio_web": u["sitio_web"],
                "anio_fundacion": u["anio_fundacion"],
            }],
            **{seccion: list(datos.get(seccion, [])) for seccion in
               ("sedes", "facultades", "carreras", "ofertas", "materias", "posgrados", "becas",
                "contactos", "autoridades", "servicios_estudiantiles",
                "actividades_extracurriculares", "programas_internacionales",
                "convenios_intercambio", "alojamientos")},
        }})
    return {"universidades": salida}


def main() -> None:
    parser = argparse.ArgumentParser(description="Exportar el catálogo corregido")
    parser.add_argument("--output", type=Path, default=SALIDA)
    args = parser.parse_args()
    from rumbo_scraper.database.supabase import get_supabase_client
    catalogo = exportar(get_supabase_client())
    args.output.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    for entrada in catalogo["universidades"]:
        d = entrada["datos"]
        print(f"{d['universidades'][0]['nombre_corto'] or '':10} "
              + " ".join(f"{k}={len(d[k])}" for k in
                         ("sedes", "facultades", "carreras", "materias", "posgrados",
                          "becas", "contactos", "autoridades", "servicios_estudiantiles",
                          "actividades_extracurriculares", "programas_internacionales",
                          "convenios_intercambio", "alojamientos")))
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
