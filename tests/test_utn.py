"""Tests for the Universidad Tecnológica Nacional adapter."""

import unittest

from rumbo_scraper.parsers.utn import (
    Career, SOURCE_URL, UNIVERSITY, build_dataset, career_url, catalogue_url,
    documents_url, duration_hours, duration_years, offers_url, parse_address,
    parse_plan_pdf, parse_plan_text, plan_document_url, programme_name,
    read_catalogue, year_column_position,
)
from rumbo_scraper.validators.utn import validate_dataset

GRADE = {
    "id_tipos_carreras": "1", "descripcion_tipos_carreras": "Grado",
    "id_subtipos_carreras": "1", "descripcion_subtipos_carreras": "Ingeniería",
    "id_carreras": "3", "nombre_carreras": "Ingeniería Civil",
    "duracion": "<p><strong>Años:</strong> 5½</p><p><strong>Horas reloj:</strong> 4110</p>",
    "alcance": "<ol><li>Diseñar, calcular y proyectar estructuras.</li></ol>",
    "requisitos": "<p>Título secundario</p>",
}
MASTER = {
    "id_tipos_carreras": "4", "descripcion_tipos_carreras": "Posgrado",
    "id_subtipos_carreras": "4", "descripcion_subtipos_carreras": "Maestría",
    "id_carreras": "126", "nombre_carreras": "Administración de Negocios",
}
COURSE = {
    "id_tipos_carreras": "4", "descripcion_tipos_carreras": "Posgrado",
    "id_subtipos_carreras": "6", "descripcion_subtipos_carreras": "Curso",
    "id_carreras": "169", "nombre_carreras": "Aceros Eléctricos",
}
HAEDO = {
    "id_regionales": "8", "nombre_regionales": "Facultad Regional Haedo",
    "decano": "Ing. Víctor Luis CABALLINI", "sexo_decano": "m",
    "direccion": "París 532. (1706) Haedo. Buenos Aires",
    "email": "comunica@frh.utn.edu.ar", "telefono": "(011) 4650-1085",
    "url_regionales": "http://www.frh.utn.edu.ar/", "res_coneau": "Nº 123/19",
}


def _catalogue(*records: dict) -> dict:
    pages = {catalogue_url(query): [] for query, _ in (
        ("id_tipos_carreras=1", ""), ("id_tipos_carreras=2", ""),
        ("id_tipos_carreras=3", ""), ("id_tipos_carreras=4", ""),
    )}
    for record in records:
        pages[catalogue_url(f"id_tipos_carreras={record['id_tipos_carreras']}")].append(record)
    return pages


class CatalogueTests(unittest.TestCase):
    def test_each_kind_of_the_search_keeps_its_level(self) -> None:
        careers = read_catalogue(_catalogue(GRADE, MASTER))
        self.assertEqual({c.name: c.level for c in careers},
                         {"Ingeniería Civil": "Grado",
                          "Maestría en Administración de Negocios": "Posgrado"})

    def test_the_subtype_decides_the_kind_of_a_postgraduate(self) -> None:
        careers = read_catalogue(_catalogue(MASTER))
        self.assertEqual(careers[0].kind, "Maestría")

    def test_the_kind_goes_back_in_front_of_the_topic(self) -> None:
        # The same topic is offered as a Maestría and as an Especialización,
        # so the topic alone is not the name of a programme.
        specialisation = dict(MASTER, id_carreras="127",
                              id_subtipos_carreras="5",
                              descripcion_subtipos_carreras="Especialización")
        names = {c.name for c in read_catalogue(_catalogue(MASTER, specialisation))}
        self.assertEqual(names, {"Maestría en Administración de Negocios",
                                 "Especialización en Administración de Negocios"})

    def test_a_doctorate_keeps_its_mention_after_its_kind(self) -> None:
        doctorate = dict(MASTER, id_carreras="200", id_subtipos_carreras="3",
                         descripcion_subtipos_carreras="Doctorado en Ingeniería",
                         nombre_carreras="Electrónica")
        careers = read_catalogue(_catalogue(doctorate))
        self.assertEqual(careers[0].name, "Doctorado en Ingeniería — Electrónica")
        self.assertEqual(careers[0].kind, "Doctorado")

    def test_a_doctorate_named_after_its_own_kind_is_not_repeated(self) -> None:
        doctorate = dict(MASTER, id_carreras="201", id_subtipos_carreras="7",
                         descripcion_subtipos_carreras="Doctorado en Informática",
                         nombre_carreras="Doctorado en Informática")
        self.assertEqual(read_catalogue(_catalogue(doctorate))[0].name,
                         "Doctorado en Informática")

    def test_a_postgraduate_course_has_no_kind_in_the_contract(self) -> None:
        # The contract's enum holds degrees; a course is not one of them and
        # inventing a kind for it would be worse than leaving it null.
        careers = read_catalogue(_catalogue(COURSE))
        self.assertIsNone(careers[0].kind)

    def test_a_career_returned_by_two_filters_appears_once(self) -> None:
        pages = _catalogue(GRADE)
        pages[catalogue_url("id_tipos_carreras=2")].append(GRADE)
        self.assertEqual(len(read_catalogue(pages)), 1)

    def test_every_career_carries_a_public_address(self) -> None:
        url = career_url(GRADE)
        self.assertTrue(url.startswith(SOURCE_URL))
        self.assertIn("idSeleccion=3", url)


class DurationTests(unittest.TestCase):
    def test_reads_the_half_year_written_as_a_fraction(self) -> None:
        self.assertEqual(duration_years(GRADE["duracion"]), 5.5)

    def test_reads_the_half_year_written_in_words(self) -> None:
        self.assertEqual(duration_years("5 años y medio. 4136 horas."), 5.5)

    def test_reads_a_whole_number_of_years(self) -> None:
        self.assertEqual(duration_years("5 (CINCO) años."), 5.0)

    def test_an_unpublished_duration_stays_null(self) -> None:
        self.assertIsNone(duration_years(None))
        self.assertIsNone(duration_years(""))

    def test_reads_the_total_hours(self) -> None:
        self.assertEqual(duration_hours(GRADE["duracion"]), 4110)
        self.assertEqual(duration_hours("5 años y medio. 4136 horas."), 4136)


class AddressTests(unittest.TestCase):
    def test_splits_street_number_locality_and_province(self) -> None:
        self.assertEqual(parse_address("París 532. (1706) Haedo. Buenos Aires"), {
            "calle": "París", "numero": "532", "localidad": "Haedo",
            "provincia": "Buenos Aires", "codigo_postal": "1706",
        })

    def test_the_city_of_buenos_aires_is_its_own_province(self) -> None:
        address = parse_address("Medrano 951. (C1179AAQ) Ciudad Autónoma de Buenos Aires")
        self.assertEqual(address["localidad"], "Ciudad Autónoma de Buenos Aires")
        self.assertEqual(address["provincia"], "CABA")

    def test_an_address_without_a_postal_code_still_reads(self) -> None:
        address = parse_address("Laprida 651. Venado Tuerto. Santa Fe")
        self.assertEqual(address["localidad"], "Venado Tuerto")
        self.assertEqual(address["provincia"], "Santa Fe")
        self.assertIsNone(address["codigo_postal"])

    def test_an_address_that_cannot_be_split_leaves_the_locality_null(self) -> None:
        # Córdoba writes a corner instead of a street number, so which of the
        # two tail words is the locality is not published; guessing would put
        # "López y Cruz Roja Argentina" on the map as a town.
        address = parse_address("Maestro M. López y Cruz Roja Argentina.  Córdoba")
        self.assertIsNone(address["localidad"])
        self.assertIsNone(address["provincia"])

    def test_an_empty_address_yields_nulls_and_not_a_crash(self) -> None:
        self.assertEqual(set(parse_address(None).values()), {None})


class DocumentTests(unittest.TestCase):
    def test_finds_the_plan_among_the_documents(self) -> None:
        url = plan_document_url([
            {"descripcion_tipos_doc_carreras": "Ordenanza CS", "numero": "1926",
             "archivo": None, "tipo_archivo": None},
            {"descripcion_tipos_doc_carreras": "Plan de estudio",
             "archivo": "Plan-de-estudio-Civil", "tipo_archivo": "pdf"},
        ])
        self.assertTrue(url.endswith("/planes_estudio/Plan-de-estudio-Civil.pdf"))

    def test_a_career_without_a_plan_document_yields_nothing(self) -> None:
        self.assertIsNone(plan_document_url(
            [{"descripcion_tipos_doc_carreras": "Ordenanza CS", "archivo": None}]
        ))


class YearColumnTests(unittest.TestCase):
    def test_reads_a_header_that_puts_the_year_first(self) -> None:
        self.assertEqual(year_column_position(["Año Código Asignatura Hs"]), "leading")

    def test_reads_a_header_that_puts_the_year_after_the_name(self) -> None:
        self.assertEqual(
            year_column_position(["Cód. Asignaturas Año Hs./Cuat. Correlativas"]),
            "trailing",
        )

    def test_a_plan_with_block_headings_declares_no_year_column(self) -> None:
        self.assertIsNone(year_column_position(["N° ASIGNATURAS Carga horaria"]))


# The four layouts the ninety-one plan documents are written in, as the text
# extractor flattens them.
HEADING_PLAN = """7.- PLAN DE ESTUDIO
N° ASIGNATURAS Carga horaria semanal (dictado anual) h catedra. Carga horaria total anual h reloj.
PRIMER NIVEL
1 Análisis Matemático I 5 120
2 Algebra y Geometría Analítica 5 120
3 Ingeniería y Sociedad 2 48
30 720
SEGUNDO NIVEL
9 Análisis Matemático II 5 120
10 Estabilidad 5 120
TOTAL SEGUNDO NIVEL 27 648
"""

ROMAN_PLAN = """PLAN DE ESTUDIOS
Nive
l
N° Cátedras Horas Cátedra Semanal Horas Cátedra Horas Reloj
I
1 Informática I 5 160 120
2 Álgebra y Geometría Analítica 5 160 120
TOTAL HORAS NIVEL I 31 992 744
II
8 Química General 5 160 120
9
Taller de Redes y
comunicaciones
2 64 48
TOTAL HORAS NIVEL II 30 960 720
"""

LEADING_COLUMN_PLAN = """Plan de Estudio de la Tecnicatura Superior en Telecomunicaciones - Ordenanza N° 1300.
Año Código Asignatura Hs/Sem reloj Hs/Total reloj
1
1.1.1 ANÁLISIS MATEMÁTICO 5 80
1.1.2 ÁLGEBRA LINEAL 2 32
2
2.1.1 SISTEMAS DE COMUNICACIONES 4 64
2.1.2 REDES DE DATOS 4 64
"""

TRAILING_COLUMN_PLAN = """Licenciatura en Higiene y Seguridad en el Trabajo
Cód. Asignaturas Año Hs./Cuat. Correlativas
1 Análisis Matemático 1 64
2 Química 1 48
10 Toxicología Laboral 2 48
11 Ergonomía 2 48
12 Legislación Laboral 2 64
13 Seguridad Industrial Avanzada 2 192
14 Diseño y Práctica de Capacitación 2 64
"""


class PlanTests(unittest.TestCase):
    def test_a_document_that_is_not_a_pdf_says_so(self) -> None:
        result = parse_plan_pdf(b"not a pdf", "Ingeniería Civil")
        self.assertEqual(result["materias"], [])
        self.assertIn("no pudo leerse", result["motivo"])

    def test_a_scanned_plan_is_reported_instead_of_read(self) -> None:
        result = parse_plan_text("PLAN DE ESTUDIO", "Ingeniería Civil")
        self.assertEqual(result["materias"], [])
        self.assertIn("imagen escaneada", result["motivo"])

    def test_a_block_heading_gives_its_year_to_the_subjects_below(self) -> None:
        rows = parse_plan_text(HEADING_PLAN, "Ingeniería Civil")["materias"]
        self.assertEqual([(r["nombre_materia"], r["anio_cursada"]) for r in rows], [
            ("Análisis Matemático I", 1), ("Algebra y Geometría Analítica", 1),
            ("Ingeniería y Sociedad", 1), ("Análisis Matemático II", 2),
            ("Estabilidad", 2),
        ])

    def test_the_weekly_load_is_the_first_column_of_the_row(self) -> None:
        rows = parse_plan_text(HEADING_PLAN, "Ingeniería Civil")["materias"]
        self.assertEqual(rows[0]["carga_horaria_semanal"], 5)
        self.assertEqual(rows[2]["carga_horaria_semanal"], 2)

    def test_a_roman_numeral_in_the_level_column_is_a_year(self) -> None:
        rows = parse_plan_text(ROMAN_PLAN, "Ingeniería en Telecomunicaciones")["materias"]
        self.assertEqual([(r["nombre_materia"], r["anio_cursada"]) for r in rows], [
            ("Informática I", 1), ("Álgebra y Geometría Analítica", 1),
            ("Química General", 2), ("Taller de Redes y comunicaciones", 2),
        ])

    def test_a_year_column_declared_before_the_name_is_read(self) -> None:
        rows = parse_plan_text(LEADING_COLUMN_PLAN, "Telecomunicaciones")["materias"]
        self.assertEqual([(r["nombre_materia"], r["anio_cursada"]) for r in rows], [
            ("ANÁLISIS MATEMÁTICO", 1), ("ÁLGEBRA LINEAL", 1),
            ("SISTEMAS DE COMUNICACIONES", 2), ("REDES DE DATOS", 2),
        ])

    def test_a_year_column_declared_after_the_name_is_read(self) -> None:
        rows = parse_plan_text(TRAILING_COLUMN_PLAN, "Higiene y Seguridad")["materias"]
        self.assertEqual([(r["nombre_materia"], r["anio_cursada"]) for r in rows], [
            ("Análisis Matemático", 1), ("Química", 1),
            ("Toxicología Laboral", 2), ("Ergonomía", 2),
            ("Legislación Laboral", 2), ("Seguridad Industrial Avanzada", 2),
            ("Diseño y Práctica de Capacitación", 2),
        ])

    def test_the_running_head_of_the_document_is_not_a_subject(self) -> None:
        text = ('"2025- Año de la Reconstrucción" Ministerio de Capital Humano\n'
                + HEADING_PLAN)
        names = {row["nombre_materia"]
                 for row in parse_plan_text(text, "Ingeniería Civil")["materias"]}
        self.assertNotIn("Ministerio de Capital Humano", names)

    def test_a_line_outside_every_year_block_is_dropped_and_counted(self) -> None:
        # The signature of the clerk who certified the plan sits on the cover,
        # before the first year; keeping it would invent a subject.
        text = "PABLO A. HUEL JEFE DE DEPARTAMENTO 1 2\n" + HEADING_PLAN
        result = parse_plan_text(text, "Ingeniería Civil")
        self.assertEqual(result["descartadas"], 1)
        self.assertEqual(len(result["materias"]), 5)

    def test_a_total_line_is_not_a_subject(self) -> None:
        names = {row["nombre_materia"]
                 for row in parse_plan_text(HEADING_PLAN, "X")["materias"]}
        self.assertNotIn("TOTAL SEGUNDO NIVEL", names)


class DatasetTests(unittest.TestCase):
    def _dataset(self, *records: dict) -> dict:
        careers = read_catalogue(_catalogue(*(records or (GRADE,))))
        return build_dataset(
            careers, {"8": HAEDO},
            {offers_url(c.id): [dict(HAEDO, **{"res_coneau": "Nº 123/19"})]
             for c in careers},
            {documents_url(c.id): [] for c in careers},
        )

    def test_a_regional_faculty_becomes_a_campus_a_faculty_and_a_dean(self) -> None:
        data = self._dataset()["datos"]
        self.assertEqual(data["sedes"][0]["nombre_sede"], "Facultad Regional Haedo")
        self.assertEqual(data["facultades"][0]["tipo_unidad"], "Facultad")
        self.assertEqual(data["sedes"][0]["tipo_sede"], "Campus")
        self.assertEqual(data["autoridades"][0]["cargo"], "Decano")
        self.assertEqual(data["autoridades"][0]["nombre_autoridad"],
                         "Ing. Víctor Luis CABALLINI")

    def test_a_woman_dean_is_named_as_the_source_publishes_her(self) -> None:
        dataset = build_dataset(
            read_catalogue(_catalogue(GRADE)),
            {"8": dict(HAEDO, sexo_decano="f", decano="Ing. Ana PÉREZ")},
            {}, {},
        )
        self.assertEqual(dataset["datos"]["autoridades"][0]["cargo"], "Decana")

    def test_the_contact_channels_come_from_the_catalogue(self) -> None:
        channels = {row["canal"]: row["usuario_o_direccion"]
                    for row in self._dataset()["datos"]["redes_contacto"]}
        self.assertEqual(channels["Email"], "comunica@frh.utn.edu.ar")
        self.assertEqual(channels["Teléfono"], "(011) 4650-1085")

    def test_a_career_becomes_one_row_and_one_offer_per_regional(self) -> None:
        data = self._dataset()["datos"]
        self.assertEqual(data["carreras"][0]["nombre_carrera"], "Ingeniería Civil")
        self.assertEqual(data["carreras"][0]["duracion_anios"], 5.5)
        self.assertEqual(data["ofertas"][0]["sede"], "Facultad Regional Haedo")
        self.assertEqual(data["ofertas"][0]["coneau_resolucion"], "Nº 123/19")

    def test_the_scope_and_the_requirements_come_from_the_catalogue(self) -> None:
        data = self._dataset()["datos"]
        self.assertEqual(data["carreras"][0]["descripcion_breve"],
                         "Diseñar, calcular y proyectar estructuras.")
        self.assertEqual(data["ofertas"][0]["regimen_ingreso"], "Título secundario")

    def test_a_career_without_a_published_scope_keeps_it_null(self) -> None:
        bare = dict(GRADE, alcance=None, requisitos="")
        dataset = build_dataset(read_catalogue(_catalogue(bare)), {"8": HAEDO},
                                {offers_url("3"): [HAEDO]}, {})
        self.assertIsNone(dataset["datos"]["carreras"][0]["descripcion_breve"])
        self.assertIsNone(dataset["datos"]["ofertas"][0]["regimen_ingreso"])

    def test_a_postgraduate_keeps_only_what_the_catalogue_publishes(self) -> None:
        data = self._dataset(MASTER)["datos"]
        row = data["posgrados"][0]
        self.assertEqual(row["nombre_programa"], "Maestría en Administración de Negocios")
        self.assertEqual(row["tipo_posgrado"], "Maestría")
        self.assertIsNone(row["duracion_meses"])
        self.assertIsNone(row["titulo_otorgado"])
        self.assertEqual(data["carreras"], [])

    def test_a_course_is_reported_instead_of_given_a_kind(self) -> None:
        dataset = self._dataset(COURSE)
        self.assertEqual(dataset["control_calidad"]["posgrados_sin_tipo_en_contrato"],
                         ["Aceros Eléctricos"])

    def test_the_dataset_respects_the_contract(self) -> None:
        dataset = self._dataset(GRADE, MASTER, COURSE)
        self.assertEqual(dataset["universidad"], UNIVERSITY)
        validate_dataset(dataset)

    def test_an_offer_in_a_campus_that_was_never_listed_is_rejected(self) -> None:
        dataset = self._dataset()
        dataset["datos"]["ofertas"][0]["sede"] = "Facultad Regional Inventada"
        with self.assertRaises(ValueError):
            validate_dataset(dataset)


if __name__ == "__main__":
    unittest.main()
