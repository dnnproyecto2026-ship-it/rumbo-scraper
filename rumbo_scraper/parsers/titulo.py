"""The degree a career gives, as its own page says it.

The pages say it as a labelled field ("Título: Ingeniero/a Civil", "Título
que otorga: Licenciado en Matemáticas", "Título a obtener: ...") or in a
sentence ("Se expide el título de Profesor/a de Lengua Inglesa"). What
follows is taken up to the end of its line or sentence, and only if it
reads as a degree: it opens with one ("Licenciado", "Ingeniera",
"Profesor/a", "Técnico", "Contador", ...) and is short.

A page that gives two different degrees is left alone unless one of them
is plainly this career's (the page of a licenciatura that names the
intermediate technician's title as well): the one whose words are the
career's. A page's menu, header and footer do not count.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key

_GRADOS = (r"licenciad[oa]s?|ingenier[oa]s?|profesor(?:a|es)?|t[ée]cnic[oa]s?|contador(?:a)?|abogad[oa]|"
           r"arquitect[oa]|m[ée]dic[oa]|traductor(?:a)?|int[ée]rprete|analista|bioqu[íi]mic[oa]|"
           r"farmac[ée]utic[oa]|odont[óo]log[oa]|kinesi[óo]log[oa]|enfermer[oa]|veterinari[oa]|"
           r"m[ée]dic[oa] veterinari[oa]|psic[óo]log[oa]|nutricionista|dise[ñn]ador(?:a)?|martillero|"
           r"corredor|escriban[oa]|ge[óo]log[oa]|obst[ée]tric[oa]|bibliotecari[oa]|bibliotec[óo]log[oa]|"
           r"gu[íi]a|secretari[oa]|actuari[oa]|agrimensor(?:a)?|perito|asistente|operador(?:a)?|"
           r"m[úu]sic[oa]|actor|actriz|director(?:a)?|realizador(?:a)?|fonoaudi[óo]log[oa]|"
           r"agr[óo]nom[oa]|ingeniero agr[óo]nomo|bachiller|despachante|archiv[íi]st[ao]|"
           r"comunicador(?:a)?|periodista|trabajador(?:a)? social|terapista|terapeuta|instrumentador(?:a)?|"
           r"escen[óo]graf[oa]|cine[ae]sta|compositor(?:a)?|dramaturg[oa]|mec[áa]nic[oa]|piloto|oficial")
_ES_UN_GRADO = re.compile(r"(?i)^(?:" + _GRADOS + r")\b")
_ROTULO = re.compile(
    r"(?i)\bt[íi]tulos?(?:\s+(?:que\s+(?:se\s+)?otorga|a\s+obtener|otorgado|que\s+se\s+obtiene|de\s+grado|final|"
    r"profesional|universitario))?\s*:\s*(.+)")
_FRASE = re.compile(r"(?i)\b(?:expide|otorga|obtiene|recibe|obtendr[áa]s?|obten[ée]s)\s+(?:el\s+)?t[íi]tulo\s+de\s+(.+)")
_CORTE = re.compile(r"\s*(?:[.;]\s|\.$|\(|\s[-–]\s|\s\|\s|,\s*(?:con|que|el|la|y)\b|\s+con\s+validez|\s+duraci[óo]n\b|"
                    r"\s+reconocimiento\b|\s+res(?:oluci[óo]n)?\.?\s)")


def _limpio(texto: str) -> str | None:
    # "Profesor/a en Cs. Biológicas": the abbreviation's point ends nothing.
    texto = re.sub(r"\bCs\.\s*", "Ciencias ", clean_text(texto))
    texto = _CORTE.split(texto, maxsplit=1)[0].strip(" .:;,-–\"'“”")
    # The next section's number run into it ("... Viajes y Turismo 1.3").
    texto = re.sub(r"\s+\d+(?:\.\d+)+$", "", texto)
    if not _ES_UN_GRADO.match(texto) or len(texto) > 90 or len(texto.split()) > 12:
        return None
    # "Licenciado", "Profesor/a", "Técnico" alone say the kind of degree, not
    # which: cut short.
    if re.fullmatch(r"(?i)(licenciad|profesor|ingenier|t[ée]cnic|traductor|analista|bachiller)\S*", texto):
        return None
    if texto.isupper():
        from rumbo_scraper.parsers.guias_nacionales import con_tildes

        texto = con_tildes(texto)
    return texto[0].upper() + texto[1:]


def titulos_en(texto: str) -> list[str]:
    halladas: list[str] = []
    for linea in texto.split("\n"):
        linea = clean_text(linea)
        for patron in (_ROTULO, _FRASE):
            for match in patron.finditer(linea):
                titulo = _limpio(match.group(1))
                if titulo and comparison_key(titulo) not in {comparison_key(h) for h in halladas}:
                    halladas.append(titulo)
    return halladas


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z]{4,}", comparison_key(texto))}


def titulo_de_la_pagina(html: str, carrera: str) -> str | None:
    """The one degree the page's content gives, or the one of several whose
    words are plainly the career's; None otherwise."""
    soup = BeautifulSoup(html or "", "html.parser")
    # (A sidebar stays: FAyD's gives "Título: Arquitecto/a" there.)
    for parte in soup.find_all(["nav", "header", "footer", "script", "style"]):
        parte.decompose()
    cuerpo = soup.find("main") or soup.body
    if cuerpo is None:
        return None
    # A label and its value are often two elements ("Título:" / "Ingeniero Civil").
    texto = re.sub(r"(?i)(t[íi]tulos?[^:\n]{0,30}:)\s*\n+\s*", r"\1 ", cuerpo.get_text("\n"))
    # Or a label alone on its line, with no colon (UPC's "Nombre del título
    # a otorgar" over "Técnico/a Universitario/a en ...").
    # Or "TÍTULO" alone (UADER), "Título/s que otorga" (UNER).
    texto = re.sub(r"(?im)^\s*(?:nombre del )?t[íi]tulo(?:/s|s)?(?: (?:a otorgar|que (?:se )?otorga|a obtener|de grado|"
                   r"de pregrado))?\s*\n+\s*", "Título: ", texto)
    halladas = titulos_en(texto)
    if len(halladas) == 1:
        return halladas[0]
    propias = _palabras(re.sub(r"(?i)^(licenciatura|profesorado|tecnicatura|ingenier[íi]a)\s+(en|de|universitaria)?", "", carrera))
    puntajes = sorted(((len(_palabras(t) & propias), t) for t in halladas), reverse=True)
    if len(puntajes) > 1 and puntajes[0][0] > puntajes[1][0] and puntajes[0][0] >= max(1, len(propias) // 2):
        return puntajes[0][1]
    return None
