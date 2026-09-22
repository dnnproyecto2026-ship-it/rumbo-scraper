"""Tests for the UdeSA postgraduate adapter.

The inputs mirror the shape the official Next.js pages publish; they are not
generated from the parser's own constants, so a wrong reading fails here.
"""

import unittest

from rumbo_scraper.parsers.udesa import (
    PostgraduateRef, UNIVERSITY, build_dataset, discover_graduate_plan_url,
    discover_postgraduates, duration_months, parse_postgraduate_detail,
    postgraduate_campus, postgraduate_kind, postgraduate_modality,
    split_academic_unit,
)
from rumbo_scraper.validators.udesa import validate_postgraduates


def _index(items: list[dict]) -> dict:
    return {"sections": [
        {"__typename": "ParagraphModule06", "cardIcon": []},
        {"__typename": "ParagraphModule29", "listDegreesModule29": {
            "__typename": "EntityList", "items": items}},
    ]}


def _graduate(name: str, url: str, department: str = "Departamento de Economía") -> dict:
    return {"__typename": "Graduate", "name": name, "url": url,
            "associatedDepartment": [{"__typename": "Department", "name": department}]}


def _page(title: str, attendance: list[dict] | None = None, cards: list[dict] | None = None) -> dict:
    return {
        "pageType": "Graduate", "title": title,
        "header": {"description": "<p>Formación en teoría y práctica.</p>",
                   "src": "https://images.udesa.edu.ar/posgrado.jpg"},
        "attendance": attendance or [],
        "navigationCards": cards or [],
    }


class DiscoveryTests(unittest.TestCase):
    def test_reads_the_official_index_whatever_the_section_order(self) -> None:
        page = _index([_graduate("Maestría en Economía", "/departamento-de-economia/maestria-en-economia")])
        page["sections"].reverse()
        refs = discover_postgraduates(page)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].name, "Maestría en Economía")
        self.assertEqual(refs[0].url, "https://udesa.edu.ar/departamento-de-economia/maestria-en-economia")
        self.assertEqual(refs[0].department, "Departamento de Economía")

    def test_ignores_entities_that_are_not_postgraduate_programmes(self) -> None:
        page = _index([
            _graduate("Maestría en Economía", "/departamento-de-economia/maestria-en-economia"),
            {"__typename": "Undergraduate", "name": "Abogacía", "url": "/abogacia"},
            {"__typename": "Graduate", "name": "Sin URL", "url": ""},
        ])
        self.assertEqual([ref.name for ref in discover_postgraduates(page)], ["Maestría en Economía"])

    def test_deduplicates_and_sorts(self) -> None:
        url = "/departamento-de-economia/maestria-en-economia"
        refs = discover_postgraduates(_index([
            _graduate("Maestría en Economía", url),
            _graduate("Maestría en Economía", url),
            _graduate("Doctorado en Economía", "/departamento-de-economia/doctorado-en-economia"),
        ]))
        self.assertEqual([ref.name for ref in refs], ["Doctorado en Economía", "Maestría en Economía"])

    def test_an_empty_index_yields_nothing_instead_of_raising(self) -> None:
        self.assertEqual(discover_postgraduates({}), ())


class ClassificationTests(unittest.TestCase):
    def test_uses_the_leading_word_the_university_publishes(self) -> None:
        self.assertEqual(postgraduate_kind("Maestría en Economía"), "Maestría")
        self.assertEqual(postgraduate_kind("Doctorado en Historia"), "Doctorado")
        self.assertEqual(postgraduate_kind("Especialización en Neurociencia"), "Especialización")
        self.assertEqual(postgraduate_kind("Diplomatura en Gestión Urbana"), "Diplomatura")

    def test_leaves_null_instead_of_forcing_an_unlisted_name(self) -> None:
        for name in ("MBA", "Executive MBA", "Master in Management", "Profesorado Universitario"):
            self.assertIsNone(postgraduate_kind(name))


class DurationTests(unittest.TestCase):
    def test_converts_the_published_units_to_months(self) -> None:
        self.assertEqual(duration_months("1 año"), 12)
        self.assertEqual(duration_months("4 años"), 48)
        self.assertEqual(duration_months("3 cuatrimestres"), 12)
        self.assertEqual(duration_months("2 semestres"), 12)
        self.assertEqual(duration_months("18 meses"), 18)
        self.assertEqual(duration_months("1,5 años"), 18)

    def test_an_unmeasured_duration_stays_null(self) -> None:
        for value in (None, "", "A definir", "Flexible"):
            self.assertIsNone(duration_months(value))


class ModalityTests(unittest.TestCase):
    def test_maps_the_published_label_to_the_contract_enum(self) -> None:
        self.assertEqual(postgraduate_modality("Presencial"), "Presencial")
        self.assertEqual(postgraduate_modality("Online"), "Virtual")
        self.assertEqual(postgraduate_modality("Híbrida (Presencial + Online)"), "Híbrida")
        self.assertEqual(postgraduate_modality("Presencial y online"), "Híbrida")
        self.assertEqual(postgraduate_modality("Online sincrónica y presencial"), "Híbrida")

    def test_an_unmappable_label_stays_null(self) -> None:
        for value in (None, "", "Flexible", "A confirmar"):
            self.assertIsNone(postgraduate_modality(value))


class CampusTests(unittest.TestCase):
    def test_accepts_only_a_label_that_is_an_official_campus(self) -> None:
        self.assertEqual(postgraduate_campus("Campus Victoria"), "Campus Victoria")
        self.assertEqual(postgraduate_campus("Riobamba"), "Sede Riobamba")

    def test_never_reads_a_campus_out_of_a_compound_label(self) -> None:
        for value in ("Clarín / Riobamba / Artear / Radio Mitre",
                      "Campus Victoria / Suipacha", "Riobamba y Campus Victoria",
                      "Suipacha 1333 (CABA)", "Perú 352, C.A.B.A."):
            self.assertIsNone(postgraduate_campus(value))


class AcademicUnitTests(unittest.TestCase):
    def test_splits_the_published_unit(self) -> None:
        self.assertEqual(split_academic_unit("Departamento de Economía"), ("Economía", "Departamento"))
        self.assertEqual(split_academic_unit("Escuela de Negocios"), ("Negocios", "Escuela"))

    def test_an_unknown_shape_is_not_forced(self) -> None:
        for value in (None, "", "Economía", "Instituto de Economía"):
            self.assertIsNone(split_academic_unit(value))


class DetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ref = PostgraduateRef("Maestría en Economía",
                                   "https://udesa.edu.ar/departamento-de-economia/maestria-en-economia",
                                   "Departamento de Economía")
        self.attendance = [
            {"label": "Duración", "body": "1 año"},
            {"label": "Sede", "body": "Campus Victoria"},
            {"label": "Modalidad", "body": "Presencial"},
            {"label": "Inicio", "body": "Marzo&nbsp;"},
        ]

    def test_reads_the_published_cells(self) -> None:
        detail = parse_postgraduate_detail(
            self.ref, _page("Maestría en Economía", self.attendance), self.ref.url
        )
        self.assertEqual(detail["duration_months"], 12)
        self.assertEqual(detail["campus"], "Campus Victoria")
        self.assertEqual(detail["modality"], "Presencial")
        self.assertEqual(detail["start"], "Marzo")
        self.assertEqual(detail["description"], "Formación en teoría y práctica.")

    def test_accepts_the_plural_campus_label(self) -> None:
        attendance = [{"label": "Sedes", "body": "Campus Victoria"}]
        detail = parse_postgraduate_detail(self.ref, _page("Maestría en Economía", attendance), self.ref.url)
        self.assertEqual(detail["campus"], "Campus Victoria")

    def test_a_page_without_the_cells_keeps_them_null(self) -> None:
        detail = parse_postgraduate_detail(self.ref, _page("Maestría en Economía"), self.ref.url)
        for field in ("duration_months", "campus", "modality", "start"):
            self.assertIsNone(detail[field], field)

    def test_rejects_a_redirect_to_another_programme(self) -> None:
        with self.assertRaises(ValueError):
            parse_postgraduate_detail(self.ref, _page("Maestría en Finanzas"), self.ref.url)

    def test_rejects_a_page_that_is_not_a_postgraduate(self) -> None:
        page = _page("Maestría en Economía")
        page["pageType"] = "Undergraduate"
        with self.assertRaises(ValueError):
            parse_postgraduate_detail(self.ref, page, self.ref.url)

    def test_finds_the_plan_under_either_field_name(self) -> None:
        for field in ("graduatePageType", "undergraduatePageType"):
            page = _page("Maestría en Economía", cards=[
                {"graduatePage": [{field: "Plan de estudios", "url": "/x/plan-de-estudios"}]}])
            self.assertEqual(discover_graduate_plan_url(page, self.ref.url),
                             "https://udesa.edu.ar/x/plan-de-estudios")

    def test_a_missing_page_type_label_does_not_crash(self) -> None:
        page = _page("Maestría en Economía", cards=[{"graduatePage": [{"url": "/x"}]}])
        self.assertIsNone(discover_graduate_plan_url(page, self.ref.url))


class BuildAndValidateTests(unittest.TestCase):
    def _dataset(self, pages: dict, refs: tuple) -> dict:
        return build_dataset({}, {}, {}, "", [], refs, pages)

    def test_every_discovered_programme_is_loaded_or_excluded(self) -> None:
        ok = PostgraduateRef("Maestría en Economía", "https://udesa.edu.ar/a", "Departamento de Economía")
        gone = PostgraduateRef("Maestría en Finanzas", "https://udesa.edu.ar/b", "Escuela de Negocios")
        dataset = self._dataset(
            {ok.url: (_page("Maestría en Economía"), ok.url)}, (ok, gone)
        )
        quality = dataset["control_calidad"]
        self.assertEqual(quality["posgrados_descubiertos"], 2)
        self.assertEqual(len(dataset["datos"]["posgrados"]), 1)
        self.assertEqual(len(quality["posgrados_excluidos"]), 1)
        self.assertIn("no se pudo descargar", quality["posgrados_excluidos"][0]["motivo"])
        validate_postgraduates(dataset, dataset["datos"])

    def test_a_wrong_page_excludes_the_programme_with_its_reason(self) -> None:
        ref = PostgraduateRef("Maestría en Economía", "https://udesa.edu.ar/a", "Departamento de Economía")
        dataset = self._dataset({ref.url: (_page("Otra Maestría"), ref.url)}, (ref,))
        self.assertEqual(dataset["datos"]["posgrados"], [])
        self.assertEqual(len(dataset["control_calidad"]["posgrados_excluidos"]), 1)

    def test_the_unit_of_a_postgraduate_becomes_an_academic_unit(self) -> None:
        ref = PostgraduateRef("Maestría en Ciencia de Datos", "https://udesa.edu.ar/a",
                              "Departamento de Matemática y Ciencias")
        dataset = self._dataset({ref.url: (_page("Maestría en Ciencia de Datos"), ref.url)}, (ref,))
        units = {row["nombre_facultad"] for row in dataset["datos"]["facultades"]}
        self.assertIn("Matemática y Ciencias", units)
        self.assertEqual(dataset["datos"]["posgrados"][0]["facultad_nombre"],
                         f"{UNIVERSITY} — Departamento de Matemática y Ciencias")

    def test_the_plan_is_linked_as_evidence_and_never_becomes_subjects(self) -> None:
        ref = PostgraduateRef("Maestría en Economía", "https://udesa.edu.ar/a", "Departamento de Economía")
        page = _page("Maestría en Economía", cards=[
            {"graduatePage": [{"graduatePageType": "Plan de estudios", "url": "/a/plan-de-estudios"}]}])
        dataset = self._dataset({ref.url: (page, ref.url)}, (ref,))
        self.assertEqual(dataset["datos"]["materias"], [])
        links = [r for r in dataset["recursos_publicos"] if r["tipo_recurso"] == "enlace"]
        self.assertEqual(links[0]["url"], "https://udesa.edu.ar/a/plan-de-estudios")

    def test_validation_fails_when_a_programme_is_neither_loaded_nor_excluded(self) -> None:
        dataset = {"control_calidad": {"posgrados_descubiertos": 3, "posgrados_excluidos": []},
                   "datos": {"posgrados": []}}
        with self.assertRaises(ValueError):
            validate_postgraduates(dataset, dataset["datos"])
