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


from rumbo_scraper.parsers import perfil, vida


class PerfilTests(unittest.TestCase):
    FOOTER = """
    <footer>
      <a href="https://www.instagram.com/itbauniversidad/">Instagram</a>
      <a href="https://x.com/ITBA">X</a>
      <a href="https://www.youtube.com/watch?v=abc">Nuestro video</a>
      <a href="https://www.youtube.com/user/ITBAuniversidad">YouTube</a>
      <a href="https://www.facebook.com/sharer/sharer.php?u=https://itba.edu.ar">Compartir</a>
      <a href="mailto:rrhh@itba.edu.ar">Trabajá con nosotros</a>
      <a href="mailto:informes@itba.edu.ar">Informes</a>
      <a href="tel:+54 11 5371 5600">Teléfono</a>
    </footer>
    """

    def test_reads_the_account_of_each_network(self) -> None:
        accounts = perfil.social_accounts(self.FOOTER, "https://www.itba.edu.ar")
        self.assertEqual(accounts["instagram"],
                         "https://www.instagram.com/itbauniversidad/")
        self.assertEqual(accounts["twitter"], "https://x.com/ITBA")

    def test_a_video_is_not_the_account_that_published_it(self) -> None:
        accounts = perfil.social_accounts(self.FOOTER, "https://www.itba.edu.ar")
        self.assertEqual(accounts["youtube"],
                         "https://www.youtube.com/user/ITBAuniversidad")

    def test_the_button_that_shares_the_page_is_not_an_account(self) -> None:
        accounts = perfil.social_accounts(self.FOOTER, "https://www.itba.edu.ar")
        self.assertNotIn("facebook", accounts)

    def test_the_contact_is_the_address_named_for_information(self) -> None:
        # The first address of the domain receives job applications; publishing
        # it as the contact of the university would be worse than none.
        contact = perfil.contact(self.FOOTER, "itba.edu.ar")
        self.assertEqual(contact["mail_contacto"], "informes@itba.edu.ar")

    def test_the_telephone_is_split_where_the_site_split_it(self) -> None:
        contact = perfil.contact(self.FOOTER, "itba.edu.ar")
        self.assertEqual(contact["telefono_area"], "11")
        self.assertEqual(contact["telefono_numero"], "53715600")

    def test_a_national_number_has_no_area_to_split(self) -> None:
        self.assertEqual(perfil._split_phone("0810-122-1222"), (None, "8101221222"))

    def test_a_number_published_without_its_area_keeps_it_empty(self) -> None:
        # Guessing where the area ends turns 2304-431260 into area 23.
        self.assertEqual(perfil._split_phone("+542304431260"), (None, "2304431260"))

    def test_a_page_of_another_domain_is_not_read(self) -> None:
        profile = perfil.read_profile({"https://example.com": self.FOOTER}, "itba.edu.ar")
        self.assertEqual(profile, {})


class VidaTests(unittest.TestCase):
    HOME = """
    <a href="/becas">Becas de grado</a>
    <a href="/deportes">Deportes</a>
    <a href="/noticias/beca-ganada">Una beca ganada</a>
    <a href="https://otro.com/becas">Becas de otro</a>
    """

    def test_the_words_of_the_link_decide_the_topic(self) -> None:
        topics = vida.discover_topics(self.HOME, "https://www.ub.edu.ar", "ub.edu.ar")
        self.assertEqual(topics["becas"], ["https://www.ub.edu.ar/becas"])
        self.assertEqual(topics["actividades_extracurriculares"],
                         ["https://www.ub.edu.ar/deportes"])

    def test_a_news_item_about_a_topic_is_not_its_page(self) -> None:
        topics = vida.discover_topics(self.HOME, "https://www.ub.edu.ar", "ub.edu.ar")
        self.assertNotIn("https://www.ub.edu.ar/noticias/beca-ganada", topics["becas"])

    def test_a_page_of_another_site_is_not_read(self) -> None:
        topics = vida.discover_topics(self.HOME, "https://www.ub.edu.ar", "ub.edu.ar")
        self.assertTrue(all("otro.com" not in url
                            for urls in topics.values() for url in urls))

    def test_an_item_is_kept_only_when_its_name_names_the_topic(self) -> None:
        page = ("<h2>Coro</h2><p>El coro de la universidad ensaya los martes "
                "en el aula magna del campus.</p>"
                "<h2>Esteban Girón</h2><p>Contó su experiencia en el coro "
                "durante el encuentro anual de estudiantes de la casa.</p>")
        items = vida.read_items(page, "actividades_extracurriculares")
        self.assertEqual([item["titulo"] for item in items], ["Coro"])

    def test_a_page_of_prose_lists_nothing(self) -> None:
        self.assertEqual(vida.read_items("<p>Ofrecemos becas.</p>", "becas"), [])

    def test_the_share_a_scholarship_covers_is_read_when_stated(self) -> None:
        self.assertEqual(vida.percentage("Cubre hasta el 35% del arancel"), 35.0)
        self.assertIsNone(vida.percentage("Cubre parte del arancel"))
