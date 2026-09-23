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

## Extracción completa: Universidad Austral

```bash
python -m rumbo_scraper.spiders.austral
python -m rumbo_scraper.database.load_austral
python -m rumbo_scraper.database.load_austral --apply
```

Austral expone la API REST de WordPress, así que el catálogo llega clasificado
por la propia universidad: cada programa trae la taxonomía que dice de qué tipo
es, en qué sede se dicta y qué unidad académica lo dirige. Los cursos que el
catálogo clasifica como "Programas" quedan fuera del contrato, con su motivo.

La misma carrera se publica una vez por sede, y a veces dos veces en la misma
sede con una página de campaña. El contrato modela eso con una carrera y una
oferta por sede, así que las entradas se agrupan por nombre y la página con más
datos publicados describe el programa; `control_calidad.programas_unificados`
registra cuáles se unieron.

Los planes son cuadros en PDF cuyo texto extraído no conserva el orden visual
—los encabezados de año aparecen separados de sus materias—, así que las
materias se guardan sin año y el motivo queda en
`control_calidad.materias_sin_anio`.

## Extracción completa: UMSA

```bash
python -m rumbo_scraper.spiders.umsa
python -m rumbo_scraper.database.load_umsa
python -m rumbo_scraper.database.load_umsa --apply
```

UMSA publica su catálogo por la API REST de WordPress en dos tipos de contenido:
`carrera`, que la universidad clasifica como grado o posgrado, y `oferta`, que
reúne todo lo más corto. De las ofertas sólo una diplomatura es un posgrado del
contrato; cursos, talleres, seminarios, programas y certificaciones quedan
afuera con su motivo.

Los planes son una tabla por ciclo, con el año nombrado en palabras en grado
("PRIMER AÑO") y entre paréntesis en posgrado ("(1 AÑO)"), y una segunda columna
con el régimen de cursada.

## Extracción completa: UCA

```bash
python -m rumbo_scraper.spiders.uca
python -m rumbo_scraper.database.load_uca
python -m rumbo_scraper.database.load_uca --apply
```

El sitio de UCA renderiza del lado del cliente, así que se lee con navegador. El
recorrido sigue cómo la universidad enlaza su oferta: el hub de facultades lista
las facultades y cada facultad enlaza sus programas. El plan de estudios sólo
aparece al abrir su sección, así que cada página recibe un click.

Una página de facultad puede terminar de cargar su shell antes que sus enlaces;
por eso, si no devolvió ninguno, se le vuelve a pedir una vez. Sin ese reintento
dos corridas del mismo sitio descubrían distinta cantidad de programas.

## Extracción completa: UADE

```bash
python -m rumbo_scraper.spiders.uade
python -m rumbo_scraper.database.load_uade
python -m rumbo_scraper.database.load_uade --apply
```

El sitemap enumera todo el sitio y un programa se reconoce por lo que la propia
universidad publica de él: sólo un programa tiene una página
`/plan-de-estudios` al lado. El tipo lo declara la palabra que abre el nombre,
así que una carrera combinada como "Lic. en Administración de Empresas + MBA"
queda como grado y no como maestría.

## Extracción completa: Universidad de Belgrano

```bash
python -m rumbo_scraper.spiders.ub
python -m rumbo_scraper.database.load_ub
python -m rumbo_scraper.database.load_ub --apply
```

Belgrano publica la ficha técnica más completa de las que lleva el proyecto: una
tabla con el título final, el intermedio, los requisitos, la modalidad, la
extensión, la cantidad de materias, el turno y la acreditación de CONEAU. Los
posgrados no usan esa tabla y escriben los mismos datos en una oración, así que
se leen los dos formatos. Una página que no publica ninguno no es un programa
—es un servicio— y queda afuera con su motivo.

## Extracción completa: Universidad Tecnológica Nacional

```bash
python -m rumbo_scraper.spiders.utn
python -m rumbo_scraper.database.load_utn
python -m rumbo_scraper.database.load_utn --apply
```

La UTN es la primera de las nueve que publica su oferta como datos y no como
páginas: el buscador "Estudiar en UTN" lee un endpoint JSON público,
`/modules/mod_oferta_acad/web-oferta.php`, que devuelve el catálogo de carreras,
las facultades regionales que dictan cada una y los documentos de cada plan. No
hace falta navegador.

También es la primera cuyas facultades traen dirección y decano, así que las
sedes, las ofertas por sede y las autoridades se cargan desde la fuente en vez
de quedar bloqueadas por las columnas `NOT NULL` del esquema.

Los planes son PDF y están escritos en cuatro formatos distintos —encabezado por
nivel, número romano en la columna de nivel, columna "Año" antes del nombre y
columna "Año" después—, así que el lector es una máquina de estados sobre el
texto extraído. Cuando el año no está publicado de ninguna de las cuatro formas,
la materia queda con año nulo y el plan se reporta en
`planes_sin_anio_publicado`. Los 484 cursos de posgrado no son un título del
enum del contrato, así que quedan en el artefacto con `tipo_posgrado` nulo y
fuera de la base, reportados.

## Extracción completa: Universidad de Buenos Aires

```bash
python -m rumbo_scraper.spiders.uba
python -m rumbo_scraper.database.load_uba
python -m rumbo_scraper.database.load_uba --apply
```

La UBA publica su oferta de forma centralizada y su detalle en ningún lado:
`uba.ar/facultades` enumera las trece facultades, y la página de cada una trae
la dirección y el teléfono de sus sedes y la lista de carreras que dicta, con un
enlace al sitio de esa facultad. El plan, la duración y el título que expide
cada carrera viven en trece sitios distintos, así que este adapter lee lo que el
catálogo central publica y **declara** lo demás en vez de inventarlo.

Dos detalles del origen que el lector tiene en cuenta: la lista de carreras está
escrita con un ancla que se autocierra —`<a ... class=""/>Nombre`— así que el
nombre que sobrevive al parseo es el del atributo `alt`; y dos facultades
publican dos edificios sin decir cuál dicta cada carrera, así que esas catorce
ofertas quedan sin sede en vez de asignarles una.

Las autoridades que publica el sitio son las del Rectorado, no las de una
facultad, y `autoridades.facultad_id` es NOT NULL, así que quedan en el
artefacto y fuera de la base.

### Posgrados de la UBA

La UBA declara más de 660 posgrados y no publica ninguno de forma central: cada
facultad publica el suyo, en su propio sitio y en una de tres formas. El lector
tiene una estrategia por forma y cada fuente declara en cuál está escrita, así
que una página que cambia de forma falla a la vista en vez de devolver una lista
más corta:

| Estrategia | Forma de la página | Facultades |
|---|---|---|
| `lista` | un encabezado con el tipo y abajo los nombres | Agronomía, Económicas, Filosofía y Letras, Ingeniería |
| `titulos` | cada programa es un encabezado propio | Exactas |
| `parrafos` | los nombres son texto suelto; se descuentan las líneas que la facultad repite en sus otras páginas | FADU, Filosofía y Letras |
| `mezcla` | una sola página para toda la oferta; sólo se leen las entradas que nombran su propio tipo | Farmacia, Sociales, Veterinarias |
| `panel:<id>` | la oferta está en solapas; el tipo lo da la solapa | Odontología |
| `selector:<css>` | bajo cada nombre hay un párrafo de director y contacto, o el nombre vive en un acordeón, así que se toma del elemento que lo contiene | Derecho, Medicina |

Una página con una sección por tipo se lee una vez por tipo, y el encabezado
que abre el bloque tiene que ser el del tipo que se está pidiendo: si no, las
diplomaturas entrarían como maestrías.

Un nombre que ya dice su tipo lo conserva. Uno que empieza con "en" o "de" es
la cola del encabezado de la página —Medicina escribe "en Biología Molecular
Médica" bajo "Oferta de Maestrías"— así que el tipo lo completa en vez de
repetirlo. El resto recibe el tipo que anuncia el índice.

Un nombre que ya dice su tipo lo conserva; una página que lista nombres pelados
les presta el tipo que anuncia, igual que el catálogo de la UTN. Las ocho
facultades que publican su oferta de una forma que este lector todavía no cubre
están declaradas una por una en `posgrados_por_facultad_sin_leer`, con lo que se
interpone en cada caso.

### Planes de la UBA

Ochenta y una de las ciento veinticinco carreras enlazan su plan de estudios
desde la página de su facultad, y ese enlace queda registrado en
`recursos_publicos`. Las materias **no** se leen de ahí.

Sesenta de esos ochenta y un enlaces van a una página y veinte a un PDF. Los
que son una **tabla** se leen: una materia por fila, y la columna del nombre se
elige por cómo leen sus celdas y no por cuánto texto tienen, porque la columna
más ancha de un plan es la que lista las correlativas. Ocho carreras publican el
plan así y dan 336 materias.

Los demás no se leen, y es una decisión. El lector de `parsers/plan_documents.py`
—el mismo que lee los noventa y un planes de la UTN— aplicado a los PDF de la
UBA devuelve materias reales mezcladas con fragmentos de la prosa que las rodea
("CBC aprobado", "Facultad de Agronomía Cod", tres materias corridas en una
línea). Con un filtro que exige año en la mayoría de las materias y nombres de
largo razonable sobreviven 8 planes de 125, y ni esos quedan limpios. El resto
de las facultades publica el plan como resolución, como diagrama en imagen o
como una página que enlaza a otra parte: no hay texto que leer.

Una materia equivocada es peor que una materia faltante, así que lo que no se
puede leer queda enlazado y declarado.

## Bitácora de cobertura

```bash
python -m rumbo_scraper.bitacora
```

Genera `data/bitacora.md` leyendo los artefactos de cada adapter y los informes
de auditoría: qué tiene cada universidad, qué secciones están vacías y con qué
motivo declarado, cuántas filas traen cada campo clave y qué quedó fuera del
contrato. No contiene nada escrito a mano.

## Datos pendientes

La auditoría genera, por universidad, un archivo con cada campo importante que
sigue vacío y la fuente recomendada para completarlo:

```bash
python -m rumbo_scraper.database.audit_completeness --todas
```

Sin `--todas` audita una sola, con `--universidad "Universidad Austral"`.

El informe separa dos cosas que en la base se parecen y no son lo mismo: un
campo vacío que puede completarse desde una página pública, y un campo vacío
porque la universidad no lo publica. Lo segundo lo declara cada adapter en su
propio artefacto —`control_calidad.secciones_sin_fuente_publica` y
`materias_sin_anio`— y se reporta aparte en `no_publicado`, para que el backlog
sea la lista de trabajo que realmente se puede hacer.

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
