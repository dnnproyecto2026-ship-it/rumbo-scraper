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

El comando consulta páginas oficiales de admisiones, información institucional, carreras y planes de estudio. Genera `data/utdt_completo.json` con las 15 secciones del contrato definido en `carga_carreras.xlsx`.

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
