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
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from rumbo_scraper.normalizers.text import comparison_key

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


_UN_CICLO = re.compile(
    r"\bccc\b|\bciclos? de (?:complementacion|licenciatura|profesorado)\b|"
    r"complementacion curricular|\((?:ciclo|complementacion)\b|licenciatura \(ciclo\)")


def es_un_ciclo(nombre: str) -> bool:
    return bool(_UN_CICLO.search(comparison_key(nombre)))


# --- the name a career is shown under ---------------------------------------
#
# The same career reached the database several times over, because each site
# names its variants as if they were careers of their own: "Abogacía" and
# "Abogacía a distancia", "Contador Público" and "Contador Público (Pilar)",
# "Arquitectura" and "Arquitectura (9)", "Ingeniería Electrónica" and
# "Ingeniería en Electrónica". A student sees one career. Here each name is
# brought to the career it names, the modality and the campus it carried are
# kept on the offer, and careers that come out the same are merged.

_MODALIDAD_EN_EL_NOMBRE = re.compile(
    r"\s*[\(\-–]?\s*(?:modalidad\s+)?(?P<modo>a distancia|online|virtual|semipresencial|"
    r"presencial)\s*[\)\-–]?\s*$", re.I)
_COLA_PUBLICITARIA = re.compile(
    r"\s+(?:conoc[ée] la carrera|la um est[áa] donde vos est[áa]s|en la cat[óo]lica)\s*$", re.I)
_SIN_MAYUSCULA = frozenset("de del la las los el y e en a al con para por o u".split())
_STOP = frozenset("de del la las los el y e en con".split())
# A block of subjects published as if it were a degree: "Arquitectura I a V y PFC".
_UN_BLOQUE_DE_MATERIAS = re.compile(r"\b[ivx]+ a [ivx]+\b")


def _titulo(nombre: str) -> str:
    """ "CONTADOR PÚBLICO" -> "Contador Público"; leaves mixed case alone."""
    palabras = nombre.split()
    salida = []
    for i, palabra in enumerate(palabras):
        # Four letters or fewer in capitals is an acronym: "TUIB", "IAG", "UBA".
        sigla = len(palabra.strip("()")) <= 4 and palabra.lower() not in _SIN_MAYUSCULA
        if palabra.isupper() and len(palabra) > 1 and not sigla:
            minuscula = palabra.lower()
            palabra = minuscula if i and minuscula in _SIN_MAYUSCULA else minuscula.capitalize()
        elif palabra.isupper() and palabra.lower() in _SIN_MAYUSCULA and i:
            palabra = palabra.lower()
        salida.append(palabra)
    return " ".join(salida)


def nombre_de_la_carrera(nombre: str, sedes: list[str]) -> tuple[str, str | None, str | None]:
    """The career a name names, and the modality and campus it carried."""
    n = re.sub(r"^[^\wÁÉÍÓÚÑáéíóúñ¿¡]+|^_+", "", nombre or "").strip()
    n = _COLA_PUBLICITARIA.sub("", n)
    modalidad = None
    m = _MODALIDAD_EN_EL_NOMBRE.search(n)
    if m and m.start() > 0:
        modo = comparison_key(m.group("modo"))
        modalidad = {"online": "a distancia", "virtual": "a distancia"}.get(modo, modo)
        n = n[:m.start()]
    n = re.sub(r"\s*\(\d+\)$", "", n)
    # The acronym a site puts after the name: "... Sexual Integral (ESI)".
    n = re.sub(r"\s*\([A-ZÁÉÍÓÚÑ]{2,8}\)$", "", n)
    n = re.sub(r"(?i)\s*\(compartid[oa] con[^)]*\)$", "", n)
    sede = None
    m = re.search(r"\s*\(([^)]*)\)$", n)
    if m:
        dentro = comparison_key(m.group(1))
        encontrada = next((s for s in sedes if dentro and dentro in comparison_key(s)), None)
        if encontrada:
            sede, n = encontrada, n[:m.start()]
    n = re.sub(r"^Lic\.?\s+en\s+", "Licenciatura en ", n).rstrip(" +-–")
    n = _titulo(" ".join(n.split()))
    # "ingenieria electrica": a name written all in lower case gets its capital.
    if n and n[0].islower():
        n = n[0].upper() + n[1:]
    return n, modalidad, sede


def clave_de_carrera(nombre: str) -> str:
    """Two names of one career share this: accents, punctuation, connecting
    words and word order left out."""
    palabras = re.findall(r"[a-z0-9]+", comparison_key(nombre).replace("licenciatura", "lic"))
    return " ".join(sorted({p for p in palabras if p not in _STOP}))


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

    # A completion cycle ("CCC Licenciatura en ...", "Ciclo de Complementación
    # Curricular ...") takes a student who already holds a tecnicatura or a
    # teaching degree; nobody leaving secondary school can start one. They
    # stay in this database and out of the application's catalogue, with
    # their subjects.
    ciclos = {c["id"] for c in carreras if es_un_ciclo(c["nombre_carrera"])}
    carreras = [c for c in carreras if c["id"] not in ciclos]
    carrera_nombre = {c["id"]: c["nombre_carrera"] for c in carreras}

    sedes_de: dict[str, list[str]] = defaultdict(list)
    for s_ in sedes:
        sedes_de[s_["universidad_id"]].append(s_["nombre_sede"])
    # Each career under the name of the career it is, merged with the others
    # of its university that come out the same.
    representante: dict[tuple[str, str], str] = {}
    for c in sorted(carreras, key=lambda c: len(c["nombre_carrera"])):
        uid = c["universidad_id"]
        if _UN_BLOQUE_DE_MATERIAS.search(comparison_key(c["nombre_carrera"])):
            continue
        base, modalidad_del_nombre, sede_del_nombre = nombre_de_la_carrera(
            c["denominacion_canonica"] or c["nombre_carrera"], sedes_de[uid])
        if not base:
            continue
        clave = (uid, clave_de_carrera(base))
        nuevo = clave not in representante
        nombre = representante.setdefault(clave, base)
        carrera_nombre[c["id"]] = nombre
        facultad = facultades.get(c["facultad_id"])
        facultad_nombre = facultad["nombre_facultad"] if facultad else None
        if nuevo:
            por_uni[uid]["carreras"].append({
                "nombre_carrera": nombre, "denominacion_canonica": nombre,
                "nivel": c["nivel"], "titulo_otorgado": c["titulo_otorgado"],
                "duracion_anios": c["duracion_anios"],
                "descripcion_breve": c["descripcion_breve"],
                "facultad_nombre": facultad_nombre,
            })
        propias = ofertas_por_carrera.get(c["id"]) or [None]
        for o in propias:
            por_uni[uid]["ofertas"].append({
                "carrera_nombre": nombre,
                "sede": (sede_nombre.get(o["sede_id"]) if o else None) or sede_del_nombre,
                "facultad_nombre": facultad_nombre,
                "modalidad": modalidad_del_nombre or (o["modalidad"] if o else None),
                "regimen_ingreso": o["regimen_ingreso"] if o else None,
                "url_oficial": (o and o["url_oficial"])
                or urls.get((nombre_uni[uid], c["nombre_carrera"])),
            })

    vistos_posgrado: dict[tuple[str, str], str] = {}
    for p in sorted(posgrados, key=lambda p: len(p["nombre_programa"])):
        base, modalidad_del_nombre, _ = nombre_de_la_carrera(
            p["nombre_programa"], sedes_de[p["universidad_id"]])
        if not base:
            continue
        clave = (p["universidad_id"], clave_de_carrera(base))
        nuevo = clave not in vistos_posgrado
        posgrado_nombre[p["id"]] = vistos_posgrado.setdefault(clave, base)
        if not nuevo:
            continue
        facultad = facultades.get(p["facultad_id"])
        por_uni[p["universidad_id"]]["posgrados"].append({
            "nombre_programa": base, "tipo_posgrado": p["tipo_posgrado"],
            "titulo_otorgado": p["titulo_otorgado"],
            "modalidad": modalidad_del_nombre or p["modalidad"],
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

    # Los turnos de cada oferta, que van a la oferta de la aplicación.
    turnos_por_oferta: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fila in todo("turnos_anio"):
        turnos_por_oferta[fila["oferta_id"]].append(
            {"anio": fila["anio_carrera"], "turno": fila["turno"]})
    for o in ofertas:
        if not turnos_por_oferta.get(o["id"]):
            continue
        carrera = next((c for c in carreras if c["id"] == o["carrera_id"]), None)
        if carrera:
            por_uni[carrera["universidad_id"]]["turnos"].append({
                "carrera_nombre": carrera["nombre_carrera"],
                "sede": sede_nombre.get(o["sede_id"]),
                "turnos": turnos_por_oferta[o["id"]]})

    # Los docentes y las materias que dictan. La materia sale del catálogo
    # semestral por su nombre, que es como la aplicación la encuentra; el
    # contenido de la comisión es la única descripción de materia relevada.
    catalogo = {m["id"]: m for m in todo("materias_catalogo")}
    comisiones = {c["id"]: c for c in todo("comisiones_materia")}
    dicta: dict[str, set[str]] = defaultdict(set)
    for fila in todo("docentes_comision"):
        comision = comisiones.get(fila["comision_id"])
        materia = catalogo.get(comision["materia_catalogo_id"]) if comision else None
        if materia and fila["persona_id"]:
            dicta[fila["persona_id"]].add(materia["nombre"])
    descripciones: dict[tuple[str, str], str] = {}
    for comision in comisiones.values():
        materia = catalogo.get(comision["materia_catalogo_id"])
        if materia and comision["contenido"]:
            descripciones.setdefault((materia["universidad_id"], materia["nombre"]),
                                     comision["contenido"])
    for (uid, nombre), texto in descripciones.items():
        por_uni[uid]["descripciones_materias"].append({"materia": nombre, "descripcion": texto})
    for persona in todo("personas"):
        if not persona["universidad_id"] or persona["activa"] is False:
            continue
        por_uni[persona["universidad_id"]]["docentes"].append({
            "nombre": persona["nombre_completo"],
            "biografia": persona["biografia"] or persona["formacion"],
            "perfil_url": persona["perfil_url"],
            "materias": sorted(dicta.get(persona["id"], ())),
        })

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
                "convenios_intercambio", "alojamientos", "docentes",
                "descripciones_materias", "turnos")},
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
                          "convenios_intercambio", "alojamientos", "docentes",
                          "descripciones_materias", "turnos")))
    print(f"Archivo: {args.output}")


if __name__ == "__main__":
    main()
