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

La carga usa las credenciales locales de `.env`, pero no las imprime. Esta carga
omite `turnos_anio` y `aranceles`: los turnos se derivan después desde los horarios
del catálogo semestral y los aranceles permanecen vacíos mientras no exista una
fuente oficial vigente.

## Extracción: Universidad de San Andrés

UdeSA se procesa de forma completamente algorítmica. El scraper abre las páginas
oficiales con Playwright, lee el JSON estructurado de Next.js y aplica reglas
fijas; no llama a modelos de IA, no usa prompts y no consume tokens.

```bash
python -m rumbo_scraper.spiders.udesa
python -m rumbo_scraper.database.load_udesa
```

La primera orden genera `data/udesa_completo.json`. Actualmente extrae las
carreras de grado, unidades académicas, sedes oficiales, modalidad, duración,
descripción, planes de estudio, año de cada materia, clasificaciones temáticas,
imágenes y documentos públicos. La segunda orden valida el resultado sin
escribir. Después de revisar el resumen, la carga explícita es:

```bash
python -m rumbo_scraper.database.load_udesa --apply
```

Los posgrados, docentes, becas y vida universitaria de UdeSA se incorporan por
etapas posteriores. Hasta que una fuente oficial los publique y el parser los
valide, esos campos permanecen vacíos; no se completan con inferencias.

## Directorio académico

La base de Supabase debe contar con las tablas `personas` y `roles_academicos`.
El scraper permite que una persona tenga simultáneamente varios cargos y vínculos
con facultades, carreras y materias. Cuando existe un perfil oficial de UTDT,
también completa correo, formación y biografía publicados.

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

Esta carga también deriva los turnos por carrera y año (mañana, tarde o noche)
a partir de los horarios efectivamente publicados.

El esquema SQL no se guarda en este repositorio.

## Extracción completa: ITBA

```bash
python -m rumbo_scraper.spiders.itba
python -m rumbo_scraper.database.load_itba
python -m rumbo_scraper.database.load_itba --apply
```

El sitio es WordPress: las páginas son HTML plano y el sitemap enumera los
programas y las fichas de docentes. Los nombres completos sólo aparecen en el
menú, que se renderiza con JavaScript —la página de una carrera se titula
"Civil", y el menú publica "Ing. Civil"—, así que el descubrimiento usa un
navegador y el resto del recorrido va por HTTP directo.

Once de las trece carreras publican su plan sólo en PDF, así que el scraper lo
descarga y lo lee con `pypdf`. Los documentos nombran cada año en mayúsculas y
listan las materias debajo en Title Case; una sección de electivas deja la
materia sin año, porque el documento no se lo asigna. El mismo PDF publica el
título que otorga la carrera, que la página no dice.

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

## Personas duplicadas por grafía

`personas` es única por el nombre exacto, mientras que los loaders identifican a
una persona con `comparison_key`, que ignora acentos y mayúsculas. Cuando un
loader no podía ver una fila existente, insertaba a la misma persona con la
grafía de su propia fuente. Para revisarlas y fusionarlas:

```bash
python -m rumbo_scraper.database.merge_people
```

Muestra qué fila se conserva y cuál se elimina; escribe sólo con `--apply`.
La fila que sobrevive se decide por la calidad de la evidencia —una página de la
universidad gana sobre el catálogo de terceros—, nunca por la grafía: hay casos
en que el nombre correcto es el que no lleva acento.

## Manifiesto y baseline entre corridas

Los archivos de `data/` no se versionan, así que los conteos de una corrida sólo
se pueden interpretar comparándolos con los de la anterior. El manifiesto guarda
la forma de cada artefacto —hash, tamaño y cantidad de filas por sección— sin
copiar ningún dato extraído:

```bash
python -m rumbo_scraper.manifest
```

Cada corrida estampa su propia hora, así que el hash del archivo cambia siempre
y no dice nada. Por eso el manifiesto guarda además un hash de contenido que
ignora los campos volátiles: si los conteos se mantienen pero ese hash cambia,
algo del dato se movió y conviene mirarlo.

Por defecto sólo muestra la vista previa y la compara contra el último baseline
de `manifests/`. Para guardar la corrida actual como nuevo baseline:

```bash
python -m rumbo_scraper.manifest --write
```

Con `--max-drop` la comparación deja de ser informativa y pasa a fallar cuando
una sección se desploma, lo que permite frenar una publicación degradada:

```bash
python -m rumbo_scraper.manifest --max-drop 0.2
```

Devuelve `2` si alguna sección cae más que el umbral. Conviene ejecutarlo entre
el spider y el loader, antes de cualquier `--apply`.

## Validación de fuentes

Toda URL publicada en el contrato debe pertenecer al dominio oficial de la
universidad y usar HTTPS. La comprobación exige que el host sea el dominio o un
subdominio suyo: `utdt.edu.otro-sitio.com` y `https://cualquiera.com/?ref=utdt.edu`
se rechazan, porque de lo contrario un enlace ajeno podría quedar guardado como
evidencia oficial. Un campo vacío sigue siendo válido: significa que la fuente no
lo publica.
