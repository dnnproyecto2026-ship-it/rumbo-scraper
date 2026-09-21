"""Tests for the complete UTDT scraper contract."""

import unittest

from rumbo_scraper.contracts import SECTION_FIELDS
from rumbo_scraper.parsers.utdt import (
    ACADEMIC_UNITS, CAREERS, build_dataset, parse_career_detail,
    build_academic_directory,
    parse_careers, parse_extracurricular_activities,
    parse_exchange_agreements,
    discover_postgraduates, parse_postgraduates, parse_postgraduate_detail,
    parse_postgraduate_subjects, PostgraduateConfig,
    parse_admissions_summary,
    parse_faculty_authorities, parse_housing, parse_international_programs,
    parse_professor_page, parse_scholarships, parse_study_plan,
    parse_person_profile,
)
from rumbo_scraper.validators.utdt import validate_dataset


class UTDTParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admissions = "<html><h2>marzo 2027</h2>" + "".join(
            f"<a>{key}</a>" for key in CAREERS
        ) + "</html>"
        self.institution = "<html>" + " ".join(
            f"{unit_type} de {name}" for name, unit_type in ACADEMIC_UNITS
        ) + " Maestría en Economía Doctorado en Historia</html>"

    def test_contract_contains_every_excel_section(self) -> None:
        self.assertEqual(len(SECTION_FIELDS), 21)
        self.assertIn("aranceles", SECTION_FIELDS)
        self.assertIn("posgrados", SECTION_FIELDS)
        self.assertIn("redes_contacto", SECTION_FIELDS)

    def test_extracts_current_careers(self) -> None:
        careers = parse_careers(self.admissions)
        self.assertEqual(len(careers), 13)
        self.assertEqual(len({item.denominacion_canonica for item in careers}), 13)

    def test_extracts_current_admission_regime_and_open_state(self) -> None:
        html = """
        <h2>Admisión por ingreso directo</h2><p>También podés realizar el curso de ingreso.</p>
        <a href="/admisiones/grado">Completá la solicitud de admisión</a>
        """
        self.assertEqual(parse_admissions_summary(html), {
            "regimen_ingreso": "Ingreso directo o curso de ingreso",
            "estado": "Abierta",
        })

    def test_discovers_and_splits_current_postgraduates(self) -> None:
        index = """
        <div class="programas-body"><h3 class="tit-escuela">Derecho</h3>
          <div class="card"><h3>Maestría y Especialización en Derecho Penal</h3>
            <a href="/penal">Ver más</a></div>
        </div>
        """
        configs = discover_postgraduates(index)
        self.assertEqual([row.name for row in configs], [
            "Maestría en Derecho Penal", "Especialización en Derecho Penal",
        ])
        rows = [row for row in parse_postgraduates(index, {
            "https://www.utdt.edu/penal": """
                <main><p>Una propuesta académica extensa que brinda herramientas avanzadas para profesionales del derecho y el sistema penal contemporáneo.</p></main>
                <main><p>La Especialización se dicta durante tres cuatrimestres.</p>
                <p>La duración aproximada total de la Maestría es de cinco cuatrimestres.</p>
                <p>Formato: híbrido. La Maestría concluye con una tesis.</p>
                <h3>Requisitos</h3><p>Contar con título universitario de grado.</p></main>
            """,
        }) if "Derecho Penal" in row["nombre_programa"]]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["duracion_meses"], 20)
        self.assertEqual(rows[1]["duracion_meses"], 12)
        self.assertEqual(rows[0]["modalidad"], "Híbrida")
        self.assertEqual(rows[0]["url_oficial"], "https://www.utdt.edu/penal")

    def test_enriches_postgraduate_title_format_and_curriculum(self) -> None:
        config = PostgraduateConfig(
            "Doctorado en Derecho", "Doctorado", "Derecho", "https://example.edu/doctorado"
        )
        pages = ["""
            <main id="contenido"><h2>Plan de estudios</h2>
            <p>Duración: 4 años. Modalidad blended.</p>
            <p>1) Metodología de la Investigación Jurídica</p>
            <p>Título a obtener: Doctor/a en Derecho</p></main>
        """]
        detail = parse_postgraduate_detail(config, pages)
        self.assertEqual(detail["titulo_otorgado"], "Doctor/a en Derecho")
        self.assertEqual(detail["modalidad"], "Híbrida")
        self.assertEqual(detail["duracion_meses"], 48)
        index = """
            <div class="programas-body"><h3 class="tit-escuela">Derecho</h3>
            <div class="card"><h3>Doctorado en Derecho</h3>
            <a href="https://example.edu/doctorado">Ver más</a></div></div>
        """
        subjects = parse_postgraduate_subjects(
            index, {"https://example.edu/doctorado": pages}
        )
        self.assertEqual(
            [row["nombre_materia"] for row in subjects],
            ["Metodología de la Investigación Jurídica"],
        )

    def test_postgraduate_curriculum_ignores_navigation_and_people(self) -> None:
        index = """
            <div class="programas-body"><h3 class="tit-escuela">Derecho</h3>
            <div class="card"><h3>Doctorado en Derecho</h3>
            <a href="https://example.edu/doctorado">Ver más</a></div></div>
        """
        pages = ["""
            <main id="contenido"><h2>Plan de estudios</h2>
            <ul class="navigation"><li>Admisión</li><li>Profesores</li></ul>
            <p>1) Metodología de la Investigación Jurídica</p>
            <p>La profesora Ana Ejemplo dirige el programa desde 2026.</p>
            <h2>Noticias</h2><ul><li>Reunión informativa 2026</li></ul></main>
        """]
        subjects = parse_postgraduate_subjects(
            index, {"https://example.edu/doctorado": pages}
        )
        self.assertEqual(
            [row["nombre_materia"] for row in subjects],
            ["Metodología de la Investigación Jurídica"],
        )

    def test_parses_detail_and_study_plan(self) -> None:
        config = CAREERS["abogacia"]
        detail_html = """
        <html><meta name="description" content="Una descripción suficientemente extensa para presentar la carrera de Abogacía y explicar claramente su propuesta académica.">
        <h4>Duración</h4><h5>5 años</h5><h4>Modalidad</h4><h5>100% presencial</h5>
        <h4>Lugar</h4><h5>Campus Di Tella</h5><a href="/plan">Ver plan de estudios</a>
        <a>María Ejemplo</a><p>Directora de la carrera</p><p>Pasantías y Di Tella Gateway</p></html>
        """
        detail = parse_career_detail(detail_html, config)
        self.assertEqual(detail["duracion_anios"], 5.0)
        self.assertEqual(detail["modalidad"], "Presencial")
        self.assertEqual(detail["plan_url"], "https://www.utdt.edu/plan")
        plan = parse_study_plan(
            "<p><strong>Título:</strong> Abogado</p><p>Duración: 5 años</p><h3>1</h3><h4>1.º semestre</h4><ul><li>Derecho Constitucional I</li></ul>",
            "Abogacía",
        )
        self.assertEqual(plan["titulo_otorgado"], "Abogado")
        self.assertEqual(len(plan["materias"]), 1)

    def test_study_plan_accepts_named_years_and_stops_before_variants(self) -> None:
        plan = parse_study_plan("""
            <h2>Primer año</h2><h4>Primer semestre</h4>
            <article><div class="padded afcbe0"><p>Matemática I</p></div></article>
            <h2>Segundo año</h2><h4>Segundo semestre</h4>
            <article><div class="padded afcbe0"><p>Economía II</p></div></article>
            <h4>Plan con Campo Menor</h4>
            <h2>Primer año</h2><li>Matemática I</li>
        """, "Administración de Empresas")
        self.assertEqual(
            [row["nombre_materia"] for row in plan["materias"]],
            ["Matemática I", "Economía II"],
        )

    def test_study_plan_ignores_contact_form_options(self) -> None:
        plan = parse_study_plan("""
            <h2>1</h2><li>Laboratorio de Diseño I</li>
            <h3>Para recibir más información por e-mail</h3>
            <li>Abogacía</li><li>Arquitectura</li>
        """, "Diseño")
        self.assertEqual(len(plan["materias"]), 1)

    def test_extracts_public_person_profile(self) -> None:
        profile = parse_person_profile("""
            <article id="contenido"><h1>Ana Ejemplo</h1>
            <p>Ph.D. en Economía, Universidad Ejemplo.</p>
            <p>Ana Ejemplo es profesora e investigadora especializada en economía aplicada y publicó numerosos trabajos académicos internacionales.</p>
            <p>Email: ana@example.edu</p></article>
        """, "Ana Ejemplo")
        self.assertEqual(profile["email"], "ana@example.edu")
        self.assertIn("Ph.D.", profile["formacion"])
        self.assertIn("investigadora", profile["biografia"])

    def test_builds_and_validates_all_sections(self) -> None:
        detail_pages = {
            config.detail_url: "<h4>Duración</h4><h5>4 años</h5><h4>Modalidad</h4><h5>Presencial</h5>"
            for config in CAREERS.values()
        }
        dataset = build_dataset(self.admissions, self.institution, detail_pages, {})
        validate_dataset(dataset)
        self.assertEqual(set(dataset["datos"]), set(SECTION_FIELDS))
        self.assertEqual(len(dataset["datos"]["carreras"]), 13)
        self.assertIn("turnos_anio", dataset["control_calidad"]["secciones_vacias"])

    def test_extracts_faculty_directors(self) -> None:
        html = """
        <h4>Escuela de Derecho</h4>
        <p><strong>Decano: Alejandro Ejemplo.</strong></p>
        <h4>Escuela de Gobierno</h4>
        <p><strong>Decano ejecutivo: Darío Ejemplo.</strong></p>
        <p><strong>Decana académica: María Ejemplo.</strong></p>
        <h4>Otra sección</h4>
        """
        rows = parse_faculty_authorities(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["cargo"], "Decano")
        self.assertEqual(rows[0]["nombre_autoridad"], "Alejandro Ejemplo")
        self.assertTrue(all(row["carrera"] is None for row in rows))

    def test_extracts_professors_without_confusing_headings(self) -> None:
        html = """
        <article id="contenido"><h2>Cuerpo de Profesores</h2>
        <a href="/perfil/1">Pérez,</a><a href="/perfil/1">Ana María.</a>
        <strong>Juan García.</strong><strong>Profesores Visitantes:</strong>
        </article>
        """
        rows = parse_professor_page(html, "Derecho", "https://www.utdt.edu/docentes")
        self.assertEqual([row["nombre_completo"] for row in rows], ["Ana María Pérez", "Juan García"])

    def test_academic_roles_use_the_canonical_person_name(self) -> None:
        directory = build_academic_directory(
            [{
                "nombre_autoridad": "Andrés de la Cruz",
                "facultad_nombre": "Universidad — Escuela de Negocios",
                "carrera": "Tecnología Digital",
                "cargo": "Director/a de carrera",
                "tipo": "Académico",
            }],
            {"Negocios": "<article id='contenido'><strong>Andrés De la Cruz.</strong></article>"},
        )
        names = {row["nombre_completo"] for row in directory["personas"]}
        role_names = {row["nombre_completo"] for row in directory["roles_academicos"]}
        self.assertEqual(names, {"Andrés de la Cruz"})
        self.assertEqual(role_names, names)

    def test_extracts_student_life_and_financial_aid(self) -> None:
        scholarships = parse_scholarships("""
        BECA INTERIOR Estudiantes a más de 100 km de CABA - 30% del arancel
        BECA DESTACADOS Desempeño sobresaliente - 25% del arancel
        BECA PREMIO AL MÉRITO Promedio mayor o igual a 8 - 20% del arancel.
        INFORMACIÓN DE LA SOLICITUD
        """)
        self.assertEqual(len(scholarships), 3)
        self.assertEqual(scholarships[0]["porcentaje_maximo"], 30)
        activities = parse_extracurricular_activities(
            "Ajedrez, Fútbol, Yoga y Taller de Teatro",
            '<a href="/club">Club de Debate</a>',
            "Centro de Estudiantes", "Acción Social",
        )
        self.assertEqual(
            {row["nombre_actividad"] for row in activities},
            {"Ajedrez", "Fútbol", "Yoga", "Taller de Teatro", "Club de Debate", "Centro de Estudiantes", "Acción Social"},
        )
        self.assertEqual(len(parse_housing("Residencias universitarias, casas de familia y departamentos")), 3)
        international = parse_international_programs(
            "Más de 156 convenios. Intercambio, doble titulación y free movers. "
            "Las materias aprobadas son reconocidas y se cursa sin abonar matrícula."
        )
        self.assertEqual(len(international), 3)
        self.assertEqual(international[0]["cantidad_convenios"], 156)

    def test_extracts_exchange_destinations_by_program(self) -> None:
        html = '''<script>
        var dataMapa = {"destino": {
          "universidad": "Universidad Ejemplo - Madrid, España",
          "programas": "Arquitectura, Licenciatura en Tecnología Digital",
          "info": "<strong>Carreras:</strong><ul><li>Arquitectura</li><li>Licenciatura en Tecnología Digital (4to año)</li></ul>",
          "pais": "", "ciudad": "Madrid, España",
          "lat": "40.4", "lng": "-3.7"
        }};
        var dataProgramas = [];
        </script>'''
        rows = parse_exchange_agreements(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["universidad_destino"], "Universidad Ejemplo - Madrid, España")
        self.assertEqual(rows[0]["pais"], "España")
        self.assertEqual(rows[1]["programa_origen"], "Licenciatura en Tecnología Digital (4to año)")


if __name__ == "__main__":
    unittest.main()
