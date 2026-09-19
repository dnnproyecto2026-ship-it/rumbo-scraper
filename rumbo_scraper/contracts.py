"""Data contract derived from carga_carreras.xlsx."""

SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "localidades": ("nombre_localidad", "provincia", "codigo_postal"),
    "universidades": (
        "nombre_oficial", "nombre_corto", "tipo_gestion", "anio_fundacion",
        "sitio_web", "telefono_area", "telefono_numero", "mail_contacto",
        "instagram", "tiktok", "linkedin", "twitter", "facebook", "youtube",
    ),
    "sedes": ("universidad_nombre", "nombre_sede", "localidad", "calle", "numero", "tipo_sede"),
    "facultades": ("universidad_nombre", "nombre_facultad", "tipo_unidad", "sede"),
    "carreras": (
        "universidad_nombre", "facultad_nombre", "nombre_carrera",
        "denominacion_canonica", "nivel", "titulo_otorgado",
        "tiene_titulo_intermedio", "duracion_anios", "es_art_43",
        "descripcion_breve", "cantidad_materias_total",
    ),
    "ofertas": (
        "universidad_nombre", "facultad_nombre", "carrera_nombre", "sede",
        "modalidad", "regimen_ingreso", "coneau_resolucion",
        "coneau_vigencia_hasta", "tiene_pasantias", "tiene_bolsa_trabajo",
    ),
    "turnos_anio": ("universidad_nombre", "carrera_nombre", "sede", "anio_carrera", "turno"),
    "ofertas_ciclo": (
        "universidad_nombre", "carrera_nombre", "sede", "ciclo_anio",
        "ciclo_nombre", "cupo_ingresantes", "fecha_apertura_inscripcion",
        "fecha_cierre_inscripcion", "estado",
    ),
    "aranceles": (
        "universidad_nombre", "carrera_nombre", "sede", "vigencia_desde",
        "monto_mensual", "monto_matricula", "moneda", "motivo_cambio",
    ),
    "areas_tematicas": (
        "universidad_nombre", "facultad_nombre", "carrera_nombre",
        "area_tematica", "cantidad_materias",
    ),
    "materias": (
        "universidad_nombre", "carrera_o_programa", "nombre_materia",
        "anio_cursada", "turno", "area_tematica", "descripcion_breve",
        "regimen", "carga_horaria_semanal",
    ),
    "posgrados": (
        "universidad_nombre", "facultad_nombre", "nombre_programa",
        "tipo_posgrado", "titulo_otorgado", "sede", "modalidad",
        "duracion_meses", "requiere_tesis_trabajo_final",
        "requisito_titulo_previo", "cohorte_inicio", "costo_total_programa",
        "moneda", "descripcion_breve",
    ),
    "actividades": (
        "universidad_nombre", "carrera_o_programa", "tipo_actividad",
        "nombre_actividad", "obligatoria", "carga_horaria_total", "descripcion_breve",
    ),
    "autoridades": ("facultad_nombre", "carrera", "cargo", "tipo", "nombre_autoridad"),
    "redes_contacto": ("universidad_nombre", "facultad_nombre", "canal", "usuario_o_direccion"),
    "becas": (
        "universidad_nombre", "nombre_beca", "nivel", "tipo_beca",
        "cobertura_descripcion", "porcentaje_maximo", "requisitos",
        "proceso_postulacion", "renovacion", "fecha_cierre",
        "url_postulacion", "contacto", "fuente_url",
    ),
    "servicios_estudiantiles": (
        "universidad_nombre", "sede", "categoria", "nombre_servicio",
        "descripcion", "contacto", "url", "fuente_url",
    ),
    "actividades_extracurriculares": (
        "universidad_nombre", "sede", "categoria", "nombre_actividad",
        "descripcion", "contacto", "url", "fuente_url",
    ),
    "alojamiento": (
        "universidad_nombre", "sede", "tipo_apoyo", "tipo_alojamiento",
        "residencia_propia", "descripcion", "contacto", "url", "fuente_url",
    ),
    "programas_internacionales": (
        "universidad_nombre", "nivel", "tipo_programa", "nombre_programa",
        "cantidad_convenios", "duracion_maxima", "reconocimiento_academico",
        "arancel_destino_cubierto", "requisitos", "url", "fuente_url",
    ),
}


def blank_record(section: str, **values: object) -> dict[str, object]:
    """Create a record containing every column in the Excel contract."""
    fields = SECTION_FIELDS[section]
    unknown = set(values) - set(fields)
    if unknown:
        raise KeyError(f"Unknown {section} fields: {sorted(unknown)}")
    return {field: values.get(field) for field in fields}
