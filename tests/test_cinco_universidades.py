"""Tests for the five adapters added together: UAI, Palermo, UCEMA, UCES, USAL."""

import unittest

from rumbo_scraper.parsers import palermo, uai, uces, ucema, usal


class UaiTests(unittest.TestCase):
    PAGE = """
    <div class="redbox">
      <p><b>Título Final:</b> Arquitecto</p>
      <p><b>Título intermedio:</b> Analista (3 años)</p>
      <p><b>Duración:</b> 5 años</p>
      <p><b>Modalidad:</b> Presencial</p>
    </div>
    <div class="content" id="Estudio">
      <iframe src="https://nbapi.uai.edu.ar/tpl/planestudio?anioc=&carrera=A1&db=UAI"></iframe>
      <!--plan A1
        Carrera de Grado-->
    </div>
    """

    def test_reads_the_box_of_facts(self) -> None:
        facts = uai.parse_facts(self.PAGE)
        self.assertEqual(facts["titulo_final"], "Arquitecto")
        self.assertEqual(facts["duracion"], "5 años")
        self.assertEqual(facts["modalidad"], "Presencial")

    def test_the_comment_beside_the_plan_states_the_code_and_the_level(self) -> None:
        reference = uai.parse_plan_reference(self.PAGE)
        self.assertEqual(reference["codigo"], "A1")
        self.assertEqual(reference["nivel"], "Grado")

    def test_a_career_is_a_page_two_levels_below_the_faculties(self) -> None:
        sitemap = ("<loc>https://uai.edu.ar/facultades/arquitectura/arquitectura/</loc>"
                   "<loc>https://uai.edu.ar/facultades/arquitectura/arquitectura/actividades/</loc>"
                   "<loc>https://uai.edu.ar/facultades/publicaciones/revista/</loc>")
        refs = uai.discover_careers(sitemap)
        self.assertEqual([ref.slug for ref in refs], ["arquitectura"])
        self.assertEqual(refs[0].faculty, "Facultad de Arquitectura")

    def test_the_plan_lends_its_year_to_the_subjects_below_it(self) -> None:
        plan = ("1er Año\nMaterias del primer cuatrimestre\nCódigo\nAsignatura\n"
                "Correlativas\nCarga\n01\nINTRODUCCIÓN A LA ARQUITECTURA\n48\n"
                "02\nCONSTRUCCIONES I\n48\n2do Año\n03\nFÍSICA APLICADA\n64\n")
        rows = uai.parse_plan(f"<pre>{plan}</pre>", "Arquitectura")
        self.assertEqual([(r["anio_cursada"], r["nombre_materia"]) for r in rows], [
            (1, "INTRODUCCIÓN A LA ARQUITECTURA"), (1, "CONSTRUCCIONES I"),
            (2, "FÍSICA APLICADA"),
        ])

    def test_the_summary_of_hours_is_not_a_subject(self) -> None:
        plan = "1er Año\n01\nÁLGEBRA\n48\nTotal\n3584\nTítulo\nArquitecto\n"
        names = {r["nombre_materia"] for r in uai.parse_plan(f"<pre>{plan}</pre>", "X")}
        self.assertEqual(names, {"ÁLGEBRA"})

    def test_the_cross_that_closes_a_panel_is_not_part_of_a_name(self) -> None:
        table = ('<div id="Autoridades"><table>'
                 '<tr><td>Decana: Dra. Vicenta Quallito vq@uai.edu.ar ×</td></tr>'
                 '</table></div>')
        rows = uai.parse_authorities(table, "Facultad de Arquitectura")
        self.assertEqual(rows[0]["nombre_autoridad"], "Dra. Vicenta Quallito")
        self.assertEqual(rows[0]["cargo"], "Decana")


class PalermoTests(unittest.TestCase):
    PLAN = """
    <div class="curso">
      <div class="cuadro-rojo year">1<span>er año</span></div>
      <ul class="bloque"><li><a href="#"><span>Derecho Civil</span></a></li>
      <li><a href="#"><span>Derechos Humanos</span></a></li></ul>
    </div>
    <div class="curso">
      <div class="cuadro-rojo year">2<span>do año</span></div>
      <ul class="bloque"><li><a href="#"><span>Contratos en Particular</span></a></li></ul>
    </div>
    <p>El plan de estudios describe cada materia en detalle más abajo.</p>
    """

    def test_the_markup_says_which_year_teaches_each_subject(self) -> None:
        rows = palermo.parse_plan(self.PLAN, "Abogacía")
        self.assertEqual([(r["anio_cursada"], r["nombre_materia"]) for r in rows], [
            (1, "Derecho Civil"), (1, "Derechos Humanos"),
            (2, "Contratos en Particular"),
        ])

    def test_the_description_printed_below_the_plan_is_not_a_subject(self) -> None:
        names = {r["nombre_materia"] for r in palermo.parse_plan(self.PLAN, "Abogacía")}
        self.assertNotIn("El plan de estudios describe cada materia en detalle más abajo.",
                         names)

    def test_a_name_the_column_wrapped_is_put_back_together(self) -> None:
        joined = palermo.join_headings([
            "1", "er año", "Teoría General del Acto Jurídico y de los", "Contratos",
        ])
        self.assertEqual(joined, ["1er año",
                                  "Teoría General del Acto Jurídico y de los Contratos"])

    def test_a_career_taught_online_and_on_campus_is_one_career(self) -> None:
        index = ('<a href="/dyc/fotografia/">Licenciatura en Fotografía</a>'
                 '<a href="/online/fotografia/">Licenciatura en Fotografía</a>')
        refs = palermo.discover_careers({palermo.INDEXES[0][0]: index})
        self.assertEqual(len(refs), 1)


class UcemaTests(unittest.TestCase):
    PAGE = """
    <div><div class="field-label-above">Titulación</div>Licenciado/a en Economía</div>
    <div><div class="field-label-above">Modalidad</div>Presencial</div>
    <div><div class="field-label-above">Duración</div>4 años</div>
    <div><div class="field-label-above">Reconocimiento Oficial</div>DISP 675/25</div>
    """

    def test_each_label_sits_above_its_own_value(self) -> None:
        facts = ucema.parse_facts(self.PAGE)
        self.assertEqual(facts["titulacion"], "Licenciado/a en Economía")
        self.assertEqual(facts["reconocimiento"], "DISP 675/25")
        self.assertEqual(ucema.duration_years(facts["duracion"]), 4.0)

    def test_the_branch_of_the_sitemap_states_the_level(self) -> None:
        sitemap = ("<loc>https://ucema.edu.ar/grado/licenciatura-en-economia</loc>"
                   "<loc>https://ucema.edu.ar/posgrado/mba</loc>"
                   "<loc>https://ucema.edu.ar/evento/charla</loc>")
        refs = ucema.discover_programmes({"a": sitemap})
        self.assertEqual([(r.slug, r.level) for r in refs],
                         [("licenciatura-en-economia", "Grado"), ("mba", "Posgrado")])

    def test_a_page_that_states_no_fact_is_not_a_programme(self) -> None:
        refs = ucema.discover_programmes(
            {"a": "<loc>https://ucema.edu.ar/posgrado/reunion</loc>"}
        )
        dataset = ucema.build_dataset(refs, {refs[0].url: "<p>Charla informativa</p>"})
        self.assertEqual(dataset["datos"]["posgrados"], [])
        self.assertIn("no publica datos",
                      dataset["control_calidad"]["programas_excluidos"][0]["motivo"])


class UcesTests(unittest.TestCase):
    INDEX = ('<script>laravel.data = {"Ciencias Econ\\u00f3micas":[{"id":402,'
             '"slug":"contador-publico","url":"/carreras-universitarias/fce/contador",'
             '"titulo":"Contador P\\u00fablico","tipoCarrera":"grado",'
             '"facultad":{"title":"Facultad de Ciencias Econ\\u00f3micas",'
             '"direccion":"Paraguay 1318","ciudad":"Ciudad de Buenos Aires",'
             '"provincia":"Capital Federal","cp":"C1057AAV",'
             '"telefono":"4815-3290","email":"fce@uces.edu.ar"}}]};</script>')

    def test_the_index_prints_its_own_catalogue(self) -> None:
        refs = uces.discover_careers(self.INDEX)
        self.assertEqual(refs[0].name, "Contador Público")
        self.assertEqual(refs[0].faculty, "Facultad de Ciencias Económicas")

    def test_the_faculty_carries_where_it_is(self) -> None:
        faculty = uces.read_faculties(self.INDEX)[0]
        self.assertEqual(faculty["direccion"], "Paraguay 1318")
        self.assertEqual(faculty["email"], "fce@uces.edu.ar")

    def test_the_plan_is_html_with_a_heading_per_year(self) -> None:
        plan = ("<h3><strong>Primer año - Primer cuatrimestre</strong></h3>"
                "<ul><li>Fundamentos de Contabilidad</li><li>Álgebra</li></ul>"
                "<h3><strong>Segundo año</strong></h3><ul><li>Estadística</li></ul>")
        rows = uces.parse_plan(plan, "Contador Público")
        self.assertEqual([(r["anio_cursada"], r["nombre_materia"]) for r in rows], [
            (1, "Fundamentos de Contabilidad"), (1, "Álgebra"), (2, "Estadística"),
        ])
        self.assertEqual(rows[0]["regimen"], "Cuatrimestral")


class UsalTests(unittest.TestCase):
    PAGE = """
    <p>Facultad de Ciencias Económicas y Empresariales</p>
    <p>Centro: RESFC-2020-572- APN-CONEAU#ME</p>
    <p>Título:</p><p>Contador Público</p><p>(4 años)</p>
    <table><tr><td>ARANCELES – Ingreso Segundo Cuatrimestre 2026 (Sujeto a modificación)</td></tr>
    <tr><td>Derecho de Inscripción: $ 190.000 Matrícula Semestral: $ 759.957
    6 cuotas mensuales (julio a diciembre) de: $ 670.980</td></tr></table>
    """

    def test_reads_the_degree_its_length_and_its_accreditation(self) -> None:
        facts = usal.parse_facts(self.PAGE)
        self.assertEqual(facts["titulo"], "Contador Público")
        self.assertEqual(usal.duration_years(facts["duracion"]), 4.0)
        self.assertEqual(facts["coneau"], "RESFC-2020-572- APN-CONEAU#ME")

    def test_reads_what_the_career_costs(self) -> None:
        fees = usal.parse_fees(self.PAGE)
        self.assertEqual(fees["monto_matricula"], 759957)
        self.assertEqual(fees["monto_mensual"], 670980)

    def test_a_page_without_a_table_of_fees_publishes_none(self) -> None:
        self.assertEqual(usal.parse_fees("<p>Contador Público</p>"), {})

    def test_only_a_page_of_a_proposal_is_a_programme(self) -> None:
        index = ('<a href="https://www.usal.edu.ar/ingreso/propuesta/contador-publico/">'
                 'Contador Público</a>'
                 '<a href="https://www.usal.edu.ar/becas">Licenciatura en Becas</a>')
        refs = usal.discover_programmes({usal.INDEXES[0][0]: index})
        self.assertEqual([ref.name for ref in refs], ["Contador Público"])

    def test_the_modality_is_written_inside_the_name(self) -> None:
        self.assertEqual(usal.modality("Especialización en Comercio (A DISTANCIA)"),
                         "Virtual")
        self.assertIsNone(usal.modality("Contador Público"))


if __name__ == "__main__":
    unittest.main()
