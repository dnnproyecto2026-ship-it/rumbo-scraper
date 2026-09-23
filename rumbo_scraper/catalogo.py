"""The universities to read, and the little each one needs said about it.

Fifteen universities were read with an adapter apiece because each site
publishes its catalogue in its own shape. That does not scale to a country:
Argentina has more than a hundred universities and writing four hundred lines
for each is a year of work.

What does scale is the observation behind this module: an Argentine university
does not get to invent the name of a degree. The Ministry recognises a closed
set of them -- Licenciatura, Ingeniería, Profesorado, Tecnicatura, Abogacía,
Medicina, Maestría, Especialización, Doctorado -- and every university prints
that name as the heading of the page about the programme. So a programme page
can be recognised by what it says rather than by where it sits, and a
university needs only its name, its address and where it is to be read.

The per-site adapters stay for the fifteen that have one: they read more,
because someone looked at each site. This reads the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Universidad:
    """A university to read, and the few things only a person can supply."""

    nombre_oficial: str
    nombre_corto: str
    tipo_gestion: str  # Privada | Estatal, as the schema spells it
    sitio_web: str
    dominio: str
    region: str
    provincia: str
    localidad: str
    # Where the site lists its own addresses. Left empty, the reader asks for
    # /sitemap.xml and, failing that, walks out from the home page.
    sitemaps: tuple[str, ...] = ()
    # Extra pages to walk out from, for a site whose catalogue the sitemap
    # does not reach.
    semillas: tuple[str, ...] = ()
    # Hosts besides the main one that carry part of the catalogue.
    dominios_extra: tuple[str, ...] = field(default_factory=tuple)
    # A site that builds its pages in the browser needs one.
    navegador: bool = False


# Ordered as the work is done: the city first, then its conurbano, then the
# interior capitals. Within each, by how many students a university teaches,
# so the catalogue covers the most people soonest.
UNIVERSIDADES: tuple[Universidad, ...] = (
    # ---------------------------------------------------------------- CABA
    Universidad(
        "Universidad Nacional de las Artes", "UNA", "Estatal",
        "https://una.edu.ar", "una.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
    ),
    Universidad(
        "Universidad de Flores", "UFLO", "Privada",
        "https://www.uflouniversidad.edu.ar", "uflouniversidad.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
    ),
    # Maimónides answers every address with a 500 and an empty body, from
    # every user agent tried. There is nothing to read until its site works.
    Universidad(
        "Universidad Maimónides", "Maimónides", "Privada",
        "https://maimonides.edu.ar", "maimonides.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
    ),
    Universidad(
        "Universidad Favaloro", "Favaloro", "Privada",
        "https://www.favaloro.edu.ar", "favaloro.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
    ),
    Universidad(
        "Universidad Argentina John F. Kennedy", "UK", "Privada",
        "https://kennedy.edu.ar", "kennedy.edu.ar", "CABA",
        "Ciudad Autónoma de Buenos Aires", "Ciudad Autónoma de Buenos Aires",
    ),
    # ----------------------------------------------------------------- GBA
    Universidad(
        "Universidad Nacional de La Matanza", "UNLaM", "Estatal",
        "https://www.unlam.edu.ar", "unlam.edu.ar", "GBA",
        "Buenos Aires", "San Justo",
    ),
    # UNSAM answers every request with a bot challenge from its content
    # network ("Just a moment..."), including the one for its sitemap. That
    # is a control the university chose to put in front of its own pages, and
    # this project does not work around one. Its catalogue stays unread until
    # the university opens it or tells us how to ask.
    Universidad(
        "Universidad Nacional de San Martín", "UNSAM", "Estatal",
        "https://www.unsam.edu.ar", "unsam.edu.ar", "GBA",
        "Buenos Aires", "San Martín",
    ),
    Universidad(
        "Universidad Nacional de Quilmes", "UNQ", "Estatal",
        "https://www.unq.edu.ar", "unq.edu.ar", "GBA",
        "Buenos Aires", "Bernal",
    ),
    Universidad(
        "Universidad Nacional de Tres de Febrero", "UNTREF", "Estatal",
        "https://www.untref.edu.ar", "untref.edu.ar", "GBA",
        "Buenos Aires", "Caseros",
    ),
    Universidad(
        "Universidad Nacional de Lanús", "UNLa", "Estatal",
        "https://www.unla.edu.ar", "unla.edu.ar", "GBA",
        "Buenos Aires", "Remedios de Escalada",
    ),
    Universidad(
        "Universidad Nacional de General Sarmiento", "UNGS", "Estatal",
        "https://www.ungs.edu.ar", "ungs.edu.ar", "GBA",
        "Buenos Aires", "Los Polvorines",
    ),
    Universidad(
        "Universidad Nacional Arturo Jauretche", "UNAJ", "Estatal",
        "https://www.unaj.edu.ar", "unaj.edu.ar", "GBA",
        "Buenos Aires", "Florencio Varela",
    ),
    # Avellaneda serves a page of three hundred bytes and builds the rest in
    # the browser; José C. Paz serves its catalogue the same way.
    Universidad(
        "Universidad Nacional de Avellaneda", "UNDAV", "Estatal",
        "https://undav.edu.ar", "undav.edu.ar", "GBA",
        "Buenos Aires", "Avellaneda", navegador=True,
    ),
    Universidad(
        "Universidad Nacional de Moreno", "UNM", "Estatal",
        "https://www.unm.edu.ar", "unm.edu.ar", "GBA",
        "Buenos Aires", "Moreno",
    ),
    Universidad(
        "Universidad Nacional de José C. Paz", "UNPAZ", "Estatal",
        "https://www.unpaz.edu.ar", "unpaz.edu.ar", "GBA",
        "Buenos Aires", "José C. Paz", navegador=True,
    ),
    Universidad(
        "Universidad Nacional de Hurlingham", "UNAHUR", "Estatal",
        "https://unahur.edu.ar", "unahur.edu.ar", "GBA",
        "Buenos Aires", "Hurlingham",
    ),
    Universidad(
        "Universidad Nacional del Oeste", "UNO", "Estatal",
        "https://www.uno.edu.ar", "uno.edu.ar", "GBA",
        "Buenos Aires", "Merlo",
    ),
    # Morón serves a page of one and a half kilobytes and fills it in the
    # browser, so it is read with one.
    Universidad(
        "Universidad de Morón", "UM", "Privada",
        "https://www.unimoron.edu.ar", "unimoron.edu.ar", "GBA",
        "Buenos Aires", "Morón", navegador=True,
    ),
    # ------------------------------------------------------------- La Plata
    Universidad(
        "Universidad Nacional de La Plata", "UNLP", "Estatal",
        "https://unlp.edu.ar", "unlp.edu.ar", "La Plata",
        "Buenos Aires", "La Plata",
    ),
    # -------------------------------------------------------------- Córdoba
    Universidad(
        "Universidad Nacional de Córdoba", "UNC", "Estatal",
        "https://www.unc.edu.ar", "unc.edu.ar", "Córdoba",
        "Córdoba", "Córdoba",
    ),
    # Siglo 21 publishes the index of its careers as a list its page builds
    # in the reader, so it is read with a browser.
    Universidad(
        "Universidad Siglo 21", "Siglo 21", "Privada",
        "https://21.edu.ar", "21.edu.ar", "Córdoba",
        "Córdoba", "Córdoba", navegador=True,
    ),
    Universidad(
        "Universidad Católica de Córdoba", "UCC", "Privada",
        "https://www.ucc.edu.ar", "ucc.edu.ar", "Córdoba",
        "Córdoba", "Córdoba",
    ),
    Universidad(
        "Universidad Blas Pascal", "UBP", "Privada",
        "https://www.ubp.edu.ar", "ubp.edu.ar", "Córdoba",
        "Córdoba", "Córdoba",
    ),
    # -------------------------------------------------------------- Rosario
    Universidad(
        "Universidad Nacional de Rosario", "UNR", "Estatal",
        "https://unr.edu.ar", "unr.edu.ar", "Rosario",
        "Santa Fe", "Rosario",
    ),
    # UCEL sits behind the same bot challenge as UNSAM, and FASTA refuses
    # every request outright with a 403. Both are controls the universities
    # put in front of their own pages, and this project does not work around
    # one. They stay unread.
    Universidad(
        "Universidad del Centro Educativo Latinoamericano", "UCEL", "Privada",
        "https://www.ucel.edu.ar", "ucel.edu.ar", "Rosario",
        "Santa Fe", "Rosario",
    ),
    # -------------------------------------------------------- Mar del Plata
    Universidad(
        "Universidad Nacional de Mar del Plata", "UNMdP", "Estatal",
        "https://www.mdp.edu.ar", "mdp.edu.ar", "Mar del Plata",
        "Buenos Aires", "Mar del Plata",
    ),
    Universidad(
        "Universidad FASTA", "FASTA", "Privada",
        "https://www.ufasta.edu.ar", "ufasta.edu.ar", "Mar del Plata",
        "Buenos Aires", "Mar del Plata",
    ),
)

POR_CLAVE = {universidad.nombre_corto.lower(): universidad
             for universidad in UNIVERSIDADES}


def buscar(clave: str) -> Universidad:
    """The university a command line names, by its short name."""
    try:
        return POR_CLAVE[clave.lower()]
    except KeyError:
        raise SystemExit(
            f"No conozco '{clave}'. Conozco: "
            + ", ".join(sorted(POR_CLAVE))
        ) from None
