# Rumbo Scraper

Base en Python para extraer, normalizar, validar y guardar información en Supabase.

## Preparación local

Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completa `.env` con tus credenciales de Supabase:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

La clave `SUPABASE_SERVICE_ROLE_KEY` es secreta. No la publiques ni la uses en el frontend. El archivo `.env` está excluido de Git.

## Estructura

```text
rumbo_scraper/
├── settings.py             # Variables de entorno
├── database/supabase.py    # Cliente de Supabase
├── spiders/                # Extracción por sitio
├── parsers/                # Conversión de respuestas a datos
├── normalizers/            # Limpieza y formato uniforme
└── validators/             # Validación antes de guardar
```

Importa `get_supabase_client` cuando necesites persistir datos:

```python
from rumbo_scraper.database import get_supabase_client

supabase = get_supabase_client()
```

## Extracción completa: Di Tella

Con el entorno virtual activado, ejecuta:

```bash
python -m rumbo_scraper.spiders.utdt
```

El comando consulta páginas oficiales de admisiones, información institucional,
carreras, planes de estudio y vida universitaria. Genera
`data/utdt_completo.json` con el contrato original de `carga_carreras.xlsx` más
becas, servicios estudiantiles, actividades extracurriculares, alojamiento,
programas internacionales y universidades de intercambio por carrera. También
recorre el índice vigente de posgrados y sus páginas de modalidad, plan y
admisión para guardar la unidad académica, URL oficial, descripción, duración,
modalidad, trabajo final y requisitos cuando están publicados.

Los datos que la web oficial no publica quedan como `null` y se detallan en `control_calidad`. El proceso es de solo lectura y no escribe en Supabase.

Para ejecutar las pruebas locales:

```bash
python -m unittest discover -v
```

## Carga en Supabase

Primero valida el archivo y muestra qué se cargaría, sin conectarse ni escribir:

```bash
python -m rumbo_scraper.database.load_utdt
```

Cuando el resumen sea correcto, la carga real se ejecuta explícitamente con:

```bash
python -m rumbo_scraper.database.load_utdt --apply
```

La carga usa las credenciales locales de `.env`, pero no las imprime. Por ahora
omite `turnos_anio` y `aranceles`, ya que la fuente pública no ofrece esos datos.

## Directorio académico

La base de Supabase debe contar con las tablas `personas` y `roles_academicos`.
El scraper permite que una persona tenga simultáneamente varios cargos y vínculos
con facultades, carreras y materias.

## Vida universitaria

Para cargar las secciones ampliadas, Supabase debe contar también con las tablas
`becas`, `servicios_estudiantiles`, `actividades_extracurriculares`,
`alojamientos`, `programas_internacionales` y `convenios_intercambio`. El repositorio no contiene SQL:
las modificaciones del esquema se administran por separado en Supabase.

## Catálogo semestral de materias

El catálogo público de UTDT incluye comisiones, docentes, días, horarios,
contenidos y condiciones de aprobación. Como la página está renderizada con
Looker Studio, la extracción utiliza un navegador automático.

La primera vez, instala el navegador de Playwright:

```bash
python -m playwright install chromium
```

Extrae automáticamente el año y semestre actuales en Argentina, sin escribir en Supabase:

```bash
python -m rumbo_scraper.spiders.utdt_catalog
python -m rumbo_scraper.database.load_utdt_catalog
```

Para consultar un período específico, se pueden indicar ambos valores manualmente:

```bash
python -m rumbo_scraper.spiders.utdt_catalog --year 2026 --semester 2
```

Después de crear las tablas requeridas en Supabase, carga el resultado:

```bash
python -m rumbo_scraper.database.load_utdt_catalog --apply
```

El esquema SQL no se guarda en este repositorio.

## Datos pendientes

La auditoría genera un archivo con cada campo importante que sigue vacío y la
fuente recomendada para completarlo:

```bash
python -m rumbo_scraper.database.audit_completeness
```

Si existe la tabla `pendientes_datos`, se puede sincronizar el tablero de
pendientes con:

```bash
python -m rumbo_scraper.database.audit_completeness --apply
```
