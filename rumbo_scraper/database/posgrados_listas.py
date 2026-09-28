"""Load a university's postgraduate careers from the page that lists them.

The universities loaded from their career guides have their grado and
pregrado careers and no postgraduate one: a guide of careers does not list
them. Each has a page that does (`parsers.posgrados_listas`), and that page is
what is read here. A programme is written with the link the page gives it,
or with the page itself where it links nowhere, so the verifier can find the
name where it was read.

A programme already stored under the same name is updated, and one the
page no longer lists stays, unless ``--reemplazar`` says the reading is the
whole of the university's postgraduates: then the rest are deleted, with
their subjects. A reading that comes back with fewer programmes than the
university is known to teach is not written.

    python -m rumbo_scraper.database.posgrados_listas UNS UNL [--apply [--reemplazar]]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rumbo_scraper.catalogo import Universidad
from rumbo_scraper.normalizers.text import comparison_key
from rumbo_scraper.parsers.posgrados_listas import PosgradoListado, leer_lista


@dataclass(frozen=True)
class Pagina:
    url: str
    # The part of the page that holds the list, where menus list other things.
    ambito: str | None = None
    # The unit that teaches what the page lists, when the page is a unit's.
    facultad: str | None = None
    # The kind a heading gives a list of bare subjects: "Especialización en".
    prefijo: str | None = None


@dataclass(frozen=True)
class Lista:
    nombre_oficial: str
    dominio: str
    paginas: tuple[Pagina, ...]
    # Fewer than this is a page that came back short.
    minimo: int
    dominios_extra: tuple[str, ...] = ()
    navegador: bool = False


LISTAS: dict[str, Lista] = {
    # Cards of every faculty's programmes, each linking to the faculty's page.
    "UNCuyo": Lista("Universidad Nacional de Cuyo", "uncuyo.edu.ar",
                    (Pagina("https://www.uncuyo.edu.ar/estudios/posgrados"),), 70),
    # Two cards hidden with display:none are programmes no longer offered.
    "UNPA": Lista("Universidad Nacional de la Patagonia Austral", "unpa.edu.ar",
                  (Pagina("https://www.unpa.edu.ar/carreraspostgrado",
                          ambito='#itemcarrerapostgrado:not([style*="display:none"])'),), 7),
    "UPSO": Lista("Universidad Provincial del Sudoeste", "upso.edu.ar",
                  (Pagina("https://www.upso.edu.ar/carreras/"),), 1),
    # The list arrives by a request the page's script makes.
    "UNS": Lista("Universidad Nacional del Sur", "uns.edu.ar",
                 (Pagina("https://www.uns.edu.ar/academicas/carreras/oferta-academica_carreras-postgrado"),),
                 54, navegador=True),
    "UPC": Lista("Universidad Provincial de Córdoba", "upc.edu.ar",
                 (Pagina("https://www.upc.edu.ar/posgrado/"),), 6),
    "UNRN": Lista("Universidad Nacional de Río Negro", "unrn.edu.ar",
                  (Pagina("https://www.unrn.edu.ar/carreras.php?id=2"),), 21),
    # One page per kind; each name is the heading of its card.
    "UNNE": Lista("Universidad Nacional del Nordeste", "unne.edu.ar", tuple(
        Pagina(f"https://www.unne.edu.ar/estudiar/posgrado/{tipo}/", ambito=".elementor-widget-heading")
        for tipo in ("doctorados", "maestrias", "especializaciones")), 70),
    # The main site's career filter shows no postgraduate; its office's does.
    "UNCAUS": Lista("Universidad Nacional del Chaco Austral", "uncaus.edu.ar",
                    (Pagina("https://posgrado.uncaus.edu.ar/ofertas", ambito=".course_title_container"),), 6),
    "UADER": Lista("Universidad Autónoma de Entre Ríos", "uader.edu.ar",
                   (Pagina("https://uader.edu.ar/comunidad-uader/posgrado",
                           ambito=".field--name-node-title"),), 11),
    # Its postgraduates live at /diplomaturas/.
    "UNAB": Lista("Universidad Nacional Guillermo Brown", "unab.edu.ar",
                  (Pagina("https://www.unab.edu.ar/diplomaturas/"),), 4),
    "UNViMe": Lista("Universidad Nacional de Villa Mercedes", "unvime.edu.ar",
                    (Pagina("https://www.unvime.edu.ar/sec-posgrado/publicaciones-de-posgrado/"),), 1),
    # Image cards, named only by their links' titles.
    "UNRaf": Lista("Universidad Nacional de Rafaela", "unraf.edu.ar",
                   (Pagina("https://unraf.edu.ar/que-estudio/posgrados",
                           ambito=".com-content-category-blog__items"),), 6),
    "UNLZ": Lista("Universidad Nacional de Lomas de Zamora", "unlz.edu.ar",
                  (Pagina("https://www.unlz.edu.ar/?page_id=2427"),), 24),
    # The current offer, each kind in an accordion; the committees' page is not it.
    "UNNOBA": Lista("Universidad Nacional del Noroeste de la Provincia de Buenos Aires", "unnoba.edu.ar",
                    (Pagina("https://www.unnoba.edu.ar/instituto-de-posgrado-vigente/",
                            ambito="details li, details p"),), 10),
    "UNLPam": Lista("Universidad Nacional de La Pampa", "unlpam.edu.ar",
                    (Pagina("https://www.unlpam.edu.ar/ingresantes?showall=&start=1", ambito="li.posgr"),), 22),
    # Each faculty's offer, one accordion entry per career.
    "UNDEF": Lista("Universidad de la Defensa Nacional", "undef.edu.ar", tuple(
        Pagina(f"https://undef.edu.ar/oferta-academica/{pagina}/",
               ambito="summary.e-n-accordion-item-title", facultad=facultad)
        for pagina, facultad in (
            ("oferta-academica-facultad-del-ejercito", "Facultad del Ejército"),
            ("oferta-academica-facultad-dela-armada", "Facultad de la Armada"),
            ("oferta-academica-facultad-dela-fuerza-aerea", "Facultad de la Fuerza Aérea"),
            ("oferta-academica-facultad-militar-conjunta", "Facultad Militar Conjunta"),
            ("oferta-academica-fadena", "Facultad de la Defensa Nacional"),
            ("oferta-academica-facultad-de-ingenieria-del-ejercito", "Facultad de Ingeniería del Ejército"),
            ("oferta-academica-facultad-de-ingenieria-del-cruc-iua", "Facultad de Ingeniería (CRUC-IUA)"),
        )), 27),
    # No central list: each faculty's own. Económicas publishes its offer on
    # a domain that is not the university's, and Naturales none.
    "UNPSJB": Lista("Universidad Nacional de la Patagonia San Juan Bosco", "unp.edu.ar", (
        Pagina("http://www.ing.unp.edu.ar/posgrados.html", ambito="a.grpelem", facultad="Facultad de Ingeniería"),
        Pagina("http://www.fhcs.unp.edu.ar/posgrado/maestrias/",
               facultad="Facultad de Humanidades y Ciencias Sociales"),
        Pagina("http://www.fhcs.unp.edu.ar/posgrado/especializaciones/",
               facultad="Facultad de Humanidades y Ciencias Sociales"),
        Pagina("https://www.fhcs.unp.edu.ar/posgrado/doctorado-en-ciencias-sociales-y-humanas-2/",
               ambito=".zak-page-header__title", facultad="Facultad de Humanidades y Ciencias Sociales"),
        Pagina("http://www.fcj.unp.edu.ar/index.php/ofertacademic/postgrados",
               facultad="Facultad de Ciencias Jurídicas"),
    ), 11),
    "UNTDF": Lista("Universidad Nacional de Tierra del Fuego, Antártida e Islas del Atlántico Sur",
                   "untdf.edu.ar", (Pagina("https://www.untdf.edu.ar/posgrado/carreras-de-posgrado/",
                                           ambito="ul.section-local-nav__list"),), 4),
    # Cards drawn by the page's script from an array in the page.
    "UNSL": Lista("Universidad Nacional de San Luis", "unsl.edu.ar",
                  (Pagina("https://carreras.unsl.edu.ar/carreras/?tipo=posgrado"),), 45, navegador=True),
    # Paginated; the campus sits beside each title.
    "UNICEN": Lista("Universidad Nacional del Centro de la Provincia de Buenos Aires", "unicen.edu.ar", tuple(
        Pagina(f"https://www.unicen.edu.ar/content/estudios-de-postgrado{pagina}",
               ambito=".view-content .views-field-title") for pagina in ("", "?page=1")), 21),
    "UNL": Lista("Universidad Nacional del Litoral", "unl.edu.ar",
                 (Pagina("https://www.unl.edu.ar/propuesta-academica/?f=posgrado"),), 80),
    "UNRC": Lista("Universidad Nacional de Río Cuarto", "unrc.edu.ar",
                  (Pagina("https://www.unrc.edu.ar/unrc/posgrado/carreras-posgrado.php"),), 21),
    # The postgraduate office's offer, eight pages of cards.
    "UNComa": Lista("Universidad Nacional del Comahue", "uncoma.edu.ar", tuple(
        Pagina(f"https://posgrado.uncoma.edu.ar/oferta-academica/{pagina}", ambito=".e-loop-item")
        for pagina in ["", *(f"{i}/" for i in range(2, 9))]), 50),
    # Expo Posgrado, faculty by faculty: the office's own list names three.
    "UNT": Lista("Universidad Nacional de Tucumán", "unt.edu.ar", tuple(
        Pagina(f"https://www.unt.edu.ar/expoposgrado/facultades/{slug}/", facultad=facultad)
        for slug, facultad in (
            ("facultad-de-agronomia-y-zootecnica", "Facultad de Agronomía, Zootecnia y Veterinaria"),
            ("facultad-de-ciencias-exactas-y-tecnologia", "Facultad de Ciencias Exactas y Tecnología"),
            ("filosofia-y-letras", "Facultad de Filosofía y Letras"),
            ("facultad-de-arquitectura-y-urbanismo", "Facultad de Arquitectura y Urbanismo"),
            ("facultad-de-ciencias-naturales_eiml", "Facultad de Ciencias Naturales e IML"),
            ("facultad-de-medicina", "Facultad de Medicina"),
            ("facultad-de-artes", "Facultad de Artes"),
            ("facultad-de-derecho", "Facultad de Derecho y Ciencias Sociales"),
            ("facultad-de-odontologia", "Facultad de Odontología"),
            ("facultad-de-bioquimica-quimica-y-farmacia", "Facultad de Bioquímica, Química y Farmacia"),
            ("facultad-de-educacion-fisica", "Facultad de Educación Física"),
            ("facultad-de-psicologia", "Facultad de Psicología"),
            ("facultad-de-ciencias-economicas", "Facultad de Ciencias Económicas"),
        )), 64),
    "UNIPE": Lista("Universidad Pedagógica Nacional", "unipe.edu.ar",
                   (Pagina("https://unipe.edu.ar/posgrado-2026/carreras-posgrado", ambito="h3.catItemTitle"),), 5),
    # The main site does not answer; each faculty's posgrado page does.
    "UNaM": Lista("Universidad Nacional de Misiones", "unam.edu.ar", (
        Pagina("https://www.fceqyn.unam.edu.ar/posgrado/",
               facultad="Facultad de Ciencias Exactas, Químicas y Naturales"),
        Pagina("https://www.fce.unam.edu.ar/carreras/posgrado/", facultad="Facultad de Ciencias Económicas"),
        Pagina("https://www.fayd.unam.edu.ar/la-facu/secretarias/posgrado", facultad="Facultad de Arte y Diseño"),
        Pagina("https://www.fcf.unam.edu.ar/la-facultad/secretarias/posgrado/",
               facultad="Facultad de Ciencias Forestales"),
        Pagina("https://www.fio.unam.edu.ar/index.php?option=com_content&view=article&id=259:"
               "secretaria-de-posgrado&catid=77&Itemid=559", facultad="Facultad de Ingeniería"),
        Pagina("https://www.fhycs.unam.edu.ar/portada/secretaria-de-posgrado/",
               facultad="Facultad de Humanidades y Ciencias Sociales"),
    ), 42),
    # Económicas builds its page in the browser; Tecnología lists its
    # programmes only in its menu. Exactas' menu merges two names in one.
    "UNCA": Lista("Universidad Nacional de Catamarca", "unca.edu.ar", (
        Pagina("https://agrarias.unca.edu.ar/?page_id=27256", ambito=".elementor-icon-box-title",
               facultad="Facultad de Ciencias Agrarias"),
        Pagina("https://huma.unca.edu.ar/oferta-academica/posgrado", ambito="article.item li",
               facultad="Facultad de Humanidades"),
        Pagina("https://eco.unca.edu.ar/posgrado", facultad="Facultad de Ciencias Económicas y de Administración"),
        Pagina("https://tecno.unca.edu.ar/", ambito="#nav-topbar",
               facultad="Facultad de Tecnología y Ciencias Aplicadas"),
    ), 14, navegador=True),
    # The central page joins two programmes in one link; Sociales and Humanas
    # are read from their own pages.
    "UNVM": Lista("Universidad Nacional de Villa María", "unvm.edu.ar", (
        Pagina("https://www.unvm.edu.ar/unidades-academicas/", ambito=".et_pb_accordion_item_1",
               facultad="Instituto Académico Pedagógico de Ciencias Básicas y Aplicadas"),
        Pagina("https://sociales.unvm.edu.ar/posgrado/", ambito="#menu-item-32474",
               facultad="Instituto Académico Pedagógico de Ciencias Sociales"),
        Pagina("https://humanas.unvm.edu.ar/carreras/posgrados/",
               facultad="Instituto Académico Pedagógico de Ciencias Humanas"),
        # Básicas' own page lists its postgraduates only in the menu.
        Pagina("https://basicas.unvm.edu.ar/posgrados/", ambito="nav.main_menu",
               facultad="Instituto Académico Pedagógico de Ciencias Básicas y Aplicadas"),
    ), 16),
    "UNSE": Lista("Universidad Nacional de Santiago del Estero", "unse.edu.ar",
                  (Pagina("https://www.unse.edu.ar/carreras-de-posgrado/"),), 19),
    "UNSa": Lista("Universidad Nacional de Salta", "unsa.edu.ar",
                  (Pagina("https://www.unsa.edu.ar/posgrado/", ambito=".eael-accordion-header"),), 29),
    "UNLu": Lista("Universidad Nacional de Luján", "unlu.edu.ar",
                  (Pagina("https://www.unlu.edu.ar/posgrado.html"),), 22),
    # No central list. Alimentación and Trabajo Social list theirs only in
    # their menus.
    "UNER": Lista("Universidad Nacional de Entre Ríos", "uner.edu.ar", (
        Pagina("https://www.fcad.uner.edu.ar/", facultad="Facultad de Ciencias de la Administración"),
        Pagina("https://posgrado.ingenieria.uner.edu.ar/", facultad="Facultad de Ingeniería"),
        Pagina("https://fca.uner.edu.ar/posgrado/", facultad="Facultad de Ciencias Agropecuarias"),
        Pagina("https://www.fceco.uner.edu.ar/?page_id=19917", facultad="Facultad de Ciencias Económicas"),
        Pagina("https://www.fcedu.uner.edu.ar/carreras/", facultad="Facultad de Ciencias de la Educación"),
        Pagina("https://www.fb.uner.edu.ar/carreras-3/", facultad="Facultad de Bromatología"),
        Pagina("https://fcs.uner.edu.ar/carreras/", facultad="Facultad de Ciencias de la Salud"),
        Pagina("https://fcal.uner.edu.ar/", ambito="#top-header",
               facultad="Facultad de Ciencias de la Alimentación"),
        Pagina("https://www.fts.uner.edu.ar/", ambito="#primary-site-navigation-desktop",
               facultad="Facultad de Trabajo Social"),
    ), 34),
    # Each faculty's list is a template in the page's script.
    "UNSJ": Lista("Universidad Nacional de San Juan", "unsj.edu.ar",
                  (Pagina("https://www.unsj.edu.ar/posgrado/carreras"),), 39),
    "IUPFA": Lista("Instituto Universitario de la Policía Federal Argentina", "universidad-policial.edu.ar",
                   (Pagina("https://universidad-policial.edu.ar/posgradosIUPFA.html"),), 4),
    # ------------------------------------------------------------ privadas
    # Its postgraduates are listed only in the site's menu.
    "IUSE": Lista("Instituto Universitario de Seguridad", "iuse.edu.ar",
                  (Pagina("https://iuse.edu.ar/", ambito="nav"),), 3),
    "UEAN": Lista("Universidad Escuela Argentina de Negocios", "uean.edu.ar",
                  (Pagina("https://www.uean.edu.ar/posgrados/"),), 2),
    # One programme, two degrees: its page names the master's by its title.
    "UCINE": Lista("Universidad del Cine", "ucine.edu.ar",
                   (Pagina("https://www.ucine.edu.ar/posgrados/posgrado-en-cine-documental"),), 1),
    "USI": Lista('Universidad de San Isidro "Dr. Plácido Marín"', "usi.edu.ar",
                 (Pagina("https://usi.edu.ar/posgrados-y-diplomaturas/posgrados/"),), 1),
    "UCongreso": Lista("Universidad de Congreso", "ucongreso.edu.ar", tuple(
        Pagina(f"https://www.ucongreso.edu.ar/facultad/posgrados-{tipo}/")
        for tipo in ("virtuales", "presenciales")), 8),
    "UGD": Lista("Universidad Gastón Dachary", "ugd.edu.ar",
                 (Pagina("https://ugd.edu.ar/es/oferta-academica/posgrado"),), 3),
    "UAP": Lista("Universidad Adventista del Plata", "uap.edu.ar", (Pagina("https://uap.edu.ar/posgrado/"),), 5),
    # Every career of every level as cards; the filter works only in a browser.
    "Atlántida": Lista("Universidad Atlántida Argentina", "atlantida.edu.ar",
                       (Pagina("https://inscribite.atlantida.edu.ar/carreras/?programa=posgrado",
                               ambito="article.ua-card-career h3.ua-card-title"),), 3),
    "UCALP": Lista("Universidad Católica de La Plata", "ucalp.edu.ar",
                   (Pagina("https://www.ucalp.edu.ar/?taxonomy=tipo-de-carrera&term=posgrados"),), 9),
    "UCASAL": Lista("Universidad Católica de Salta", "ucasal.edu.ar",
                    (Pagina("https://www.ucasal.edu.ar/menu-oferta-educativa-por-nivel/posgrado"),), 34),
    "UGR": Lista("Universidad del Gran Rosario", "ugr.edu.ar",
                 (Pagina("https://ugr.edu.ar/grado_academico/posgrado/"),), 10),
    # The faculties' drop-down on the home page.
    "UDE": Lista("Universidad del Este", "ude.edu.ar",
                 (Pagina("https://www.ude.edu.ar/", ambito="ul.dropdown-facultades"),), 2),
    # The specialisations taught as residencies are listed by subject alone,
    # under a heading that says they are specialisations.
    "CEMIC": Lista("Instituto Universitario CEMIC", "cemic.edu.ar", (
        Pagina("https://cemic.edu.ar/instituto-universitario.php",
               ambito="#pilljustifiedHomePos h3, h1.color-green"),
        Pagina("https://cemic.edu.ar/instituto-universitario.php", ambito="#pilljustified5 strong",
               prefijo="Especialización en"),
    ), 15),
    # Its one postgraduate is only in the careers menu.
    "UCAMI": Lista("Universidad Católica de las Misiones", "ucami.edu.ar",
                   (Pagina("https://www.ucami.edu.ar/", ambito="#cbp-hrmenu"),), 1),
    "UCP": Lista("Universidad de la Cuenca del Plata", "ucp.edu.ar",
                 (Pagina("https://www.ucp.edu.ar/posgrado/", ambito="#resultado-cursos"),), 10),
    "UCH": Lista("Universidad Champagnat", "uch.edu.ar", (Pagina("https://www.uch.edu.ar/"),), 2),
    # The visible list; the page also carries hidden search entries.
    "CAECE": Lista("Universidad CAECE", "ucaece.edu.ar",
                   (Pagina("https://www.ucaece.edu.ar/posgrados", ambito=".carrera-listado-nombre-publico"),), 13),
    "UDA": Lista("Universidad del Aconcagua", "uda.edu.ar", (Pagina("https://www.uda.edu.ar/"),), 9),
    "IUCSB": Lista("Instituto Universitario de Ciencias de la Salud", "barcelo.edu.ar",
                   (Pagina("https://barcelo.edu.ar/carreras-de-posgrado"),), 2),
    # One page per kind; two programmes can share a heading.
    "UHIBA": Lista("Universidad Hospital Italiano de Buenos Aires", "hospitalitaliano.edu.ar", tuple(
        Pagina(f"https://posgrado.hospitalitaliano.edu.ar/{tipo}")
        for tipo in ("doctorados", "maestrias", "especializaciones")), 10),
    "UdeMM": Lista("Universidad de la Marina Mercante", "udemm.edu.ar",
                   (Pagina("https://www.udemm.edu.ar/posgrado/"),), 1),
    # The page's banner reads as a card of its own without the ambito.
    "IUCBC": Lista("Instituto Universitario de Ciencias Biomédicas de Córdoba", "iucbc.edu.ar",
                   (Pagina("https://www.iucbc.edu.ar/posgrado.html", ambito=".item-oferta-titulo h3"),), 14),
    # Built by script: each kind heads a run of links to its programmes.
    "Maimónides": Lista("Universidad Maimónides", "maimonides.edu",
                        (Pagina("https://www.maimonides.edu/carreras/"),), 15, navegador=True),
    "UCU": Lista("Universidad de Concepción del Uruguay", "ucu.edu.ar",
                 (Pagina("https://ucu.edu.ar/project_category/posgrado/"),), 4),
    "UNSTA": Lista("Universidad del Norte Santo Tomás de Aquino", "unsta.edu.ar",
                   (Pagina("https://www.unsta.edu.ar/posgrados-unsta/"),), 6),
    # The side menu keeps an old name of the doctorate.
    "IUNIR": Lista("Instituto Universitario Italiano de Rosario", "iunir.edu.ar", tuple(
        Pagina(f"https://www.iunir.edu.ar/postgrado/{ruta}", ambito="#contenido")
        for ruta in ("", "especializacion/medicina/", "especializacion/odontologia/")), 10),
    # Built in the browser.
    "ISALUD": Lista("Universidad ISALUD", "isalud.edu.ar",
                    (Pagina("https://www.isalud.edu.ar/carreras/posgrados"),), 8, navegador=True),
    # No page names them all in full: each programme's own landing page does.
    "ESEADE": Lista("Instituto Universitario ESEADE", "eseade.edu.ar", tuple(
        Pagina(f"https://go.eseade.edu.ar/{codigo}", ambito=".hs-elevate-heading-container:first-of-type")
        for codigo in ("mgac", "mmkt", "mbdba", "mder", "mcur", "mcomp", "mproy", "mecp", "mde", "dba")
    ) + (Pagina("https://go.eseade.edu.ar/mba", ambito=".hs-elevate-rich-text p:first-child strong"),), 9),
    # The "Posgrado" column of the careers menu; the postítulos sit beside it.
    "UCSE": Lista("Universidad Católica de Santiago del Estero", "ucse.edu.ar",
                  (Pagina("https://www.ucse.edu.ar/carreras/", ambito="#menu-item-2628"),), 6),
    # The central page is a menu; each faculty lists its own.
    "UMendoza": Lista("Universidad de Mendoza", "um.edu.ar", tuple(
        Pagina(f"https://um.edu.ar/{ruta}/", facultad=facultad) for ruta, facultad in (
            ("ciencias-juridicas-y-sociales/doctorados-fcjs", "Facultad de Ciencias Jurídicas y Sociales"),
            ("ciencias-juridicas-y-sociales/maestrias-fcjs", "Facultad de Ciencias Jurídicas y Sociales"),
            ("ciencias-juridicas-y-sociales/especializaciones-fcjs", "Facultad de Ciencias Jurídicas y Sociales"),
            ("arquitectura-urbanismo-y-diseno/doctorado-faud", "Facultad de Arquitectura, Urbanismo y Diseño"),
            ("arquitectura-urbanismo-y-diseno/especializaciones-faud",
             "Facultad de Arquitectura, Urbanismo y Diseño"),
            ("ingenieria/doctorados-fi", "Facultad de Ingeniería"),
            ("ciencias-medicas/especializaciones-fcm", "Facultad de Ciencias Médicas"),
        )), 15),
    "IUDPT": Lista("Instituto Universitario para el Desarrollo Productivo y Tecnológico Empresarial de la "
                   "Argentina", "iudpt.edu.ar", (Pagina("https://iudpt.edu.ar/extension-academica/posgrados/"),), 2),
    # The list is of pictures; each programme's page names it in its crumbs.
    "UCSF": Lista("Universidad Católica de Santa Fe", "ucsf.edu.ar", tuple(
        Pagina(f"https://www.ucsf.edu.ar/{ruta}/", ambito=".breadcrumbs") for ruta in (
            "la-ucsf/facultades/posgrados/especializacion-en-comunicacion-comunitaria",
            "la-ucsf/facultades/posgrados/especializacion-en-docencia-universitaria",
            "la-ucsf/facultades/posgrados/especializacion-en-pastoral-en-contextos-educativos",
            "la-ucsf/facultades/posgrados/especializacion-en-psicogerontologia",
            "posgrados/doctorado-en-ciencia-juridica", "posgrados/doctorado-en-educacion",
            "posgrados/especializacion-analisis-economico-y-gestion-cadenas-valor-agroalimentarias",
            "posgrados/especializacion-en-derecho-procesal",
            "posgrados/especializacion-en-gestion-de-la-transformacion-digital",
            "posgrados/especializacion-en-gestion-integral-del-habitat", "posgrados/maestria-en-educacion",
            "posgrados/maestria-en-proyecto-arquitectonico-y-urbano",
            "posgrados/maestria-relaciones-internacionales", "posgrados/maestria-sustentabilidad-ambiental",
        )), 11),
    # The list names the specialisations; each master's is named by its own page.
    "UMaza": Lista("Universidad Juan Agustín Maza", "umaza.edu.ar", (
        Pagina("https://www.umaza.edu.ar/posgrado"),
        *(Pagina(f"https://www.umaza.edu.ar/landings/{codigo}", ambito=".texto-cabecera")
          for codigo in ("maestria-educacion-superior", "winemba", "maestria-en-gestion-de-rrhh")),
    ), 6),
    "UNJu": Lista("Universidad Nacional de Jujuy", "unju.edu.ar",
                  (Pagina("https://unju.edu.ar/posgrado.html"),), 30),
}


def leer(lista: Lista) -> tuple[list[PosgradoListado], list[dict[str, str]]]:
    from rumbo_scraper.spiders.generico import Lector
    universidad = Universidad(lista.nombre_oficial, "", "Estatal", "https://" + lista.dominio,
                              lista.dominio, "", "", "", dominios_extra=lista.dominios_extra,
                              navegador=lista.navegador)
    lector = Lector(universidad)
    try:
        vistos: dict[str, PosgradoListado] = {}
        for pagina in lista.paginas:
            # The server's answer to a page its script fills in holds menus
            # enough to pass for a page, so the browser is asked outright.
            html = (lector._navegador.get(pagina.url) if lector._navegador is not None
                    else lector.get(pagina.url))
            for programa in leer_lista(html, pagina.url, lector.dominios,
                                       pagina.ambito, pagina.facultad, pagina.prefijo):
                vistos.setdefault(comparison_key(programa.nombre), programa)
        return list(vistos.values()), lector.errores
    finally:
        lector.close()


def aplicar(lista: Lista, programas: list[PosgradoListado], client: Any,
            reemplazar: bool = False) -> dict[str, int]:
    from rumbo_scraper.database.load_utdt import _upsert_chunks
    from rumbo_scraper.database.supabase import select_all

    fila = client.table("universidades").select("id").eq(
        "nombre_oficial", lista.nombre_oficial).execute().data
    if not fila:
        return {"universidad_no_encontrada": 1}
    uid = fila[0]["id"]
    facultades = {comparison_key(f["nombre_facultad"]): f["id"] for f in select_all(
        client.table("facultades").select("id,nombre_facultad").eq("universidad_id", uid))}
    filas = [{
        "universidad_id": uid,
        "facultad_id": facultades.get(comparison_key(p.facultad or "")),
        "nombre_programa": p.nombre, "tipo_posgrado": p.tipo,
        "url_oficial": p.url,
    } for p in programas]
    guardados = _upsert_chunks(client, "posgrados", filas, "universidad_id,nombre_programa")
    retirados = 0
    if reemplazar:
        vigentes = {f["id"] for f in guardados}
        viejos = [f["id"] for f in select_all(
            client.table("posgrados").select("id").eq("universidad_id", uid))
            if f["id"] not in vigentes]
        for inicio in range(0, len(viejos), 100):
            tanda = viejos[inicio:inicio + 100]
            client.table("materias").delete().in_("posgrado_id", tanda).execute()
            client.table("posgrados").delete().in_("id", tanda).execute()
        retirados = len(viejos)
    return {"posgrados": len(guardados), "retirados": retirados}


def main() -> None:
    parser = argparse.ArgumentParser(description="Leer los posgrados de la página que los lista")
    parser.add_argument("siglas", nargs="+", choices=sorted(LISTAS))
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase")
    parser.add_argument("--reemplazar", action="store_true",
                        help="Borrar los posgrados de la universidad que la lectura no trae")
    args = parser.parse_args()
    client = None
    for sigla in args.siglas:
        lista = LISTAS[sigla]
        programas, errores = leer(lista)
        salida = Path("data") / f"{sigla.lower()}_posgrados_lista.json"
        salida.write_text(json.dumps({
            "universidad": lista.nombre_oficial,
            "posgrados": [asdict(p) for p in programas], "errores": errores,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        propios = sum(p.url != p.fuente for p in programas)
        print(f"== {sigla}: {len(programas)} posgrados ({propios} con página propia)")
        for p in programas:
            print(f"   {p.tipo:16} {p.nombre}  <{p.url}>")
        for error in errores:
            print("   ERROR", error)
        if len(programas) < lista.minimo:
            print(f"   NO SE CARGA: menos de {lista.minimo}")
            continue
        if args.apply:
            if client is None:
                from rumbo_scraper.database.supabase import get_supabase_client
                client = get_supabase_client()
            print("   CARGADO", aplicar(lista, programas, client, args.reemplazar))


if __name__ == "__main__":
    main()
