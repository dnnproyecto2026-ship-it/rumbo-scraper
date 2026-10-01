"""The plans of the tertiary institutes, from their province's curricular
designs.

An institute of teacher training does not publish its plan: the province
does. Its curricular design for a career (the Province of Buenos Aires'
"Diseño Curricular Profesorado de Educación Secundaria en Matemática") is
the plan every institute of the province that gives the career follows, by
resolution. So one design is the plan of each of them: the career of that
name at every institute of the province's registry
(``relevamiento/terciarios.json``) that has no plan yet and whose site is on
the design's domain (abc.gob.ar; infd.edu.ar, where the INFoD hosts the
institutes' sites and they publish their province's designs).

A design is read by its own reader (``planes_sitios.plan_diseno_pba``: the
"Estructura curricular" table, a row per unit and year) and taken only when
it reads as the whole plan. The design's address is kept as each plan's
source (``data/<institute>_planes.json``), where the verifier checks each
unit against it.

    python -m rumbo_scraper.database.planes_disenos [--apply]
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import subprocess
import time
from collections import Counter
from typing import Any

from rumbo_scraper.database.planes_documentos import (CACHE, _FUERA_DEL_PLAN, _parece_el_plan_entero,
                                                      guardar_las_fuentes)
from rumbo_scraper.database.terciarios import REGISTRO
from rumbo_scraper.parsers import planes_sitios
from rumbo_scraper.verificacion import es_oficial

_PBA = "https://abc.gob.ar/secretarias/sites/default/files/"
_SECUNDARIA = "Profesorado de Educación Secundaria en "
_INICIAL_Y_PRIMARIA = _PBA + ("2021-05/Dise%C3%B1o%20Curricular%20Profesorado%20de%20Educaci%C3%B3n%20Inicial"
                              "%20y%20primaria.pdf")
_FISICA = _PBA + "2021-05/Dise%C3%B1o%20Curricular%20Profesorado%20de%20Educaci%C3%B3n%20F%C3%ADsica.pdf"
_ESPECIAL = _PBA + "2021-05/Dise%C3%B1o%20Curricular%20Profesorado%20de%20Educaci%C3%B3n%20Especial.pdf"
_INGLES = _PBA + ("2021-05/Dise%C3%B1o%20Curricular%20Profesorado%20de%20Educaci%C3%B3n%20Secundaria%20en"
                  "%20Ingl%C3%A9s.pdf")
_TECNICA = "Profesorado de Educación Secundaria Técnico Profesional en "
_TECNICA_MIN = "Profesorado de Educación Secundaria técnico profesional en "
_DC_TECNICA = "2023-02/Dise%C3%B1o%20Curricular%20"
_SALTA = "https://dges-sal.infd.edu.ar/sitio/wp-content/uploads/2018/07/"
# Especial: the first two years are common, then each orientation's own.
_ESPECIAL_COMUN = r"^CONTENIDOS DEL DISEÑO CURRICULAR DEL PROFESORADO DE EDUCACIÓN$"


def _especial(orientacion: str) -> Any:
    return functools.partial(planes_sitios.plan_marco_orientador, (_ESPECIAL_COMUN, r"^CONTENIDOS " + orientacion))

# The designs in force (the Dirección de Formación Docente Inicial's page
# "Diseño y desarrollo curricular"), by the career's name as the province's
# school map gives it.
DISENOS: dict[str, dict[str, tuple[str, Any]]] = {
    "Buenos Aires": {
        _SECUNDARIA + "Matemática": (_PBA + "2026-08/Matem%C3%A1tica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Lengua y Literatura": (_PBA + "2026-08/Lengua%20y%20literatura.pdf",
                                              planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Biología": (_PBA + "2024-03/Biolog%C3%ADa.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Economía": (_PBA + "2024-03/Economia.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Geografía": (_PBA + "2024-03/Geograf%C3%ADa.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Química": (_PBA + "2024-03/Qu%C3%ADmica_0.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Física": (_PBA + "2024-03/F%C3%ADsica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Filosofía": (_PBA + "2024-03/FILOSOF%C3%8DA.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Ciencia Política": (_PBA + "2024-03/C.%20Politica.pdf", planes_sitios.plan_diseno_pba),
        _SECUNDARIA + "Historia": (_PBA + "2024-03/Historia_0.pdf", planes_sitios.plan_diseno_pba),
        "Profesorado de Educación Inicial": (_INICIAL_Y_PRIMARIA,
                                             functools.partial(planes_sitios.plan_indice_pba, "Educación Inicial")),
        "Profesorado de Educación Primaria": (_INICIAL_Y_PRIMARIA,
                                              functools.partial(planes_sitios.plan_indice_pba, "Educación Primaria")),
        "Profesorado de Educación Física": (_FISICA, functools.partial(
            planes_sitios.plan_marco_orientador, (r"^3/ CONTENIDOS DEL PROFESORADO DE EDUCACIÓN FÍSICA",))),
        "Profesorado de Inglés": (_INGLES, planes_sitios.plan_formato_ubicacion),
        _TECNICA + "Electromecánica": (_PBA + "2026-07/Prof.%20Sec%20Tec.%20Prof.%20Electromecanica.pdf",
                                       planes_sitios.plan_formato_ubicacion),
        _TECNICA + "Construcciones": (_PBA + "2026-07/Prof.%20Sec%20Tec.%20Prof.%20Construcciones.pdf",
                                      planes_sitios.plan_formato_ubicacion),
        _TECNICA + "Electrónica": (_PBA + "2026-07/Prof.%20Sec%20Tec.%20Prof.%20Electronica.pdf",
                                   planes_sitios.plan_formato_ubicacion),
        _TECNICA_MIN + "Industrias de Procesos y Alimentos": (
            _PBA + _DC_TECNICA + "PROFESORADO%20DE%20EDUCACI%C3%93N%20SECUNDARIA%20T%C3%89CNICO%20PROFESIONAL"
                                 "%20EN%20INDUSTRIAS%20DE%20PROCESOS%20Y%20DE%20ALIMENTOS.pdf",
            planes_sitios.plan_formato_ubicacion),
        _TECNICA_MIN + "Producción Agropecuaria": (
            _PBA + _DC_TECNICA + "PROFESORADO%20DE%20EDUCACI%C3%93N%20SECUNDARIA%20T%C3%89CNICO%20PROFESIONAL"
                                 "%20EN%20PRODUCCI%C3%93N%20AGROPECUARIA.pdf",
            planes_sitios.plan_formato_ubicacion),
        _TECNICA_MIN + "Automotores": (
            _PBA + _DC_TECNICA + "Profesorado%20de%20Educaci%C3%B3n%20Secundaria%20T%C3%A9cnico%20Profesional"
                                 "%20en%20Automotores.pdf",
            planes_sitios.plan_formato_ubicacion),
        "Profesorado de Educación Especial Orientación en Discapacidad Intelectual": (
            _ESPECIAL, _especial("DISCAPACIDAD INTELECTUAL")),
        "Profesorado de Educación Especial Orientación en Discapacidad Neuromotora": (
            _ESPECIAL, _especial("DISCAPACIDAD NEUROMOTORA")),
        "Profesorado de Educación Especial Orientación en Ciegos y Disminuidos Visuales": (
            _ESPECIAL, _especial("CIEGOS Y DISMINUIDOS VISUALES")),
        "Profesorado de Educación Especial Orientación en Sordos e Hipoacúsicos": (
            _ESPECIAL, _especial("SORDOS E HIPOACÚSICOS")),
    },
    # Santa Fe's designs (Res. 528/09 and 529/09), as its Escuela Normal
    # Superior N° 35 publishes them on its INFoD site.
    "Santa Fe": {
        "Profesorado de Educación Primaria": (
            "https://ens35-sfe.infd.edu.ar/sitio/wp-content/uploads/2026/03/Diseno-curricular-Prof.-Ed.-Primaria-528-09.pdf",
            planes_sitios.plan_listas_sfe),
        "Profesorado de Educación Inicial": (
            "https://ens35-sfe.infd.edu.ar/sitio/wp-content/uploads/2026/03/Diseno-curricular-Prof.-Ed.-Inicial-529-09.pdf",
            planes_sitios.plan_listas_sfe),
    },
    # Salta's (Res. 537 and 538 of 2009), as its Dirección General de
    # Educación Superior publishes them on its INFoD site.
    "Salta": {
        "Profesorado de Educación Inicial": (
            _SALTA + "Disenio_Curricular_Educacion_Inicial__Resolucion_537.pdf", planes_sitios.plan_codigos_salta),
        "Profesorado de Educación Primaria": (
            _SALTA + "Disenio_Curricular_Educacion_Primaria__Resolucion_538.pdf", planes_sitios.plan_codigos_salta),
        "Profesorado de Educación Especial con Orientación en Discapacidad Intelectual": (
            _SALTA + "Disenio_Curricular_Educacion_Especial_con_Disc_Intelectual__Resolucion_539.pdf",
            planes_sitios.plan_codigos_salta),
        "Profesorado de Educación Especial con Orientación en Sordos e Hipoacúsicos": (
            _SALTA + "Disenio_Curricular_Educacion_Especial_con_Or_Sordos_e_Hipoac__Resolucion_540.pdf",
            planes_sitios.plan_codigos_salta),
        "Profesorado de Educación Especial con Orientación en Ciegos y Disminuidos Visuales": (
            _SALTA + "Disenio_Curricular_Educacion_Especial_con_Or_Ciegos_y_Dism_Visual__Resolucion_536.pdf",
            planes_sitios.plan_codigos_salta),
    },
    # Chaco's and Chubut's, as their institutes publish them on their INFoD
    # sites (Chaco: ISP "Juan Mantovani"; Chubut: IES 813 and ISFD 804).
    "Chaco": {
        "Profesorado de Educación Inicial": ("https://ispmantovani-cha.infd.edu.ar/sitio/wp-content/uploads/sitio/DISENO_PROF._EDUC_INICIAL..pdf", planes_sitios.plan_formato_ubicacion),
        "Profesorado de Educación Primaria": ("https://ispmantovani-cha.infd.edu.ar/sitio/wp-content/uploads/sitio/DISEN_O_PRIMARIA2.pdf", planes_sitios.plan_formato_ubicacion),
    },
    "Chubut": {
        "Profesorado de Educación Primaria": ("https://ies813pabloluppi-chu.infd.edu.ar/sitio/wp-content/uploads/sitio/Disen_o_Curricular_Profesorado_de_Educacion_Primaria.pdf", planes_sitios.plan_formato_ubicacion),
        "Profesorado de Educación Inicial": ("https://isfd804-chu.infd.edu.ar/sitio/wp-content/uploads/sitio/Diseno_Curricular_Nivel_Inicial_1.pdf", planes_sitios.plan_formato_ubicacion),
        "Profesorado de Educación Especial con orientación en Discapacidad Intelectual": ("https://isfd804-chu.infd.edu.ar/sitio/wp-content/uploads/sitio/Res._ME_315.14_Anexo_I_Disen_o_Curricular_Prof.Ed.Especial_Or._Disc.Int..pdf", planes_sitios.plan_formato_ubicacion),
    },
    # Tucumán's, La Rioja's and Neuquén's, as their institutes publish them.
    "Tucumán": {
        "Profesorado de Educación Primaria": ("https://iesfa-tuc.infd.edu.ar/sitio/wp-content/uploads/sitio/Disenio_Curricular_Prof.Primaria.pdf", planes_sitios.plan_formato_ubicacion),
        "Profesorado de Educación Inicial": ("https://iesmarchetti-tuc.infd.edu.ar/sitio/wp-content/uploads/sitio/Disen_o_Curricular_Educ._Inicial.pdf", planes_sitios.plan_formato_ubicacion),
    },
    "La Rioja": {
        "Profesorado de Educación Primaria": ("https://ifdcjvgonzalez-lrj.infd.edu.ar/sitio/wp-content/uploads/2019/03/Diseño-Curricular-Educación-Primaria.pdf", planes_sitios.plan_formato_ubicacion),
    },
    # Jujuy's, as the IFDC N° 3 publishes it (its "Estructura curricular").
    "Jujuy": {
        "Profesorado de Educación Primaria": (
            "https://ifdc3-juj.infd.edu.ar/sitio/wp-content/uploads/sitio/Disenio_curricular_E_primaria.pdf",
            planes_sitios.plan_estructura_jujuy),
    },
    "Neuquén": {
        "Profesorado de Educación Primaria": ("https://ifd6-nqn.infd.edu.ar/sitio/wp-content/uploads/2021/05/Disen_o_Curricular_Profesorado_de_Educacion_Primaria.pdf", planes_sitios.plan_formato_ubicacion),
    },
}
PAUSA = 2.0


def _mismo_nombre(a: str, b: str) -> bool:
    """The same career, whether its name says "Profesorado de" or
    "Profesorado en" ("Profesorado en Educación Primaria")."""
    def clave(nombre: str) -> str:
        # ... or "Educación Nivel Inicial", as the INFoD names it.
        nombre = re.sub(r"^Profesorado en ", "Profesorado de ", nombre)
        return re.sub(r"\bEducación Nivel Inicial$", "Educación Inicial", nombre).lower()
    return clave(a) == clave(b)


def leer_diseno(visitante: Any, url: str, lector: Any, carrera: str) -> list[tuple[str, int]]:
    """The design's plan, or none when it does not read as the whole plan."""
    archivo = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".pdf")
    if not archivo.exists() or archivo.stat().st_size < 1000:
        respuesta = visitante.client.get(url)
        archivo.write_bytes(respuesta.content if respuesta.status_code == 200 else b"")
        time.sleep(PAUSA)
    modo = "-bbox-layout" if getattr(lector, "cajas", False) else "-layout"
    texto = subprocess.run(["pdftotext", modo, str(archivo), "-"], capture_output=True, text=True,
                           timeout=300).stdout
    materias, vistas = [], set()
    for nombre, anio in lector(texto):
        if not _FUERA_DEL_PLAN.search(nombre) and nombre.lower() not in vistas:
            vistas.add(nombre.lower())
            materias.append((nombre, anio))
    return materias if _parece_el_plan_entero(carrera, materias, None) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Planes de los terciarios según el diseño curricular de su provincia")
    parser.add_argument("--apply", action="store_true", help="Escribir las materias en Supabase")
    parser.add_argument("--fuentes", action="store_true",
                        help="Sólo volver a escribir las fuentes de los planes ya cargados")
    args = parser.parse_args()

    from rumbo_scraper.database.supabase import get_supabase_client, select_all
    from rumbo_scraper.spiders.visitante import Visitante

    client = get_supabase_client()
    registro = json.loads(REGISTRO.read_text())
    universidades = {u["id"]: u for u in select_all(
        client.table("universidades").select("id,nombre_oficial,nombre_corto,sitio_web"))}
    materias_de: dict[str, set[str]] = {}
    for m in select_all(client.table("materias").select("carrera_id,nombre_materia")):
        if m["carrera_id"]:
            materias_de.setdefault(m["carrera_id"], set()).add(m["nombre_materia"])
    con_materias = set(materias_de)
    carreras = select_all(client.table("carreras").select("id,universidad_id,nombre_carrera"))
    planes, filas = [], []
    with Visitante(timeout=180) as visitante:
        for provincia, disenos in DISENOS.items():
            institutos = {i for i, u in universidades.items()
                          if (registro.get(u["nombre_oficial"]) or {}).get("jurisdiccion") == provincia}
            for carrera_nombre, (url, lector) in disenos.items():
                materias = leer_diseno(visitante, url, lector, carrera_nombre)
                # Only where the design is on the institute's own domain: that is
                # where the verifier reads its source.
                destino = [c for c in carreras if c["universidad_id"] in institutos
                           and _mismo_nombre(c["nombre_carrera"], carrera_nombre)
                           and (args.fuentes or c["id"] not in con_materias)
                           and es_oficial(url, universidades[c["universidad_id"]]["sitio_web"])]
                print(f"{provincia:14} {carrera_nombre[:55]:55} {len(materias):3} materias "
                      f"{dict(Counter(a for _, a in materias))} -> {len(destino)} institutos", flush=True)
                if not materias:
                    continue
                for carrera in destino:
                    # With --fuentes, only a career whose plan is this design's.
                    if args.fuentes and materias_de.get(carrera["id"]) != {n for n, _ in materias}:
                        continue
                    universidad = universidades[carrera["universidad_id"]]
                    # The source goes under the institute's own name for the
                    # career ("Profesorado de Educación Nivel Inicial"): that is
                    # the name the verifier looks it up by.
                    planes.append({"universidad": universidad["nombre_corto"], "documento": url,
                                   "carrera": {"nombre_carrera": carrera["nombre_carrera"]}})
                    filas += [{"universidad_id": carrera["universidad_id"], "carrera_id": carrera["id"],
                               "nombre_materia": nombre, "anio_cursada": anio} for nombre, anio in materias]
    if args.fuentes:
        # Only the careers whose plan is this design's: a career loaded from
        # elsewhere keeps its own source.
        guardar_las_fuentes(planes)
        print(f"Fuentes: {len(planes)}")
        return
    if args.apply and filas:
        for inicio in range(0, len(filas), 500):
            client.table("materias").insert(filas[inicio:inicio + 500]).execute()
        guardar_las_fuentes(planes)
    print(f"Planes: {len(planes)}; materias {'cargadas' if args.apply else 'a cargar'}: {len(filas)}")


if __name__ == "__main__":
    main()
