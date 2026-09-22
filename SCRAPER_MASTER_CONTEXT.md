# SCRAPER MASTER CONTEXT — Rumbo

> Documento maestro de continuidad técnica, memoria de decisiones y especificación del pipeline de datos universitarios.
>
> **Fecha de corte:** 22 de septiembre de 2026, zona horaria America/Argentina/Buenos_Aires.  
> **Repositorio:** `https://github.com/dnnproyecto2026-ship-it/rumbo-scraper`  
> **Rama:** `main`  
> **Último commit analizado:** `b695194 Add deterministic UdeSA degree scraper`  
> **Regla de lectura:** `CONFIRMADO` significa comprobado en el código, una ejecución o Supabase; `INFERIDO` significa deducido de evidencia; `HIPÓTESIS` no fue validada; `PENDIENTE` requiere trabajo; `NO DEFINIDO` nunca se cerró; `DESCARTADO` fue considerado y abandonado.

> **Límite de reproducibilidad:** los conteos de JSON corresponden a snapshots locales ignorados por Git y los conteos de Supabase a una consulta puntual del 22-09-2026. No existe todavía un `run_id` común, manifiesto de hashes ni snapshot versionado que demuestre que ambos conjuntos provienen de una única corrida. Por eso se distinguen explícitamente y no deben sumarse como si fueran una fotografía atómica.

---

# 1. Resumen ejecutivo del proyecto

## Qué se está construyendo

`rumbo-scraper` es el pipeline de recolección, normalización, validación y carga de información pública de universidades para Rumbo, una plataforma EdTech que busca ayudar a estudiantes a descubrir, explorar, comparar y decidir qué y dónde estudiar.

El scraper no es sólo un listado de carreras. El contrato cubre instituciones, localidades, sedes, unidades académicas, carreras, ofertas por sede, turnos, ciclos de ingreso, aranceles, áreas temáticas, materias, posgrados, actividades, autoridades, contactos, becas, servicios, vida extracurricular, alojamiento e internacionalización. Además existe una capa específica para catálogo semestral, comisiones, horarios y docentes.

## Problema que resuelve

La información universitaria está distribuida entre páginas institucionales, páginas de carreras, planes de estudio, perfiles académicos, mapas, documentos y aplicaciones dinámicas. Cada universidad usa estructuras y vocabulario diferentes. Rumbo necesita transformarlos en un esquema comparable y auditable sin completar huecos con datos inventados.

## Usuario final y resultado esperado

- **Usuario de datos:** la aplicación Rumbo y sus desarrolladores.
- **Usuario final indirecto:** estudiantes que comparan universidades y programas.
- **Resultado esperado:** Supabase contiene entidades normalizadas, con vínculos estables y datos que puedan alimentar perfiles, filtros, comparaciones y recomendaciones.
- **Restricción principal confirmada:** el scraping y la normalización deben ser algorítmicos, determinísticos y sin llamadas a IA ni consumo de tokens.

## Estado actual

### UTDT — funcionando en el Supabase compartido

Conteos verificados en Supabase al 22-09-2026:

| Entidad | Registros |
|---|---:|
| Sedes | 1 |
| Facultades/unidades | 11 |
| Carreras | 13 |
| Ofertas académicas | 13 |
| Materias de planes, incluidas materias de posgrado | 829 |
| Posgrados | 28 |
| Materias del catálogo semestral | 299 |
| Turnos derivados | 99 |
| Personas totales, incluidos docentes del catálogo | 1.475 |
| Roles académicos estructurados | 688 |
| Becas | 6 |
| Servicios estudiantiles | 8 |
| Actividades extracurriculares | 32 |
| Alojamientos/apoyos | 3 |
| Programas internacionales | 5 |
| Convenios de intercambio por programa | 671 |

El último archivo principal contiene 13 carreras, 829 materias, 28 posgrados, 12 actividades, 17 autoridades, 632 personas del directorio académico y 688 roles. Supabase devolvió 1.475 filas de personas al consultar el entorno compartido. Esa cifra incluye docentes del catálogo y puede incluir nueve filas históricas no observadas en los artefactos actuales: 632 personas del directorio + 960 docentes únicos − 126 solapamientos = 1.466 identidades locales. El loader hace upsert, pero todavía no inactiva personas ausentes.

### UdeSA — núcleo de grado funcionando y cargado

| Entidad | Registros |
|---|---:|
| Localidades | 3 |
| Sedes | 4 |
| Unidades académicas | 8 |
| Carreras | 18 |
| Ofertas por sede | 31 |
| Materias | 681 |
| Recursos públicos detectados | 53 |

Las 53 imágenes, documentos y enlaces están en `data/udesa_completo.json`, pero **PENDIENTE:** no se persisten en Supabase porque el loader actual sólo carga el núcleo académico y no existe en este repositorio una migración de recursos.

## Grado de avance aproximado

- **CONFIRMADO:** UTDT tiene cobertura amplia de grado, posgrado, docentes, vida universitaria, intercambios y catálogo.
- **CONFIRMADO:** UdeSA tiene cobertura de las 18 carreras configuradas y verificadas al corte. **PENDIENTE:** comparar automáticamente la navegación oficial con `CAREERS` para detectar nuevas carreras o bajas; hoy el validador contrasta contra la misma configuración.
- **PENDIENTE:** ampliar UdeSA a posgrados, docentes, autoridades, becas, servicios, alojamiento e intercambios.
- **PENDIENTE:** aranceles verificables y fechas precisas siguen siendo el principal hueco transversal.
- **NO DEFINIDO:** no existe todavía un porcentaje único de “avance total nacional”, porque sólo se trabajó en dos universidades y el alcance final de instituciones no fue cerrado.

## Principal cuello de botella

El cuello de botella no es descargar HTML: es conseguir fuentes públicas, vigentes y semánticamente inequívocas para campos sensibles o variables en el tiempo —aranceles, fechas, cupos, títulos oficiales, correlatividades y detalles de materias— sin inferir ni inventar.

---

# 2. Origen del proyecto

## Necesidad inicial

La conversación comenzó buscando repositorios de scraping que pudieran recorrer sitios universitarios y obtener datos públicos. Se analizaron proyectos orientados a programas, cursos y faculty, entre ellos:

- `ANU-Programs-and-Courses-Scraper`;
- `Scraping-Degree-Programs`;
- `keefeeilish/scrappy`;
- `Vaporjawn/universities`;
- `OpenCourseAPI/OpenCourseAPI`;
- `higgsAT/tiss-crawler`;
- Scrapy como motor general.

La idea inicial fue tomar patrones útiles: crawler, adaptadores por universidad, schema canónico y conservación de HTML/raw. Se descartó mezclar repositorios completos porque generaría una base difícil de mantener.

## Evolución del criterio técnico

1. **Decisión inicial:** Scrapy como columna vertebral; Playwright para JavaScript; Pydantic para schema; LLM sólo para ambigüedades.
2. **Cambio solicitado por el usuario:** el scraper debía ser 100% algorítmico, sin IA y sin tokens.
3. **Decisión final implementada:** adaptadores determinísticos por universidad, HTML/JSON oficial, expresiones regulares, reglas explícitas, validadores y `null` ante ausencia.
4. **Estado real:** el repositorio no contiene cliente de OpenAI, prompts ni dependencia LLM. Tampoco usa Scrapy todavía: la implementación efectiva usa `httpx`, BeautifulSoup y Playwright.

## Evolución del modelo de datos

La planilla `carga_carreras.xlsx` se tomó como contrato de salida. Al principio se planteó un SQL simplificado; luego se revisó el Excel pestaña por pestaña y se concluyó que el modelo debía conservar ofertas por sede, turnos por año, historial de ciclos y aranceles, materias, posgrados, actividades, autoridades y contactos. Después se sumaron becas, servicios estudiantiles, extracurriculares, alojamiento, programas internacionales y convenios.

## Universidad piloto

UTDT se eligió como piloto porque había datos de referencia y páginas públicas comparables. El avance fue incremental:

1. 13 carreras y estructura básica.
2. 256 materias iniciales.
3. 23 posgrados descubiertos inicialmente; luego 28.
4. 632 personas académicas y 688 roles.
5. Becas, servicios, extracurriculares, alojamiento e internacionalización.
6. 671 convenios de intercambio por programa.
7. Catálogo dinámico de cursos: 2.248 filas de horarios y 616 filas de contenidos.
8. Enriquecimiento de títulos, modalidades, duraciones, descripciones y planes de posgrado.
9. Ampliación de planes hasta 829 materias totales.

UdeSA fue la segunda universidad para demostrar replicabilidad sin IA.

---

# 3. Alcance actual

## Incluido actualmente

- Extracción desde sitios oficiales públicos de UTDT y UdeSA.
- Descarga HTML con `httpx` cuando la fuente lo permite.
- Navegación headless con Playwright cuando la fuente es dinámica o bloquea HTTP simple.
- Parseo de JSON estructurado Next.js de UdeSA.
- Parseo de Looker Studio para el catálogo semestral UTDT.
- Normalización de texto, URLs de Supabase, nombres de personas, materias y modalidades.
- Validación de forma, conteos críticos, relaciones internas y comprobaciones básicas de dominio. **Limitación conocida:** las validaciones de host actuales son demasiado permisivas y aún no verifican de modo uniforme HTTPS ni el destino final de redirects.
- Exportación JSON local ignorada por Git.
- Vista previa sin escritura y carga explícita con `--apply`.
- Upserts idempotentes de entidades estables.
- Sincronización de materias preservando IDs ya vinculados al catálogo.
- Auditoría de completitud UTDT y sincronización opcional de `pendientes_datos`.
- Lectura de `.env` local; compatibilidad con `SUPABASE_SECRET_KEY` y `SUPABASE_SERVICE_ROLE_KEY`.
- Pruebas unitarias: 35 tests, todos aprobados al corte.

## Posible expansión futura

- Completar toda la cobertura UdeSA.
- Agregar ITBA, UTN, UBA, UADE, UCA, Austral y otras universidades argentinas.
- Extraer PDF de planes, programas y resoluciones.
- Automatizar ejecuciones con GitHub Actions y GitHub Secrets.
- Incorporar change detection, versionado de fuentes y snapshots raw.
- Extender auditoría a todas las universidades.
- Agregar recursos multimedia/documentales a Supabase.
- Incorporar correlatividades, requisitos de admisión detallados y resultados académicos/laborales si existen fuentes comparables.
- Escalar a otros países mediante adapters y contratos por jurisdicción.

## Fuera de alcance o pospuesto

- **DESCARTADO:** guardar SQL de Supabase dentro de `rumbo-scraper`. El commit `5b2f286` lo agregó y `c89842a` lo eliminó expresamente. Las migraciones se administran fuera del repo.
- **DESCARTADO:** usar Vercel como entorno del scraper. Vercel queda para la app; el scraper usa local/GitHub Actions.
- **DESCARTADO:** usar la clave pública/publishable para escribir. El scraper requiere secret/service role local o en GitHub Secrets.
- **DESCARTADO:** completar campos no publicados mediante IA o imaginación.
- **DESCARTADO por pedido del usuario:** clasificación de carreras mediante Artículo 43/46 como eje del producto. El campo `es_art_43` existió en el SQL conversado, pero fue eliminado del contrato Python vigente.
- **PENDIENTE, no descartado:** descripciones por materia cuando una fuente pública las ofrece.
- **NO DEFINIDO:** reviews, rankings, aceptación, graduación o salarios; fueron discutidos como producto futuro, no implementados por el scraper.

---

# 4. Fuentes de datos

## 4.1 Universidad Torcuato Di Tella — sitio institucional

**Dominio:** `https://www.utdt.edu`  
**Tipo:** HTML mayormente estático, con múltiples páginas y parámetros `id_contenido` / `id_item_menu`.  
**Login:** no requerido para las páginas usadas.  
**Paginación:** depende de la sección; el spider principal trabaja con URLs conocidas y URLs descubiertas.  
**robots.txt/restricciones:** **NO DEFINIDO** en la conversación; el crawler usa un User-Agent identificable y contenido público.

Fuentes principales codificadas:

| Uso | URL |
|---|---|
| Listado/admisiones de grado | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=359` |
| Información institucional | `https://www.utdt.edu/ver_contenido.php?id_contenido=1006&id_item_menu=140` |
| Autoridades | `https://www.utdt.edu/autoridades/listado_contenidos.php?id_item_menu=26532` |
| Servicios | `https://www.utdt.edu/ver_contenido.php?id_contenido=1239&id_item_menu=386` |
| Becas | `https://www.utdt.edu/admisiones/becas/listado_contenidos.php?id_item_menu=423` |
| Deportes | `https://www.utdt.edu/deportes` |
| Organizaciones estudiantiles | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=356` |
| Primer año | `https://www.utdt.edu/ver_contenido.php?id_contenido=9731&id_item_menu=19136` |
| Bienestar | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=19142` |
| Orientación | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=19139` |
| Centro de estudiantes | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=19157` |
| Acción social | `https://www.utdt.edu/listado_contenidos.php?id_item_menu=4607` |
| Alojamiento | `https://www.utdt.edu/ver_contenido.php?id_contenido=27151&id_item_menu=44632` |
| Internacional | `https://www.utdt.edu/ver_contenido.php?id_contenido=9949&id_item_menu=19550` |
| Mapa de intercambio | `https://www.utdt.edu/map_international` |
| Posgrados | `https://www.utdt.edu/posgrados` |
| Admisión de grado | `https://www.utdt.edu/admisiones/grado` |

**Datos obtenibles:** institución, contactos, 13 carreras, planes, títulos, duración, modalidad, descripciones, pasantías/bolsa cuando se publican, unidades académicas, autoridades, profesores y perfiles, posgrados, becas, servicios, actividades, alojamiento, programas y destinos internacionales.

**Problemas encontrados:** enlaces internos obsoletos (404), una URL con error 500, variaciones de maquetado y nombres, información de posgrado fragmentada entre página principal y suplementos. El último JSON registra seis errores de descarga sin impedir completar el dataset.

**Calidad estimada:** alta para entidades y URLs verificadas; variable para campos no publicados o con semántica implícita.

## 4.2 Catálogo semestral UTDT — Looker Studio

**URL:** `https://datastudio.google.com/reporting/30c8c711-0f14-462a-a825-fb5fe501bc1d/page/hAzCD`  
**Tipo:** aplicación dinámica JavaScript/Looker Studio.  
**Login:** la ejecución probada accedió públicamente.  
**Paginación:** sí; tablas virtualizadas con botones y scroll interno.  
**Buscador/filtros:** la página puede tener controles, pero el scraper identifica tablas por encabezados exactos.  
**Herramienta:** Playwright headless.

Tablas detectadas:

- `MATERIA`, `SECCIÓN`, `CLASE`, `DOCENTES`, `DÍA`, `HORARIO`.
- `CURSO`, `CONTENIDO`, `CONDICIONES DE APROBACIÓN`, `LINK`.

Última extracción local: 2.248 filas de horarios, 616 filas de contenidos, 0 horarios sin código, 25 detalles sin contenido y 316 sin condiciones de aprobación.

**Limitaciones:** el catálogo describe oferta semestral, no el plan completo. Una materia del plan puede no aparecer ese semestre. Por eso una falta de vínculo no se considera automáticamente error del scraper.

## 4.3 Universidad de San Andrés — sitio Next.js

**Dominio:** `https://udesa.edu.ar`  
**Fuente inicial:** `https://udesa.edu.ar/estudia-en-udesa`  
**Tipo:** Next.js con `#__NEXT_DATA__` y contenido renderizado.  
**HTTP simple:** respondió 403 en pruebas.  
**Fallback implementado:** Playwright carga la página, lee el JSON oficial y no depende de visión ni IA.  
**Login:** no requerido.  
**Paginación:** no para las carreras y planes usados.  
**robots.txt/restricciones:** **NO DEFINIDO**; sólo se usan páginas públicas.

**Datos obtenidos:** 18 carreras, attendance estructurado (`Duración`, `Sede`, `Modalidad`, `Inicio`), descripción, imagen, navegación a plan, tablas de syllabus por año/semestre, clasificaciones temáticas y adjuntos.

**Estrategia:** existe una lista explícita de 18 carreras para evitar que un cambio de menú convierta enlaces ajenos en programas. Cada página se valida contra el nombre esperado. Se ejecutan hasta cuatro navegaciones simultáneas mediante semáforo.

## 4.4 UdeSA — sedes de Educación Ejecutiva

**URL:** `https://exed.udesa.edu.ar/sedes/`  
**Tipo:** HTML estático accesible con `httpx`.  
**Datos obtenidos:** Campus Victoria, Sede Callao, Sede Nordelta y Sede Riobamba; dirección, código postal, localidad y teléfono visible.

El esquema de Supabase no acepta el enum literal `Sede`; sólo `Campus`, `Edificio único`, `Anexo`, `Otro`. Se conserva el nombre oficial y las sedes satélite se clasifican como `Otro` para no afirmar que son anexos.

## 4.5 Excel maestro

**Archivo mencionado:** `carga_carreras.xlsx`.  
**Rol:** contrato funcional inicial y referencia para las secciones.  
**Estado:** sus columnas fueron trasladadas a `rumbo_scraper/contracts.py`; el archivo no forma parte del repo actual.

## 4.6 Supabase

**Rol:** base PostgreSQL normalizada y destino de carga.  
**Acceso del scraper:** URL base + secret/service-role key desde `.env`.  
**Acceso de frontend:** se planteó anon/authenticated con RLS de lectura; las políticas no están versionadas en este repo.  
**Tablas técnicas discutidas:** `scrape_runs`, `paginas_web`, `scrape_raw`, `fuentes_datos`, `scrape_errors`. Su uso efectivo por los loaders actuales es **PENDIENTE/NO CONFIRMADO**.

---

# 5. Flujo completo del scraper

| Paso | Input | Proceso | Output | Error/fallback | Estado |
|---|---|---|---|---|---|
| 1. Configuración | `.env` | valida URL base y secret | cliente Supabase | error claro si faltan variables | Implementado |
| 2. Catálogo de fuentes | constantes/adapters | define URLs y programas esperados | conjunto controlado de URLs | no descubre todo el dominio libremente | Implementado por universidad |
| 3. Descarga | URL | `httpx` o Playwright | HTML/Next JSON | registra `errores_descarga`; continúa cuando es seguro | Implementado |
| 4. Descubrimiento | índice/página de carrera | encuentra detalle, plan, suplementos, perfil | URLs derivadas | comprobación actual de dominio; pendiente endurecer host/HTTPS/redirect | Parcial |
| 5. Parseo | HTML/JSON/tablas | selectores, encabezados, regex y reglas | registros intermedios | `None` ante ausencia | Implementado |
| 6. Normalización | texto fuente | espacios, acentos para comparación, nombres, modalidad, duración | valores canónicos | conserva texto publicado cuando no existe enum seguro | Implementado parcial |
| 7. Construcción | registros | `blank_record` completa todas las columnas | JSON con 21 secciones | rechaza campos desconocidos | Implementado |
| 8. Validación | dataset | forma, conteos, duplicados, referencias, dominio | dataset válido o excepción | detiene antes de escribir | Implementado |
| 9. Exportación | dataset | JSON UTF-8 indentado | archivo en `data/` | carpeta creada automáticamente | Implementado |
| 10. Preview | JSON | valida y cuenta | resumen sin DB | no carga `.env` en loaders que lo permiten | Implementado |
| 11. Persistencia | JSON validado | upsert/insert por chunks | Supabase | carga sólo con `--apply` | Implementado |
| 12. Vinculación catálogo | plan + catálogo | nombre exacto/equivalencia segura | links con método/confianza | ambiguos quedan sin vínculo | Implementado UTDT |
| 13. Auditoría | Supabase | reglas de faltantes | `utdt_pendientes.json` | puede sincronizar `pendientes_datos` | Implementado UTDT |

## Comandos operativos

```bash
cd ~/Desktop/rumbo-scraper
source .venv/bin/activate

# UTDT principal
python -m rumbo_scraper.spiders.utdt
python -m rumbo_scraper.database.load_utdt
python -m rumbo_scraper.database.load_utdt --apply

# UTDT catálogo semestral; período actual de Argentina por defecto
python -m rumbo_scraper.spiders.utdt_catalog
python -m rumbo_scraper.database.load_utdt_catalog
python -m rumbo_scraper.database.load_utdt_catalog --apply

# Auditoría UTDT
python -m rumbo_scraper.database.audit_completeness
python -m rumbo_scraper.database.audit_completeness --apply

# UdeSA grado
python -m rumbo_scraper.spiders.udesa
python -m rumbo_scraper.database.load_udesa
python -m rumbo_scraper.database.load_udesa --apply

# Tests
python -m unittest discover -v
```

---

# 6. Arquitectura técnica

## Arquitectura actual

```text
fuentes oficiales
  ├─ HTML estático ───────────────► httpx
  ├─ Next.js / #__NEXT_DATA__ ───► Playwright
  └─ Looker Studio ───────────────► Playwright + DOM
                                         │
                                         ▼
parsers por universidad/fuente
                                         │
                                         ▼
normalizadores + contrato de 21 secciones
                                         │
                                         ▼
validadores ──► JSON local ──► preview ──► loader --apply ──► Supabase
                                         │
                                         └─► auditoría de faltantes
```

### Lenguaje y dependencias

- Python 3.11+; ejecución observada con Python 3.13.
- `beautifulsoup4>=4.12,<5`.
- `httpx>=0.27,<1`.
- `playwright>=1.48,<2`.
- `python-dotenv>=1.0,<2`.
- `supabase>=2.0,<3`.

### Estructura actual

```text
rumbo_scraper/
├── contracts.py
├── settings.py
├── database/
│   ├── supabase.py
│   ├── load_utdt.py
│   ├── load_utdt_catalog.py
│   ├── load_udesa.py
│   └── audit_completeness.py
├── parsers/
│   ├── utdt.py
│   ├── utdt_catalog.py
│   └── udesa.py
├── spiders/
│   ├── utdt.py
│   ├── utdt_catalog.py
│   └── udesa.py
├── normalizers/
│   ├── text.py
│   └── url.py
└── validators/
    ├── utdt.py
    └── udesa.py
tests/
```

## Arquitectura propuesta originalmente

Se propusieron Scrapy, `scrapy-playwright`, Pydantic, un crawler genérico, clasificación de páginas, raw storage y eventualmente LLM. **Estado:** Scrapy/Pydantic/raw pipeline no están implementados; LLM fue descartado por requisito explícito.

## Arquitectura futura para escalar

Mantener adapters determinísticos por fuente, pero separar:

1. descubrimiento de URLs;
2. captura versionada;
3. parseo puro y reproducible;
4. normalización;
5. validación;
6. publicación;
7. auditoría/diff.

El salto de escala requiere cola de trabajos, límites por dominio, reintentos con backoff, caché de respuestas, snapshots, métricas, ejecución incremental y un registro de versiones de parser. No requiere IA para funcionar.

---

# 7. Modelo de datos

El contrato vigente está en `rumbo_scraper/contracts.py`. `blank_record(section, **values)` garantiza que cada fila tenga exactamente las columnas del contrato y rechaza nombres desconocidos. En JSON, un campo no publicado se representa como `null`; una sección sin datos es `[]`.

Convenciones de las tablas siguientes:

- **Req.**: obligatorio conceptual para identificar la entidad, no necesariamente restricción SQL.
- **Fuente/método:** fuente predominante; puede variar por universidad.
- **Estado:** `I` implementado, `P` parcial, `N` no resuelto.

## 7.1 Localidades

| Campo técnico | Descripción y ejemplo | Tipo / Req. | Fuente y extracción | Normalización / validación | Estado |
|---|---|---|---|---|---|
| `nombre_localidad` | Ciudad/localidad; `Victoria` | text / sí | dirección oficial; texto/regex | nombre legible; clave con provincia | I |
| `provincia` | Jurisdicción; `Buenos Aires`, `CABA` | text / sí | dirección oficial | `Pcia. de Bs. As.` → `Buenos Aires` | I |
| `codigo_postal` | Código postal; `B1644BID` | text / no | dirección oficial; regex entre paréntesis | conservar alfanumérico | I |

## 7.2 Universidades

| Campo | Descripción / ejemplo | Tipo / Req. | Fuente/método | Normalización/validación | Estado |
|---|---|---|---|---|---|
| `nombre_oficial` | `Universidad Torcuato Di Tella` | text / sí | configuración verificada + sitio oficial | nombre canónico; unique | I |
| `nombre_corto` | `UTDT`, `UdeSA` | text / no | sitio/configuración | sigla estable | I |
| `tipo_gestion` | `Privada` | enum / no | información institucional verificada | `Estatal` o `Privada` | I |
| `anio_fundacion` | `1991` para UTDT | integer / no | institucional | rango razonable desde 1000 | P; UdeSA nulo |
| `sitio_web` | URL base oficial | URL / sí | configuración | HTTPS/base | I |
| `telefono_area` | `54 11` | text / no | contacto oficial | separado del número | P |
| `telefono_numero` | `5169 7000` | text / no | contacto oficial | preservar extensiones/formato | P |
| `mail_contacto` | `admisiones@utdt.edu` | email / no | contacto/admisiones | minúsculas deseables | P |
| `instagram` | URL/usuario oficial | text/URL / no | links oficiales | canal reconocido | P |
| `tiktok` | URL/usuario oficial | text/URL / no | links oficiales | canal reconocido | P |
| `linkedin` | URL oficial | URL / no | links oficiales | dominio/plataforma | P |
| `twitter` | URL/usuario X/Twitter | text/URL / no | links oficiales | conserva compatibilidad `twitter` | P |
| `facebook` | URL oficial | URL / no | links oficiales | dominio/plataforma | P |
| `youtube` | URL oficial | URL / no | links oficiales | dominio/plataforma | P |

## 7.3 Sedes

| Campo | Descripción / ejemplo | Tipo / Req. | Fuente/método | Normalización/validación | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | Universidad propietaria | text / sí | contexto del adapter | debe existir | I |
| `nombre_sede` | `Campus Victoria` | text / sí | encabezado oficial | unique por universidad | I |
| `localidad` | referencia `Victoria — Buenos Aires` | text/ref / no | dirección | se resuelve a `localidad_id` | I |
| `calle` | `Vito Dumas` | text / no | dirección; regex | separar número | I |
| `numero` | `284` | text / no | dirección; regex | text para admitir formatos | I |
| `tipo_sede` | `Campus` u `Otro` | enum / no | nombre/tipo publicado + enum DB | enum: Campus, Edificio único, Anexo, Otro | I |

## 7.4 Facultades/unidades

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización/validación | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | Institución | text / sí | contexto | FK lógica | I |
| `nombre_facultad` | `Derecho`, `Ingeniería` | text / sí | institucional/ruta | quitar prefijo sólo al cargar | I |
| `tipo_unidad` | Escuela, Departamento, Centro | text / no | encabezado/ruta/config | vocabulario publicado | I |
| `sede` | referencia de sede | text/ref / no | oferta/institucional | relación N:M en DB | P; UdeSA null en JSON, loader deriva |

## 7.5 Carreras

| Campo | Descripción / ejemplo | Tipo / Req. | Fuente/método | Normalización/validación | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | Institución | text / sí | contexto | canónico | I |
| `facultad_nombre` | unidad responsable | text/ref / no | configuración/ruta | prefijo `Universidad — Tipo de Unidad` | I |
| `nombre_carrera` | nombre de exhibición | text / sí | página oficial | unique por universidad | I |
| `denominacion_canonica` | nombre comparable | text / no | configuración verificada | aliases seguros | I |
| `nivel` | `Grado` | enum / sí | tipo de sección | Pregrado/Grado/Posgrado | I |
| `titulo_otorgado` | `Abogado`, `Licenciado...` | text / no | plan/página/resolución | nunca derivar sólo del marketing | P; UdeSA nulo |
| `tiene_titulo_intermedio` | existencia de título intermedio | boolean / no | plan oficial | sí/no/true/false normalizados | N en datasets actuales |
| `duracion_anios` | `4`, `5` | numeric / no | etiqueta/plan; regex | años decimal | I |
| `descripcion_breve` | descripción oficial | text / no | meta/header/contenido | limpia HTML; no genera copy | I |
| `cantidad_materias_total` | total del plan extraído | integer / no | conteo de materias | >=0; derivado | I |

`es_art_43` fue parte del Excel/SQL inicial, pero **DESCARTADO del contrato vigente** a pedido del usuario.

## 7.6 Ofertas académicas

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización/validación | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I |
| `facultad_nombre` | unidad | text/ref / no | carrera/config | FK lógica | I |
| `carrera_nombre` | carrera | text/ref / sí | carrera | debe existir | I |
| `sede` | sede concreta | text/ref / sí | etiqueta publicada | UdeSA divide etiquetas multi-sede verificadas | I |
| `modalidad` | Presencial/Virtual/Híbrida | enum / no | etiqueta/texto | detector explícito | I |
| `regimen_ingreso` | forma de ingreso | text / no | admisiones/FAQ | UTDT: ingreso directo o curso | P |
| `coneau_resolucion` | número de resolución | text / no | CONEAU/página | no extraído | N |
| `coneau_vigencia_hasta` | vigencia | date / no | resolución | ISO date | N |
| `tiene_pasantias` | disponibilidad | boolean / no | detalle de carrera | sólo afirmación explícita | P |
| `tiene_bolsa_trabajo` | bolsa/desarrollo profesional | boolean / no | detalle/servicio | sólo afirmación explícita | P |
| `url_oficial` | página de oferta | URL / sí | navegación | dominio oficial | I |

## 7.7 Turnos por año

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I en contrato |
| `carrera_nombre` | carrera | text/ref / sí | vínculo materia-plan-catálogo | exacto/equivalente seguro | I UTDT |
| `sede` | sede de oferta | text/ref / sí | oferta | FK | I UTDT |
| `anio_carrera` | año del plan | integer / sí | materia vinculada | entero | I UTDT |
| `turno` | Mañana/Tarde/Noche | enum / sí | hora de inicio | <13, 13–17:59, >=18 | I UTDT |

La sección `turnos_anio` del JSON principal UTDT sigue vacía; los 99 registros se derivan y escriben durante `load_utdt_catalog --apply`.

## 7.8 Ofertas por ciclo

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I UTDT |
| `carrera_nombre` | carrera | text/ref / sí | oferta | FK | I UTDT |
| `sede` | sede | text/ref / sí | oferta | FK | I UTDT |
| `ciclo_anio` | año de ingreso | integer / sí | texto `marzo AAAA` | 4 dígitos | I UTDT |
| `ciclo_nombre` | `Ingreso 2027` | text / sí | derivado del año | formato estable | I UTDT |
| `cupo_ingresantes` | cupo | integer / no | admisiones | no publicado | N |
| `fecha_apertura_inscripcion` | apertura | date / no | calendario | ISO date | N |
| `fecha_cierre_inscripcion` | cierre | date / no | calendario | ISO date | N |
| `estado` | Abierta/Cerrada/Suspendida | enum / no | presencia de solicitud | regla explícita | P |

## 7.9 Aranceles

| Campo | Descripción | Tipo / Req. | Fuente propuesta | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | N sin filas |
| `carrera_nombre` | carrera | text/ref / sí | tabla/arancel oficial | FK | N |
| `sede` | sede | text/ref / sí | arancel/oferta | FK | N |
| `vigencia_desde` | inicio de vigencia | date / sí | documento vigente | ISO date; histórico | N |
| `monto_mensual` | cuota | numeric / no | arancel oficial | decimal sin símbolo | N |
| `monto_matricula` | matrícula | numeric / no | arancel oficial | decimal | N |
| `moneda` | ARS/USD | enum / no | documento | enum | N |
| `motivo_cambio` | explicación/versionado | text / no | evento de actualización | no pisar historia | N |

## 7.10 Áreas temáticas

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I |
| `facultad_nombre` | unidad | text/ref / no | carrera | FK | I |
| `carrera_nombre` | carrera | text/ref / sí | plan | FK | I |
| `area_tematica` | categoría | text/ref / sí | UTDT: keywords; UdeSA: referencias por color | vocabulario consistente por fuente | I/P |
| `cantidad_materias` | cantidad en el plan | integer / sí | `Counter` | derivado, no dato manual | I |

## 7.11 Materias

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I |
| `carrera_o_programa` | carrera o posgrado padre | text/ref / sí | plan | resuelve `carrera_id` o `posgrado_id` | I |
| `nombre_materia` | denominación | text / sí | plan/syllabus | limpia espacios; preserva nombre | I |
| `anio_cursada` | año | integer / no | encabezado/celda | entero; posgrados pueden no tenerlo | P |
| `turno` | turno de la materia | enum / no | catálogo | no se almacena en plan principal | P/N |
| `area_tematica` | clasificación | text/ref / no | keywords o color/referencia | verificable | I |
| `descripcion_breve` | contenido/resumen | text / no | catálogo/detalle | hoy vive principalmente en comisión | P |
| `regimen` | anual/semestral/cuatrimestral | text / no | estructura del plan | UdeSA `Semestral` | P |
| `carga_horaria_semanal` | horas semanales | numeric / no | programa/plan | no resuelta | N |

## 7.12 Posgrados

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I UTDT |
| `facultad_nombre` | unidad | text/ref / no | sección/ruta | aliases de unidades | I UTDT |
| `nombre_programa` | posgrado | text / sí | índice | separa títulos combinados | I UTDT |
| `tipo_posgrado` | Diplomatura/Especialización/Maestría/Doctorado | enum / sí | nombre | enum | I |
| `titulo_otorgado` | título oficial | text / no | detalle/plan/resolución | no inferir del nombre | P: 14/28 UTDT |
| `sede` | sede | text/ref / no | programa | UTDT campus | I UTDT |
| `modalidad` | formato | enum / no | detalle/suplementos | Presencial/Virtual/Híbrida | P: 22/28 |
| `duracion_meses` | duración normalizada | integer / no | texto; regex de meses/años/cuatrimestres | convierte a meses | P: 22/28 |
| `requiere_tesis_trabajo_final` | requisito final | boolean / no | detalle/plan | expresiones explícitas | P: 26/28 |
| `requisito_titulo_previo` | admisión | text / no | sección requisitos | texto oficial | P: 26/28 |
| `cohorte_inicio` | inicio próximo | text/date / no | detalle | conserva texto si no es fecha inequívoca | P: 2/28 |
| `costo_total_programa` | costo | numeric / no | arancel oficial | no publicado | N |
| `moneda` | ARS/USD | enum / no | junto con costo | nulo si no hay costo | N |
| `descripcion_breve` | descripción | text / no | página relevante | filtro de relevancia por programa | I: 28/28 |
| `url_oficial` | página | URL / sí | índice/descubrimiento | dominio oficial | I |

## 7.13 Actividades académicas

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I UTDT |
| `carrera_o_programa` | padre | text/ref / sí | materia detectada | FK | I |
| `tipo_actividad` | práctica, tesis, seminario, taller, etc. | text/enum / sí | keywords en materia | lista controlada conceptual | I |
| `nombre_actividad` | nombre publicado | text / sí | plan | limpio | I |
| `obligatoria` | obligatoriedad | boolean / no | plan/reglamento | no inferir por presencia | N |
| `carga_horaria_total` | horas | numeric / no | plan/reglamento | no resuelta | N |
| `descripcion_breve` | explicación | text / no | página/plan | no resuelta | N |

## 7.14 Autoridades

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `facultad_nombre` | unidad | text/ref / sí | sección de autoridades | mapa de encabezados | I UTDT |
| `carrera` | carrera si aplica | text/ref / no | detalle de carrera | null para decanos de facultad | P |
| `cargo` | Decano, decano ejecutivo, director/a | text / sí | etiqueta publicada | conserva variantes | I |
| `tipo` | académico/administrativo | text / no | cargo/contexto | permite múltiples tipos | I/P |
| `nombre_autoridad` | persona | text / sí | texto/strong | nombre canónico | I |

## 7.15 Redes y contactos

| Campo | Descripción | Tipo / Req. | Fuente/método | Normalización | Estado |
|---|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | canónico | I UTDT |
| `facultad_nombre` | unidad opcional | text/ref / no | contexto | null para institucional | P |
| `canal` | Email, Instagram, etc. | enum/text / sí | link/tipo | canal controlado | I |
| `usuario_o_direccion` | URL, usuario, email o teléfono | text / sí | atributo/texto | según canal | I |

## 7.16 Becas

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `nombre_beca` | nombre oficial | text / sí | encabezado/tarjeta | I |
| `nivel` | grado/posgrado | text / no | sección | I |
| `tipo_beca` | mérito, necesidad, etc. | text / no | texto | I/P |
| `cobertura_descripcion` | qué cubre | text / no | cuerpo | I |
| `porcentaje_maximo` | cobertura máxima | numeric / no | regex `%` | I cuando se publica |
| `requisitos` | condiciones | text / no | cuerpo | I |
| `proceso_postulacion` | pasos | text / no | cuerpo/link | I |
| `renovacion` | condiciones de continuidad | text / no | cuerpo | I |
| `fecha_cierre` | deadline | date / no | convocatoria | N en las 6 UTDT actuales |
| `url_postulacion` | enlace | URL / no | anchor | I |
| `contacto` | email/canal | text / no | cuerpo | I |
| `fuente_url` | evidencia | URL / sí | página scrapeada | I |

## 7.17 Servicios estudiantiles

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `sede` | sede | text/ref / no | página/contexto | I |
| `categoria` | orientación, bienestar, apoyo, etc. | text / sí | fuente asignada | I |
| `nombre_servicio` | nombre | text / sí | encabezado | I |
| `descripcion` | explicación | text / no | cuerpo | I |
| `contacto` | contacto | text / no | email/teléfono | P: 3/8 nulos |
| `url` | destino | URL / no | anchor | I |
| `fuente_url` | evidencia | URL / sí | fuente | I |

## 7.18 Actividades extracurriculares

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `sede` | sede | text/ref / no | contexto | I |
| `categoria` | deportes, club, organización, voluntariado | text / sí | página origen | I |
| `nombre_actividad` | nombre | text / sí | listado | I |
| `descripcion` | detalle | text / no | página individual | P: 32/32 nulas |
| `contacto` | canal | text / no | página | P: 2/32 nulos; otros presentes según JSON |
| `url` | página | URL / no | anchor | I |
| `fuente_url` | evidencia | URL / sí | fuente | I |

## 7.19 Alojamiento

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `sede` | sede | text/ref / no | fuente | I |
| `tipo_apoyo` | residencia, orientación, convenio | text / sí | texto | I |
| `tipo_alojamiento` | tipo | text / no | texto | I |
| `residencia_propia` | propiedad universitaria | boolean / no | afirmación explícita | I |
| `descripcion` | detalle | text / no | cuerpo | I |
| `contacto` | contacto | text / no | cuerpo | I |
| `url` | página | URL / no | anchor | I |
| `fuente_url` | evidencia | URL / sí | fuente | I |

## 7.20 Programas internacionales

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `nivel` | grado/posgrado | text / no | texto | I |
| `tipo_programa` | intercambio/doble diploma/programa corto | text / sí | encabezado/texto | I |
| `nombre_programa` | nombre | text / sí | encabezado | I |
| `cantidad_convenios` | cantidad declarada/contada | integer / no | fuente/mapa | I cuando aplica |
| `duracion_maxima` | duración | text/integer / no | requisitos | P: 4/5 nulos |
| `reconocimiento_academico` | reconocimiento | boolean / no | texto explícito | P: 4/5 nulos |
| `arancel_destino_cubierto` | cobertura | boolean / no | condiciones | P: 3/5 nulos |
| `requisitos` | requisitos | text / no | cuerpo | I |
| `url` | página | URL / no | anchor | I |
| `fuente_url` | evidencia | URL / sí | fuente | I |

## 7.21 Convenios de intercambio

| Campo | Descripción | Tipo / Req. | Fuente/método | Estado |
|---|---|---|---|---|
| `universidad_nombre` | institución | text / sí | contexto | I UTDT |
| `programa_origen` | carrera/programa habilitado | text / sí | mapa/listado | I |
| `universidad_destino` | contraparte | text / sí | mapa | I |
| `ciudad` | ciudad destino | text / no | etiqueta | I |
| `pais` | país | text / no | etiqueta | I en JSON actual |
| `latitud` | coordenada | numeric / no | mapa | I |
| `longitud` | coordenada | numeric / no | mapa | I |
| `observaciones` | restricciones; ej. vacantes | text / no | etiqueta | I |
| `fuente_url` | evidencia | URL / sí | mapa | I |

## 7.22 Directorio académico adicional

No forma parte de `SECTION_FIELDS`, pero está implementado y cargado:

### `personas`

`universidad_id`, `nombre_completo`, `email`, `perfil_url`, `foto_url`, `formacion`, `biografia`, `fuente_url`, `activa`. Los perfiles oficiales enriquecen formación y biografía; docentes sólo presentes en catálogo pueden tener únicamente nombre y fuente.

### `roles_academicos`

Permite que una misma persona tenga varios roles simultáneos en facultad, carrera o materia. Los 688 roles UTDT no se reducen a “profesor” o “decano”; conservan cargo y vínculos.

## 7.23 Catálogo semestral adicional

- `materias_catalogo`: universidad, código, nombre, fuente, activa.
- `materias_catalogo_vinculos`: materia de plan, materia de catálogo, método, confianza.
- `comisiones_materia`: materia de catálogo, año, semestre, sección, contenido, condiciones, programa URL, fuente.
- `horarios_comision`: comisión, tipo de clase, día, inicio, fin.
- `docentes_comision`: comisión, persona, nombre fuente, tipo de clase.

---

# 8. Diccionario completo de columnas

Esta sección repite cada campo funcional de forma individual. Los tipos, ejemplos y estados cuantitativos están en la sección 7.

## `localidades.nombre_localidad`

**Descripción:** ciudad o localidad normalizada. **Fuente:** dirección institucional. **Cómo se obtiene:** texto o regex. **Problemas:** abreviaturas y CABA. **Vacío:** si la sede no publica dirección. **Mejora:** catálogo geográfico oficial.

## `localidades.provincia`

**Descripción:** provincia/jurisdicción. **Fuente:** dirección. **Extracción:** texto posterior a localidad. **Problemas:** variantes `Pcia. de Bs. As.`. **Vacío:** fuente insuficiente. **Mejora:** normalizador jurisdiccional.

## `localidades.codigo_postal`

**Descripción:** CPA/código postal publicado. **Fuente:** dirección. **Extracción:** regex. **Problemas:** no todas las fuentes lo muestran. **Vacío:** no publicado. **Mejora:** fuente postal oficial, sólo si se valida.

## `universidades.nombre_oficial`

**Descripción:** razón/nombre institucional. **Fuente:** sitio oficial y adapter. **Extracción:** configuración verificada. **Problemas:** variantes ortográficas. **Vacío:** nunca debería. **Mejora:** registro maestro nacional.

## `universidades.nombre_corto`

**Descripción:** sigla de exhibición. **Fuente:** marca institucional. **Extracción:** configuración. **Problemas:** siglas ambiguas. **Vacío:** si no hay sigla oficial. **Mejora:** alias versionados.

## `universidades.tipo_gestion`

**Descripción:** estatal o privada. **Fuente:** información institucional. **Extracción:** valor verificado por adapter. **Problemas:** no inferir por dominio. **Vacío:** sin fuente. **Mejora:** fuente oficial educativa.

## `universidades.anio_fundacion`

**Descripción:** año institucional. **Fuente:** historia institucional. **Extracción:** número. **Problemas:** fundación versus autorización. **Vacío:** UdeSA actual. **Mejora:** definir semántica exacta.

## `universidades.sitio_web`

**Descripción:** URL oficial base. **Fuente:** configuración. **Extracción:** constante. **Problemas:** redirects/subdominios. **Vacío:** no esperado. **Mejora:** canonical final.

## `universidades.telefono_area`

**Descripción:** prefijo país/área. **Fuente:** contacto. **Extracción:** separación de teléfono. **Problemas:** formatos heterogéneos. **Vacío:** no publicado. **Mejora:** E.164 más raw.

## `universidades.telefono_numero`

**Descripción:** número principal. **Fuente:** contacto. **Extracción:** texto. **Problemas:** internos. **Vacío:** no publicado. **Mejora:** guardar número normalizado y original.

## `universidades.mail_contacto`

**Descripción:** email institucional. **Fuente:** admisiones/contacto. **Extracción:** `mailto` o regex. **Problemas:** varios destinatarios. **Vacío:** no publicado. **Mejora:** tabla de contactos por función.

## `universidades.instagram`

**Descripción:** canal Instagram. **Fuente:** enlaces oficiales. **Extracción:** anchor. **Problemas:** cuentas por unidad. **Vacío:** canal ausente. **Mejora:** usar `redes_contacto` como fuente canónica.

## `universidades.tiktok`

**Descripción:** canal TikTok. **Fuente:** enlaces oficiales. **Extracción:** anchor. **Problemas:** cuenta no institucional. **Vacío:** canal ausente. **Mejora:** validar dominio/usuario.

## `universidades.linkedin`

**Descripción:** LinkedIn institucional. **Fuente:** links. **Extracción:** anchor. **Problemas:** escuelas separadas. **Vacío:** no enlazado. **Mejora:** contactos multientidad.

## `universidades.twitter`

**Descripción:** Twitter/X institucional. **Fuente:** links. **Extracción:** anchor. **Problemas:** renombre de plataforma. **Vacío:** no enlazado. **Mejora:** alias de canal `X`/`Twitter`.

## `universidades.facebook`

**Descripción:** Facebook institucional. **Fuente:** links. **Extracción:** anchor. **Problemas:** URLs de tracking. **Vacío:** no enlazado. **Mejora:** limpiar parámetros.

## `universidades.youtube`

**Descripción:** YouTube institucional. **Fuente:** links. **Extracción:** anchor. **Problemas:** canales legacy. **Vacío:** no enlazado. **Mejora:** canonical de canal.

## `sedes.universidad_nombre`

**Descripción:** padre institucional. **Fuente:** adapter. **Extracción:** contexto. **Problemas:** ninguno si adapter correcto. **Vacío:** inválido. **Mejora:** FK temprana.

## `sedes.nombre_sede`

**Descripción:** nombre publicado. **Fuente:** encabezado. **Extracción:** texto. **Problemas:** `Campus`/`Sede` forman parte del nombre. **Vacío:** inválido. **Mejora:** aliases sin perder nombre oficial.

## `sedes.localidad`

**Descripción:** referencia legible. **Fuente:** dirección. **Extracción:** localidad + provincia. **Problemas:** resolución ambigua. **Vacío:** dirección incompleta. **Mejora:** geocodificación verificable.

## `sedes.calle`

**Descripción:** vía. **Fuente:** dirección. **Extracción:** regex. **Problemas:** avenidas/rutas. **Vacío:** no publicado. **Mejora:** parser argentino de domicilios.

## `sedes.numero`

**Descripción:** altura. **Fuente:** dirección. **Extracción:** regex. **Problemas:** `s/n`, km. **Vacío:** sin altura. **Mejora:** mantener text.

## `sedes.tipo_sede`

**Descripción:** categoría compatible con enum DB. **Fuente:** nombre/contexto. **Extracción:** regla. **Problemas:** enum no incluía `Sede`; se usa `Otro`. **Vacío:** tipo incierto. **Mejora:** ampliar enum fuera del repo si el producto lo requiere.

## `facultades.universidad_nombre`

**Descripción:** institución padre. **Fuente:** adapter. **Extracción:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `facultades.nombre_facultad`

**Descripción:** nombre de unidad. **Fuente:** institucional/ruta. **Extracción:** texto o configuración. **Problemas:** facultad/escuela/departamento. **Vacío:** inválido. **Mejora:** aliases.

## `facultades.tipo_unidad`

**Descripción:** tipo organizativo. **Fuente:** encabezado/ruta. **Extracción:** prefijo. **Problemas:** taxonomía institucional propia. **Vacío:** tipo no declarado. **Mejora:** vocabulario flexible.

## `facultades.sede`

**Descripción:** sede asociada. **Fuente:** institucional/ofertas. **Extracción:** relación derivada. **Problemas:** N:M. **Vacío:** UdeSA JSON. **Mejora:** usar exclusivamente `facultades_sedes`.

## `carreras.universidad_nombre`

**Descripción:** institución. **Fuente:** adapter. **Extracción:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `carreras.facultad_nombre`

**Descripción:** unidad responsable. **Fuente:** configuración/ruta. **Extracción:** mapa explícito. **Problemas:** programas interdisciplinarios. **Vacío:** sin asignación oficial. **Mejora:** relación N:M futura.

## `carreras.nombre_carrera`

**Descripción:** nombre usado por la institución. **Fuente:** listado/página. **Extracción:** texto/config. **Problemas:** cambios de nombre. **Vacío:** inválido. **Mejora:** historial de denominaciones.

## `carreras.denominacion_canonica`

**Descripción:** forma comparable. **Fuente:** mapa verificado. **Extracción:** alias. **Problemas:** no confundir programas distintos. **Vacío:** si no se validó. **Mejora:** catálogo nacional de títulos.

## `carreras.nivel`

**Descripción:** nivel académico. **Fuente:** sección. **Extracción:** contexto. **Problemas:** ciclos de complementación. **Vacío:** no esperado. **Mejora:** subtipos.

## `carreras.titulo_otorgado`

**Descripción:** credencial oficial. **Fuente:** plan/resolución. **Extracción:** etiqueta `Título`. **Problemas:** el nombre comercial no garantiza el título. **Vacío:** UdeSA actual. **Mejora:** planes PDF/resoluciones.

## `carreras.tiene_titulo_intermedio`

**Descripción:** indica credencial intermedia. **Fuente:** plan. **Extracción:** texto explícito. **Problemas:** ausencia no equivale a `false`. **Vacío:** 13/13 UTDT y UdeSA. **Mejora:** buscar secciones de certificaciones.

## `carreras.duracion_anios`

**Descripción:** duración nominal. **Fuente:** detalle/plan. **Extracción:** regex de años. **Problemas:** meses/cuatrimestres. **Vacío:** no publicado. **Mejora:** conversor con evidencia raw.

## `carreras.descripcion_breve`

**Descripción:** propuesta oficial. **Fuente:** meta/header/párrafo relevante. **Extracción:** HTML limpio. **Problemas:** marketing o contenido irrelevante. **Vacío:** fuente pobre. **Mejora:** ranking determinístico de párrafos.

## `carreras.cantidad_materias_total`

**Descripción:** cantidad extraída del plan. **Fuente:** lista/tablas. **Extracción:** conteo. **Problemas:** electivas genéricas, orientaciones. **Vacío:** plan no accesible. **Mejora:** distinguir mínimo, optativas y variantes.

## `ofertas.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `ofertas.facultad_nombre`

**Descripción:** unidad. **Fuente:** carrera/config. **Extracción:** mapa. **Problemas:** interdisciplinariedad. **Vacío:** unidad desconocida. **Mejora:** N:M.

## `ofertas.carrera_nombre`

**Descripción:** carrera ofrecida. **Fuente:** carrera. **Extracción:** referencia. **Vacío:** inválido. **Mejora:** FK directa.

## `ofertas.sede`

**Descripción:** lugar de dictado. **Fuente:** etiqueta `Sede`. **Extracción:** texto y descomposición segura. **Problemas:** cursada mixta. **Vacío:** no publicado. **Mejora:** modelar proporción/ciclo por sede.

## `ofertas.modalidad`

**Descripción:** presencial/virtual/híbrida. **Fuente:** detalle. **Extracción:** etiqueta/keywords. **Problemas:** presencial con componentes virtuales. **Vacío:** no declarada. **Mejora:** conservar raw y modalidad principal.

## `ofertas.regimen_ingreso`

**Descripción:** mecanismo de admisión. **Fuente:** admisiones/FAQ. **Extracción:** frases explícitas. **Problemas:** cambia por carrera/ciclo. **Vacío:** UdeSA actual. **Mejora:** entidad de requisitos por ciclo.

## `ofertas.coneau_resolucion`

**Descripción:** resolución de acreditación. **Fuente:** CONEAU/resolución. **Extracción:** no implementada. **Vacío:** 13/13 UTDT. **Mejora:** adapter oficial externo.

## `ofertas.coneau_vigencia_hasta`

**Descripción:** vencimiento de acreditación. **Fuente:** resolución. **Extracción:** fecha. **Problemas:** resoluciones sucesivas. **Vacío:** actual. **Mejora:** historial de acreditaciones.

## `ofertas.tiene_pasantias`

**Descripción:** disponibilidad publicada. **Fuente:** página de carrera. **Extracción:** keywords verificadas. **Problemas:** promesa general versus requisito. **Vacío:** no explícito. **Mejora:** distinguir disponibilidad/obligatoriedad.

## `ofertas.tiene_bolsa_trabajo`

**Descripción:** servicio laboral. **Fuente:** carrera/institucional. **Extracción:** frase. **Problemas:** servicio universitario global. **Vacío:** no publicado. **Mejora:** mover a servicio + derivar indicador.

## `ofertas.url_oficial`

**Descripción:** evidencia principal. **Fuente:** navegación. **Extracción:** URL final. **Problemas:** redirects. **Vacío:** error crítico. **Mejora:** canonical y fecha de chequeo.

## `turnos_anio.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto de carga. **Extracción:** relación. **Vacío:** no esperado. **Mejora:** vista DB.

## `turnos_anio.carrera_nombre`

**Descripción:** carrera. **Fuente:** materia de plan vinculada. **Extracción:** link plan-catálogo. **Problemas:** materias compartidas. **Vacío:** sin vínculo inequívoco. **Mejora:** más semestres.

## `turnos_anio.sede`

**Descripción:** sede de oferta. **Fuente:** oferta. **Extracción:** FK. **Problemas:** una carrera multi-sede. **Vacío:** oferta sin sede. **Mejora:** comisión con sede explícita.

## `turnos_anio.anio_carrera`

**Descripción:** año del plan. **Fuente:** materia vinculada. **Extracción:** entero. **Problemas:** optativas transversales. **Vacío:** materia sin año. **Mejora:** ciclo/tramo.

## `turnos_anio.turno`

**Descripción:** franja. **Fuente:** hora inicial. **Extracción:** <13 Mañana; <18 Tarde; resto Noche. **Problemas:** frontera convencional. **Vacío:** hora inválida. **Mejora:** parametrizar cortes.

## `ofertas_ciclo.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `ofertas_ciclo.carrera_nombre`

**Descripción:** carrera. **Fuente:** oferta. **Extracción:** referencia. **Vacío:** inválido. **Mejora:** FK.

## `ofertas_ciclo.sede`

**Descripción:** sede. **Fuente:** oferta. **Extracción:** referencia. **Vacío:** no publicado. **Mejora:** oferta_id directo.

## `ofertas_ciclo.ciclo_anio`

**Descripción:** año de ingreso. **Fuente:** texto de admisión. **Extracción:** regex `marzo 20xx`. **Problemas:** múltiples ingresos. **Vacío:** no detectado. **Mejora:** calendario estructurado.

## `ofertas_ciclo.ciclo_nombre`

**Descripción:** etiqueta. **Fuente:** año extraído. **Extracción:** `Ingreso {año}`. **Problemas:** semestre/cohorte. **Vacío:** sin año. **Mejora:** preservar etiqueta original.

## `ofertas_ciclo.cupo_ingresantes`

**Descripción:** capacidad. **Fuente:** admisiones. **Extracción:** no implementada. **Vacío:** 13/13 UTDT. **Mejora:** convocatorias oficiales.

## `ofertas_ciclo.fecha_apertura_inscripcion`

**Descripción:** inicio. **Fuente:** calendario. **Extracción:** fecha. **Vacío:** 13/13 UTDT. **Mejora:** fuente por cohorte.

## `ofertas_ciclo.fecha_cierre_inscripcion`

**Descripción:** deadline. **Fuente:** calendario. **Extracción:** fecha. **Vacío:** 13/13 UTDT. **Mejora:** monitoreo de cambios.

## `ofertas_ciclo.estado`

**Descripción:** estado actual. **Fuente:** disponibilidad de solicitud. **Extracción:** regla. **Problemas:** señal indirecta. **Vacío:** sin evidencia. **Mejora:** fechas + estado publicado.

## `aranceles.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto futuro. **Extracción:** no implementada. **Vacío:** tabla completa. **Mejora:** adapter de aranceles.

## `aranceles.carrera_nombre`

**Descripción:** carrera tarifada. **Fuente:** documento futuro. **Problemas:** valores por categoría, no carrera. **Vacío:** tabla completa. **Mejora:** reglas de aplicabilidad.

## `aranceles.sede`

**Descripción:** sede aplicable. **Fuente:** documento futuro. **Problemas:** tarifa institucional. **Vacío:** tabla completa. **Mejora:** nullable/aplicabilidad global.

## `aranceles.vigencia_desde`

**Descripción:** inicio del precio. **Fuente:** documento con fecha. **Problemas:** páginas sin fecha. **Vacío:** tabla completa. **Mejora:** no cargar sin evidencia temporal.

## `aranceles.monto_mensual`

**Descripción:** cuota. **Fuente:** tarifario. **Problemas:** cantidad de cuotas/bonificaciones. **Vacío:** tabla completa. **Mejora:** modelo de componentes.

## `aranceles.monto_matricula`

**Descripción:** matrícula. **Fuente:** tarifario. **Problemas:** conceptos variables. **Vacío:** tabla completa. **Mejora:** concepto separado.

## `aranceles.moneda`

**Descripción:** moneda. **Fuente:** símbolo/texto. **Problemas:** `$` ambiguo. **Vacío:** sin monto. **Mejora:** exigir `ARS`/`USD` explícito o contexto argentino validado.

## `aranceles.motivo_cambio`

**Descripción:** razón/versionado. **Fuente:** proceso de actualización. **Problemas:** rara vez publicado. **Vacío:** esperable. **Mejora:** `detected_change` técnico.

## `areas_tematicas.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `areas_tematicas.facultad_nombre`

**Descripción:** unidad. **Fuente:** carrera. **Extracción:** referencia. **Vacío:** unidad desconocida. **Mejora:** FK.

## `areas_tematicas.carrera_nombre`

**Descripción:** carrera. **Fuente:** plan. **Extracción:** referencia. **Vacío:** inválido. **Mejora:** FK.

## `areas_tematicas.area_tematica`

**Descripción:** familia de contenido. **Fuente:** UTDT keywords; UdeSA referencias oficiales. **Problemas:** taxonomías no equivalentes. **Vacío:** materia no clasificable. **Mejora:** mapa transversal versionado.

## `areas_tematicas.cantidad_materias`

**Descripción:** agregado. **Fuente:** materias. **Extracción:** conteo. **Problemas:** optativas. **Vacío:** sin materias. **Mejora:** vista calculada.

## `materias.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `materias.carrera_o_programa`

**Descripción:** padre polimórfico. **Fuente:** plan recorrido. **Extracción:** contexto. **Problemas:** mismo nombre en grado/posgrado. **Vacío:** inválido. **Mejora:** IDs separados desde staging.

## `materias.nombre_materia`

**Descripción:** nombre oficial. **Fuente:** celda/lista. **Extracción:** texto. **Problemas:** asteriscos, partes, equivalencias. **Vacío:** se descarta. **Mejora:** raw + canonical.

## `materias.anio_cursada`

**Descripción:** año nominal. **Fuente:** encabezado/columna. **Extracción:** entero. **Problemas:** ciclos/posgrado. **Vacío:** 358 UTDT, principalmente posgrados. **Mejora:** `tramo` flexible.

## `materias.turno`

**Descripción:** franja. **Fuente:** horarios. **Extracción:** no se completa en fila de plan. **Vacío:** 829/829 UTDT. **Mejora:** consultar tabla derivada, no duplicar.

## `materias.area_tematica`

**Descripción:** categoría. **Fuente:** regla/color. **Extracción:** classifier determinístico. **Problemas:** ambigüedad semántica. **Vacío:** no clasificable. **Mejora:** taxonomía revisada.

## `materias.descripcion_breve`

**Descripción:** contenido. **Fuente:** catálogo/programa. **Extracción:** en catálogo se guarda a nivel comisión. **Vacío:** 829/829 en tabla de plan UTDT. **Mejora:** vista que combine vínculo y contenido vigente.

## `materias.regimen`

**Descripción:** frecuencia. **Fuente:** plan. **Extracción:** estructura/etiqueta. **Problemas:** semestre no siempre publicado. **Vacío:** 661 UTDT. **Mejora:** campo `semestre_plan` separado.

## `materias.carga_horaria_semanal`

**Descripción:** horas por semana. **Fuente:** programa. **Extracción:** no implementada. **Vacío:** 829/829 UTDT. **Mejora:** PDF/API de cursos.

## `posgrados.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `posgrados.facultad_nombre`

**Descripción:** unidad responsable. **Fuente:** sección del índice/detalle. **Extracción:** alias de unidad. **Problemas:** programas conjuntos. **Vacío:** fuente no asigna. **Mejora:** N:M.

## `posgrados.nombre_programa`

**Descripción:** nombre oficial. **Fuente:** tarjeta/índice. **Extracción:** texto y separación de nombres combinados. **Problemas:** páginas que agrupan maestría/especialización. **Vacío:** se descarta. **Mejora:** identidad por URL+título.

## `posgrados.tipo_posgrado`

**Descripción:** tipo. **Fuente:** nombre/sección. **Extracción:** prefijo. **Problemas:** MBA/Executive MBA. **Vacío:** tipo no clasificable. **Mejora:** aliases verificados.

## `posgrados.titulo_otorgado`

**Descripción:** credencial oficial. **Fuente:** `Título`/plan/resolución. **Extracción:** patrones estrictos + mapa verificado. **Problemas:** nombre comercial distinto. **Vacío:** 14/28 UTDT. **Mejora:** repositorio institucional/CONEAU.

## `posgrados.sede`

**Descripción:** lugar. **Fuente:** programa. **Extracción:** contexto. **Problemas:** online/múltiples sedes. **Vacío:** no publicado. **Mejora:** ofertas de posgrado separadas.

## `posgrados.modalidad`

**Descripción:** formato. **Fuente:** todas las páginas relevantes. **Extracción:** keywords presencial/online/blended. **Problemas:** contradicciones entre páginas. **Vacío:** 6/28 UTDT. **Mejora:** registrar fuente por campo.

## `posgrados.duracion_meses`

**Descripción:** duración comparable. **Fuente:** texto. **Extracción:** regex y conversión. **Problemas:** carga flexible. **Vacío:** 6/28. **Mejora:** preservar unidad/original.

## `posgrados.requiere_tesis_trabajo_final`

**Descripción:** cierre académico. **Fuente:** plan/reglamento. **Extracción:** frases explícitas. **Problemas:** tesis vs trabajo integrador. **Vacío:** 2/28. **Mejora:** enum de tipo de trabajo final.

## `posgrados.requisito_titulo_previo`

**Descripción:** titulación requerida. **Fuente:** admisiones. **Extracción:** sección requisitos. **Problemas:** excepciones. **Vacío:** 2/28. **Mejora:** requisitos estructurados.

## `posgrados.cohorte_inicio`

**Descripción:** próxima cohorte. **Fuente:** detalle. **Extracción:** patrones de mes/año. **Problemas:** contenido caduca. **Vacío:** 26/28. **Mejora:** entidad histórica de cohortes.

## `posgrados.costo_total_programa`

**Descripción:** costo total. **Fuente:** arancel oficial. **Extracción:** no implementada. **Vacío:** 28/28. **Mejora:** tarifarios con vigencia.

## `posgrados.moneda`

**Descripción:** moneda del costo. **Fuente:** junto al monto. **Extracción:** no implementada. **Vacío:** 28/28. **Mejora:** enum y raw.

## `posgrados.descripcion_breve`

**Descripción:** propuesta. **Fuente:** detalle/suplementos. **Extracción:** puntuación determinística de relevancia. **Problemas:** suplementos de otros programas. **Vacío:** 0/28. **Mejora:** tests por unidad.

## `posgrados.url_oficial`

**Descripción:** página principal. **Fuente:** índice. **Extracción:** anchor. **Problemas:** redirects/legacy. **Vacío:** ninguno actual. **Mejora:** canonical final.

## `actividades.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `actividades.carrera_o_programa`

**Descripción:** padre. **Fuente:** plan. **Extracción:** contexto. **Problemas:** actividad transversal. **Vacío:** inválido. **Mejora:** N:M.

## `actividades.tipo_actividad`

**Descripción:** categoría. **Fuente:** nombre de materia. **Extracción:** keywords. **Problemas:** falsos positivos. **Vacío:** no se crea la fila. **Mejora:** validar sección y naturaleza.

## `actividades.nombre_actividad`

**Descripción:** nombre publicado. **Fuente:** plan. **Extracción:** texto. **Problemas:** asteriscos/notas. **Vacío:** no esperado. **Mejora:** raw/canonical.

## `actividades.obligatoria`

**Descripción:** obligatoriedad. **Fuente:** plan. **Extracción:** no implementada. **Vacío:** 12/12 UTDT. **Mejora:** distinguir optativa/obligatoria.

## `actividades.carga_horaria_total`

**Descripción:** horas totales. **Fuente:** plan/reglamento. **Extracción:** no implementada. **Vacío:** 12/12. **Mejora:** parser PDF.

## `actividades.descripcion_breve`

**Descripción:** detalle. **Fuente:** página/plan. **Extracción:** no implementada. **Vacío:** 12/12. **Mejora:** enlazar página individual.

## `autoridades.facultad_nombre`

**Descripción:** unidad. **Fuente:** encabezado. **Extracción:** `AUTHORITY_SECTIONS`. **Problemas:** encabezados nuevos. **Vacío:** inválido. **Mejora:** descubrir unidades del mismo índice.

## `autoridades.carrera`

**Descripción:** carrera si el cargo aplica. **Fuente:** página de carrera. **Extracción:** contexto. **Problemas:** autoridades de unidad no tienen carrera. **Vacío:** 14/17 UTDT y es correcto en muchos casos. **Mejora:** no tratar null como error global.

## `autoridades.cargo`

**Descripción:** denominación publicada. **Fuente:** etiqueta. **Extracción:** texto antes de `:`. **Problemas:** varios decanos/roles. **Vacío:** inválido. **Mejora:** conservar cargo exacto + categoría.

## `autoridades.tipo`

**Descripción:** académico/administrativo. **Fuente:** cargo/contexto. **Extracción:** regla. **Problemas:** no siempre explícito. **Vacío:** posible. **Mejora:** enum con `No especificado` o null.

## `autoridades.nombre_autoridad`

**Descripción:** persona. **Fuente:** texto. **Extracción:** parser de nombre. **Problemas:** `Andrés De la Cruz` expuso discrepancia de canonicalización. **Vacío:** se descarta. **Mejora:** identidad por clave normalizada.

## `redes_contacto.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Extracción:** adapter. **Vacío:** inválido. **Mejora:** FK.

## `redes_contacto.facultad_nombre`

**Descripción:** unidad opcional. **Fuente:** contexto. **Extracción:** referencia. **Vacío:** 9/9 UTDT porque son institucionales. **Mejora:** no auditar como faltante si alcance institucional.

## `redes_contacto.canal`

**Descripción:** tipo de canal. **Fuente:** dominio/atributo. **Extracción:** mapa. **Problemas:** X/Twitter. **Vacío:** inválido. **Mejora:** enum extensible.

## `redes_contacto.usuario_o_direccion`

**Descripción:** valor. **Fuente:** href/texto. **Extracción:** anchor. **Problemas:** URLs relativas. **Vacío:** inválido. **Mejora:** URL absoluta y valor display separados.

## `becas.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `becas.nombre_beca`

**Descripción:** nombre oficial. **Fuente:** encabezado. **Extracción:** texto. **Problemas:** programas paraguas. **Vacío:** inválido. **Mejora:** id fuente.

## `becas.nivel`

**Descripción:** nivel aplicable. **Fuente:** contexto. **Extracción:** sección/texto. **Problemas:** múltiples niveles. **Vacío:** no especificado. **Mejora:** lista N:M.

## `becas.tipo_beca`

**Descripción:** criterio. **Fuente:** nombre/cuerpo. **Extracción:** keywords. **Problemas:** combinaciones. **Vacío:** no clasificable. **Mejora:** taxonomía flexible.

## `becas.cobertura_descripcion`

**Descripción:** beneficio. **Fuente:** cuerpo. **Extracción:** párrafo. **Problemas:** condiciones. **Vacío:** no publicado. **Mejora:** componentes estructurados.

## `becas.porcentaje_maximo`

**Descripción:** tope porcentual. **Fuente:** cobertura. **Extracción:** regex. **Problemas:** `hasta` no equivale a otorgamiento. **Vacío:** monto no porcentual. **Mejora:** tipo de cobertura.

## `becas.requisitos`

**Descripción:** elegibilidad. **Fuente:** sección. **Extracción:** texto. **Problemas:** listas largas. **Vacío:** no publicado. **Mejora:** requisitos atomizados.

## `becas.proceso_postulacion`

**Descripción:** pasos. **Fuente:** sección/link. **Extracción:** texto. **Problemas:** portales externos. **Vacío:** no publicado. **Mejora:** checklist.

## `becas.renovacion`

**Descripción:** continuidad. **Fuente:** condiciones. **Extracción:** texto. **Problemas:** reglamentos PDF. **Vacío:** no publicado. **Mejora:** parser de reglamentos.

## `becas.fecha_cierre`

**Descripción:** cierre. **Fuente:** convocatoria. **Extracción:** fecha. **Problemas:** contenido no fechado/permanente. **Vacío:** 6/6 UTDT. **Mejora:** fuente por ciclo.

## `becas.url_postulacion`

**Descripción:** aplicación. **Fuente:** anchor. **Extracción:** URL absoluta. **Problemas:** formulario temporal. **Vacío:** no hay postulación online. **Mejora:** health check.

## `becas.contacto`

**Descripción:** canal de consulta. **Fuente:** cuerpo. **Extracción:** email/teléfono. **Problemas:** genérico. **Vacío:** no publicado. **Mejora:** contacto estructurado.

## `becas.fuente_url`

**Descripción:** evidencia. **Fuente:** página. **Extracción:** URL de fetch. **Vacío:** no permitido conceptualmente. **Mejora:** timestamp/hash.

## `servicios_estudiantiles.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `servicios_estudiantiles.sede`

**Descripción:** sede de disponibilidad. **Fuente:** página/contexto. **Problemas:** servicios globales. **Vacío:** alcance no especificado. **Mejora:** nullable + alcance institucional.

## `servicios_estudiantiles.categoria`

**Descripción:** tipo de apoyo. **Fuente:** página origen. **Extracción:** mapa determinístico. **Problemas:** superposición. **Vacío:** no esperado. **Mejora:** taxonomía común.

## `servicios_estudiantiles.nombre_servicio`

**Descripción:** nombre publicado. **Fuente:** encabezado. **Extracción:** texto. **Vacío:** inválido. **Mejora:** alias.

## `servicios_estudiantiles.descripcion`

**Descripción:** alcance. **Fuente:** cuerpo. **Extracción:** párrafo. **Problemas:** texto general. **Vacío:** sin detalle. **Mejora:** página individual.

## `servicios_estudiantiles.contacto`

**Descripción:** canal. **Fuente:** cuerpo. **Extracción:** email/tel. **Vacío:** 3/8 UTDT. **Mejora:** enlaces de contacto.

## `servicios_estudiantiles.url`

**Descripción:** página del servicio. **Fuente:** anchor. **Extracción:** absoluta. **Vacío:** no hay detalle. **Mejora:** health check.

## `servicios_estudiantiles.fuente_url`

**Descripción:** evidencia. **Fuente:** fetch. **Extracción:** URL. **Vacío:** no esperado. **Mejora:** fecha/hash.

## `actividades_extracurriculares.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `actividades_extracurriculares.sede`

**Descripción:** sede. **Fuente:** contexto. **Problemas:** actividad global. **Vacío:** alcance no especificado. **Mejora:** alcance institucional.

## `actividades_extracurriculares.categoria`

**Descripción:** deporte, organización, centro, acción social. **Fuente:** página. **Extracción:** mapa por URL. **Vacío:** no esperado. **Mejora:** taxonomía.

## `actividades_extracurriculares.nombre_actividad`

**Descripción:** nombre. **Fuente:** listado. **Extracción:** texto. **Problemas:** encabezados ajenos. **Vacío:** inválido. **Mejora:** filtros estructurales.

## `actividades_extracurriculares.descripcion`

**Descripción:** detalle. **Fuente:** página individual. **Extracción:** no recorrida actualmente. **Vacío:** 32/32 UTDT. **Mejora:** seguir URLs de detalle.

## `actividades_extracurriculares.contacto`

**Descripción:** canal. **Fuente:** listado/detalle. **Extracción:** email/red. **Vacío:** algunos registros. **Mejora:** perfiles individuales.

## `actividades_extracurriculares.url`

**Descripción:** página. **Fuente:** anchor. **Extracción:** URL. **Vacío:** si listado sin link. **Mejora:** canonical.

## `actividades_extracurriculares.fuente_url`

**Descripción:** evidencia. **Fuente:** URL de origen. **Vacío:** no esperado. **Mejora:** fecha/hash.

## `alojamiento.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `alojamiento.sede`

**Descripción:** sede relacionada. **Fuente:** página. **Extracción:** contexto. **Vacío:** apoyo general. **Mejora:** alcance.

## `alojamiento.tipo_apoyo`

**Descripción:** modalidad de ayuda. **Fuente:** texto. **Extracción:** regla. **Problemas:** recomendación vs residencia. **Vacío:** no esperado. **Mejora:** enum.

## `alojamiento.tipo_alojamiento`

**Descripción:** residencia/departamento/guía. **Fuente:** texto. **Extracción:** keywords. **Problemas:** ofertas de terceros. **Vacío:** no especificado. **Mejora:** proveedor/relación.

## `alojamiento.residencia_propia`

**Descripción:** propiedad/operación universitaria. **Fuente:** afirmación explícita. **Extracción:** boolean. **Problemas:** convenio no equivale a propia. **Vacío:** ambiguo. **Mejora:** tres estados.

## `alojamiento.descripcion`

**Descripción:** detalle. **Fuente:** cuerpo. **Extracción:** texto limpio. **Vacío:** no publicado. **Mejora:** amenities estructuradas.

## `alojamiento.contacto`

**Descripción:** consulta. **Fuente:** cuerpo. **Extracción:** email/tel. **Vacío:** no publicado. **Mejora:** contacto separado.

## `alojamiento.url`

**Descripción:** página. **Fuente:** anchor. **Extracción:** URL. **Vacío:** no hay detalle. **Mejora:** health check.

## `alojamiento.fuente_url`

**Descripción:** evidencia. **Fuente:** origen. **Vacío:** no esperado. **Mejora:** fecha/hash.

## `programas_internacionales.universidad_nombre`

**Descripción:** institución. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `programas_internacionales.nivel`

**Descripción:** nivel aplicable. **Fuente:** sección/texto. **Problemas:** múltiples. **Vacío:** no especificado. **Mejora:** lista.

## `programas_internacionales.tipo_programa`

**Descripción:** intercambio/doble diploma/corto. **Fuente:** encabezado. **Extracción:** keywords. **Vacío:** no esperado. **Mejora:** enum.

## `programas_internacionales.nombre_programa`

**Descripción:** nombre. **Fuente:** encabezado. **Extracción:** texto. **Vacío:** inválido. **Mejora:** ID fuente.

## `programas_internacionales.cantidad_convenios`

**Descripción:** cantidad de acuerdos. **Fuente:** declaración/mapa. **Extracción:** entero/conteo. **Problemas:** total institucional vs programa. **Vacío:** no disponible. **Mejora:** derivar de convenios por programa.

## `programas_internacionales.duracion_maxima`

**Descripción:** duración permitida. **Fuente:** requisitos. **Extracción:** texto. **Vacío:** 4/5 UTDT. **Mejora:** reglamento.

## `programas_internacionales.reconocimiento_academico`

**Descripción:** reconocimiento de créditos. **Fuente:** condiciones. **Extracción:** boolean explícito. **Vacío:** 4/5. **Mejora:** convenio/reglamento.

## `programas_internacionales.arancel_destino_cubierto`

**Descripción:** tratamiento de arancel destino. **Fuente:** condiciones. **Extracción:** boolean. **Problemas:** exención parcial. **Vacío:** 3/5. **Mejora:** modelo de costos.

## `programas_internacionales.requisitos`

**Descripción:** elegibilidad. **Fuente:** cuerpo. **Extracción:** texto. **Problemas:** listas complejas. **Vacío:** no publicado. **Mejora:** requisitos atomizados.

## `programas_internacionales.url`

**Descripción:** página. **Fuente:** anchor. **Extracción:** URL. **Vacío:** no hay detalle. **Mejora:** canonical.

## `programas_internacionales.fuente_url`

**Descripción:** evidencia. **Fuente:** origen. **Vacío:** no esperado. **Mejora:** fecha/hash.

## `convenios_intercambio.universidad_nombre`

**Descripción:** institución origen. **Fuente:** contexto. **Vacío:** inválido. **Mejora:** FK.

## `convenios_intercambio.programa_origen`

**Descripción:** carrera habilitada. **Fuente:** popup/listado del mapa. **Extracción:** texto. **Problemas:** aliases de carrera. **Vacío:** no esperado en actuales. **Mejora:** FK por alias seguro.

## `convenios_intercambio.universidad_destino`

**Descripción:** institución contraparte. **Fuente:** mapa. **Extracción:** etiqueta. **Problemas:** nombres/traducciones. **Vacío:** inválido. **Mejora:** catálogo global.

## `convenios_intercambio.ciudad`

**Descripción:** ciudad destino. **Fuente:** etiqueta. **Extracción:** separación textual. **Problemas:** ciudades con comas. **Vacío:** no publicada. **Mejora:** geocodificación sólo validada.

## `convenios_intercambio.pais`

**Descripción:** país. **Fuente:** etiqueta/mapa. **Extracción:** texto. **Problemas:** auditoría histórica lo marcó como faltante; JSON final lo completa. **Vacío:** fuente incompleta. **Mejora:** ISO country code adicional.

## `convenios_intercambio.latitud`

**Descripción:** coordenada. **Fuente:** marcador. **Extracción:** dato del mapa. **Vacío:** marcador sin coordenada. **Mejora:** validar rango.

## `convenios_intercambio.longitud`

**Descripción:** coordenada. **Fuente:** marcador. **Extracción:** dato del mapa. **Vacío:** marcador sin coordenada. **Mejora:** validar rango.

## `convenios_intercambio.observaciones`

**Descripción:** restricciones. **Fuente:** texto; ejemplo conversado: temporalmente sin vacantes. **Extracción:** residuo controlado. **Vacío:** sin nota. **Mejora:** estado estructurado.

## `convenios_intercambio.fuente_url`

**Descripción:** mapa/página. **Fuente:** URL scrapeada. **Vacío:** no esperado. **Mejora:** timestamp/hash.

---

# 9. Análisis de datos faltantes

## UTDT — snapshot `data/utdt_completo.json`

| Campo/sección | Faltante exacto | Causa | Recuperable | Fuente alternativa | Complejidad |
|---|---:|---|---|---|---|
| `turnos_anio` en JSON principal | sección vacía | pertenece al catálogo dinámico | Sí; 99 en DB | Looker Studio | Media, resuelto por pipeline aparte |
| `aranceles` | sección vacía | sin fuente pública vigente comprobada | Quizás | tarifario/admisiones oficial | Alta |
| `carreras.tiene_titulo_intermedio` | 13/13 = 100% | plan no lo declara de forma inequívoca | Sí, programa por programa | plan/resolución | Media |
| `ofertas.coneau_resolucion` | 13/13 = 100% | no se integró CONEAU | Sí | CONEAU | Alta |
| `ofertas.coneau_vigencia_hasta` | 13/13 = 100% | idem | Sí | resolución | Alta |
| `ofertas_ciclo.cupo_ingresantes` | 13/13 = 100% | no publicado | Incierto | convocatoria | Alta |
| fechas de ciclo | 13/13 cada una = 100% | sólo se detectó estado/año | Sí si se publican | calendario de admisiones | Media |
| `materias.anio_cursada` | 358/829 = 43,2% | materias de posgrado sin año | Parcial | plan detallado | Media |
| `materias.turno` | 829/829 = 100% | turno está normalizado aparte | Ya derivado para grado | horarios | No debe duplicarse sin decisión |
| `materias.descripcion_breve` | 829/829 = 100% en tabla de plan | contenidos viven en catálogo/comisión | Parcial | catálogo/programas | Media |
| `materias.regimen` | 661/829 = 79,7% | plan no siempre marca período | Parcial | plan/programa | Media |
| `materias.carga_horaria_semanal` | 829/829 = 100% | no publicada en planes usados | Incierto | programas/PDF | Alta |
| `posgrados.titulo_otorgado` | 14/28 = 50% | marketing no equivale a título | Sí | plan/resolución/repositorio | Alta |
| `posgrados.modalidad` | 6/28 = 21,4% | no visible en fuentes recorridas | Parcial | admisiones/programa | Media |
| `posgrados.duracion_meses` | 6/28 = 21,4% | no visible/ambigua | Parcial | plan/programa | Media |
| `posgrados.requiere_tesis...` | 2/28 = 7,1% | no declarado | Sí | reglamento | Media |
| `posgrados.requisito_titulo_previo` | 2/28 = 7,1% | no declarado | Sí | admisiones | Media |
| `posgrados.cohorte_inicio` | 26/28 = 92,9% | fecha variable/no publicada | Parcial | página vigente | Media |
| costo/moneda posgrado | 28/28 = 100% | sin tarifario verificado | Incierto | arancel oficial | Alta |
| actividades: obligatoriedad/horas/descripción | 12/12 cada una = 100% | detectadas desde nombre, sin detalle | Sí | plan/reglamento | Media/Alta |
| `autoridades.carrera` | 14/17 = 82,4% | autoridad de facultad, no faltante real | No corresponde | ninguna | Baja; ajustar semántica de auditoría |
| `redes_contacto.facultad_nombre` | 9/9 = 100% | contactos institucionales | No corresponde | ninguna | Baja |
| `becas.fecha_cierre` | 6/6 = 100% | no publicada/vigencia continua | Parcial | convocatoria anual | Media |
| servicios `contacto` | 3/8 = 37,5% | no publicado | Parcial | página individual | Baja |
| extracurriculares `descripcion` | 32/32 = 100% | sólo listado | Sí | página individual | Media |
| internacional: duración | 4/5 = 80% | no publicada | Parcial | reglamento | Media |
| internacional: reconocimiento | 4/5 = 80% | no explícito | Parcial | reglamento | Media |
| internacional: arancel destino | 3/5 = 60% | no explícito | Parcial | condiciones | Media |

El reporte local más reciente registra 899 pendientes: 53 de prioridad alta, 30 media y 816 baja. Este total subió respecto de los 664 vistos antes porque se agregaron materias/posgrados y reglas; no representa una regresión lineal.

## UdeSA — snapshot `data/udesa_completo.json`

| Campo/sección | Faltante exacto | Causa | Recuperable | Fuente alternativa | Complejidad |
|---|---:|---|---|---|---|
| datos institucionales salvo nombre/tipo/web | 1/1 cada campo | primera fase sólo grado | Sí | institucional/contacto | Baja |
| `facultades.sede` | 8/8 | loader deriva N:M desde ofertas | Ya resuelto en DB | ofertas | No duplicar |
| `carreras.titulo_otorgado` | 18/18 | no extraído del plan | Sí | PDFs/resoluciones | Media |
| `carreras.tiene_titulo_intermedio` | 18/18 | no analizado | Parcial | plan | Media |
| ofertas: ingreso/CONEAU/pasantías/bolsa | 31/31 cada una | fase pendiente | Parcial | admisiones/carrera/CONEAU | Media/Alta |
| materias: turno/descripción/horas | 681/681 cada una | syllabus no lo publica en esas celdas | Parcial | buscador de materias/programas | Alta |
| turnos, ciclos, aranceles | secciones vacías | no implementado | Parcial | catálogo/admisiones/tarifario | Alta |
| posgrados y vida universitaria | 10 secciones vacías | segunda fase no construida | Sí en parte | menú y páginas oficiales | Media/Alta |

Para porcentajes no presentes en estos snapshots o entidades futuras se usa: **PORCENTAJE NO CALCULADO**.

---

# 10. Causa raíz de los faltantes

| Categoría | Ejemplo confirmado |
|---|---|
| Dato no publicado | aranceles UTDT; varias cargas horarias |
| Publicado sólo en algunas páginas | modalidad/duración de posgrados |
| Página dinámica | catálogo Looker Studio; Next.js UdeSA |
| Dato dentro de PDF | títulos, planes, resoluciones potenciales |
| Dato en otra URL | suplementos de posgrado y perfiles personales |
| Inconsistencia semántica | nombre del programa no equivale a título otorgado |
| Scraping incompleto | UdeSA posgrados/vida universitaria todavía no implementados |
| Link obsoleto | seis errores 404/500 en el scrape UTDT final |
| Normalización pendiente | equivalencias de materias, localidades, tipos de sede |
| Ausencia contextual correcta | `autoridades.carrera=null` para decanos de unidad |
| Oferta temporal | materia del plan no aparece en catálogo del semestre |
| Restricción de esquema | `tipo_sede_enum` no acepta `Sede` |

No hubo evidencia de rate limiting, captcha o bloqueo permanente. UdeSA devolvió 403 a `httpx`, pero cargó correctamente con navegador. No se comprobó robots.txt en esta conversación.

---

# 11. Normalización

## Implementada

- `clean_text`: reemplaza NBSP, colapsa espacios y recorta.
- `comparison_key`: Unicode NFKD, remueve acentos y normaliza para comparar.
- URL Supabase: elimina accidentalmente `/rest/v1` y exige URL base.
- Booleanos: acepta `si`, `sí`, `true`, `1`, `no`, `false`, `0`.
- Personas: convierte `Apellido, Nombre` a `Nombre Apellido` y compara sin acentos/case.
- Materias: quita asteriscos finales; equivalencias muy limitadas (`primera parte`/`parte I`, prefijo `Seminario:`, `en la Argentina`).
- Turnos: Mañana antes de 13:00; Tarde antes de 18:00; Noche desde 18:00.
- Modalidad: reglas explícitas para presencial, virtual/online e híbrida/blended.
- Duración: años para carreras; meses/años/cuatrimestres a meses en posgrados.
- UdeSA sedes: `Pcia. de Bs. As.` a `Buenos Aires`; `CABA` a nombre completo + provincia CABA.
- UdeSA multi-sede: descompone etiquetas oficiales en ofertas separadas; CABA se asigna a Callao y Riobamba según la página oficial de sedes.
- Mojibake en textos UTDT: reparación específica.
- Programas legacy UTDT: aliases controlados en loader.

## Propuesta/pending

- ISO 3166 para países, sin sustituir el nombre display.
- E.164 para teléfonos conservando raw.
- Taxonomía transversal de áreas, porque UTDT usa keywords y UdeSA referencias propias.
- Versionar nombres de carrera y programa.
- Separar duración original de duración normalizada.
- Modelar modalidad y sede por período cuando la oferta sea mixta.
- No convertir null en falso.

## Procedencia semántica pendiente de formalizar

“Determinístico” no significa que todos los valores sean citas literales. El pipeline usa cuatro categorías que deben registrarse por campo en la evolución del modelo:

1. **Literal de fuente:** aparece textualmente en HTML, JSON, API o documento oficial.
2. **Configuración verificada:** valor mantenido por el adapter, por ejemplo sigla, gestión o mapa de unidad.
3. **Derivación determinística:** resultado de una regla explícita, por ejemplo turno desde hora o ofertas separadas desde una etiqueta multi-sede.
4. **Ausente:** no existe evidencia suficiente y queda `null`.

Hoy esta distinción está documentada en código/tablas, pero no se persiste uniformemente; `campos_inferidos` vacío no demuestra que todo el registro sea literal.

---

# 12. Deduplicación

## Claves actuales

| Entidad | Identidad/conflicto |
|---|---|
| Localidad | `nombre_localidad, provincia` |
| Universidad | `nombre_oficial` |
| Sede | `universidad_id, nombre_sede` |
| Facultad | `universidad_id, nombre_facultad, tipo_unidad` |
| Carrera | `universidad_id, nombre_carrera` |
| Oferta | `carrera_id, sede_id, modalidad` |
| Ciclo | `oferta_id, ciclo_anio, ciclo_nombre` |
| Posgrado | `universidad_id, nombre_programa` |
| Persona | `universidad_id, nombre_completo` |
| Materia de plan | padre carrera/posgrado + nombre normalizado + año |
| Materia catálogo | `universidad_id, codigo` |
| Comisión | materia catálogo + año + semestre + sección |
| Vínculo plan-catálogo | `materia_id, materia_catalogo_id` |

## Casos problemáticos

- Una materia puede compartir nombre entre años o carreras; la identidad incluye padre y año.
- Los cambios cosméticos no deben crear materias nuevas; se usa `comparison_key`.
- Equivalencias agresivas pueden unir materias diferentes; por eso el matcher sólo enlaza si hay exactamente una coincidencia.
- UdeSA no tuvo duplicados exactos en las 681 materias verificadas.
- `Andrés de la Cruz` versus `Andrés De la Cruz` provocó un `KeyError`; se corrigió usando una clave canónica para persona/rol.

---

# 13. Calidad de los datos

## Problemas de fuente

- Links 404/500 en UTDT.
- Campos distribuidos en páginas suplementarias.
- Páginas de marketing sin título oficial.
- Datos variables sin fecha de vigencia.
- Catálogo semestral no representa la totalidad del plan.
- UdeSA bloquea clientes HTTP simples.

## Problemas del scraper aún abiertos

- Auditoría sólo especializada en UTDT.
- Recursos UdeSA no se cargan a DB.
- Falta pipeline PDF.
- Falta captura raw/versionada aunque fue propuesta.
- Falta atribución por campo; hoy hay fuente por registro/sección en varios casos.
- `areas_tematicas` no es todavía una taxonomía plenamente comparable entre universidades.

## Salvaguardas vigentes

- Validación antes de escritura.
- Conteos esperados (UTDT 13, UdeSA 18).
- Detección de duplicados.
- Comprobación básica de dominios. **PENDIENTE:** reemplazar substring/`endswith` permisivo por `host == dominio` o `host.endswith("." + dominio)`, exigir HTTPS cuando corresponda y validar la URL final tras redirects; agregar tests negativos.
- `null` en vez de valores inventados.
- Preview por defecto; escritura sólo con `--apply`.
- Cargas por chunks para evitar timeouts.
- Preservación de IDs de materias vinculadas.

---

# 14. Decisiones tomadas

## Decisión 001 — Repositorio separado

**Tema:** ubicación del scraper. **Alternativas:** monorepo con app/IA o repo propio. **Decisión:** `rumbo-scraper` separado. **Motivo:** independencia, secretos y ejecuciones largas. **Impacto:** Supabase es el punto común. **Estado:** confirmado.

## Decisión 002 — Supabase directo, no Vercel

**Alternativas:** variables de Vercel o `.env`/GitHub Secrets. **Decisión:** local `.env`; automatización futura con GitHub Secrets. **Motivo:** el scraper no es frontend ni función corta. **Estado:** implementado local; GitHub Actions pendiente.

## Decisión 003 — Secret/service role

**Decisión:** clave secreta para escritura; nunca publishable/anon. **Motivo:** RLS bloqueó escritura con clave pública. **Estado:** implementado; settings admite ambos nombres de variable secreta.

## Decisión 004 — Sin IA

**Alternativas:** LLM fallback versus reglas. **Decisión final:** no IA, prompts ni tokens. **Motivo:** costo, reproducibilidad y pedido explícito. **Estado:** implementado.

## Decisión 005 — Adapters por universidad

**Alternativas:** crawler universal mágico versus parsers específicos. **Decisión:** contrato común y adapters por fuente. **Motivo:** heterogeneidad real. **Estado:** UTDT/UdeSA implementados.

## Decisión 006 — Fuente estructurada antes que visual

**Decisión:** JSON/API/DOM estructurado antes que scraping visual. **Motivo:** precisión. **Estado:** Next JSON y Looker DOM implementados.

## Decisión 007 — No inventar

**Decisión:** ausencia → `null`/sección vacía. **Motivo:** confianza. **Estado:** regla central validada.

## Decisión 008 — SQL fuera del repo

**Decisión:** no guardar migraciones SQL en `rumbo-scraper`. **Motivo:** separación pedida por usuario. **Estado:** commit que lo agregó fue revertido inmediatamente.

## Decisión 009 — Catálogo separado del plan

**Decisión:** `materias` de plan y `materias_catalogo`/comisiones separadas, unidas por vínculo. **Motivo:** temporalidad y detalle. **Estado:** implementado.

## Decisión 010 — Carga idempotente y preservación de IDs

**Decisión:** upsert de entidades estables; sincronizar materias preservando IDs vinculados. **Motivo:** reruns seguros. **Estado:** implementado para entidades principales y materias. Las tablas de detalle que el loader borra y reconstruye —entre ellas actividades, autoridades, contactos, becas, servicios, extracurriculares, alojamiento, programas, convenios, roles y comisiones— no prometen IDs estables todavía.

## Decisión 011 — Directorio persona/rol N:M

**Decisión:** separar personas de roles. **Motivo:** una persona puede ser profesor, director y autoridad. **Estado:** implementado.

## Decisión 012 — UdeSA con Playwright + Next JSON

**Alternativas:** `httpx` bloqueado, scraping visual o navegador estructurado. **Decisión:** navegador y `#__NEXT_DATA__`. **Motivo:** 403 a HTTP y JSON estable. **Estado:** implementado.

## Decisión 013 — Sedes UdeSA como ofertas separadas

**Decisión:** normalizar etiquetas multi-sede a filas por sede validada. **Motivo:** modelo relacional. **Estado:** 31 ofertas cargadas.

## Decisión 014 — Artículo 43/46 fuera del criterio

**Decisión:** no basar similitud ni descripciones en esa etiqueta legal. **Motivo:** el usuario lo descartó y no resuelve similitud de materias. **Estado:** eliminado del contrato Python.

---

# 15. Decisiones descartadas

| Enfoque | Por qué parecía útil | Problema | Motivo del descarte | ¿Retomable? |
|---|---|---|---|---|
| Mezclar varios repos open source | acelerar inicio | arquitectura Frankenstein | mantenimiento | sólo ideas/código puntual |
| Scrapy obligatorio desde día uno | motor robusto | las primeras fuentes se resolvieron mejor con httpx/Playwright | simplicidad del MVP | sí al escalar crawling |
| LLM para ambigüedades | generalización | tokens, no determinismo | requisito del usuario | no mientras siga la restricción |
| Vercel para scraper | infraestructura existente | ejecuciones largas | separación de responsabilidades | no como motor principal |
| Clave publishable | fácil acceso | RLS 42501 | no tiene permisos seguros de escritura | no |
| SQL dentro del repo | reproducibilidad | usuario separa scraper de schema | alcance del repositorio | en repo de infraestructura separado |
| Art. 43/46 como clasificación | equivalencias regulatorias | no describe cada materia/carrera | poca utilidad y pedido explícito | sólo metadata legal externa |
| Inferir título desde nombre | completar más | puede ser falso | principio de no inventar | no |

---

# 16. Errores y problemas encontrados

| Problema | Síntoma | Causa | Solución | Estado |
|---|---|---|---|---|
| Git inicializado en `~` | remote `Rumbo.git`, push rechazado | comando ejecutado en home | crear repo separado en Desktop; no force/pull home | Resuelto |
| Carpeta parecía vacía | Cursor no mostraba archivos | cambios no estaban en repo visible/pusheados | crear estructura y push | Resuelto |
| `.env` mal ubicado | duda sobre carpeta | se intentaba dentro del paquete | ubicar en raíz junto a README | Resuelto |
| `Invalid URL` Supabase | excepción del cliente | URL incorrecta | usar base `https://ref.supabase.co` | Resuelto |
| `PGRST125 Invalid path` | upsert falla | URL contenía `/rest/v1` | normalizador elimina sufijo | Resuelto |
| RLS 42501 | escritura denegada | clave publishable/anon | secret/service-role | Resuelto |
| `KeyError: Andrés De la Cruz` | carga roles falla | nombre no coincidía exactamente | clave canónica por `comparison_key` | Resuelto |
| Looker dinámico | HTML directo insuficiente | JS, virtualización y paginación | Playwright, scroll y paginado | Resuelto |
| Timeouts de cientos de requests | carga lenta/inestable | upserts uno por uno | chunks de 100 | Resuelto |
| IDs de materias cambiaban | links catálogo se perdían | delete/reinsert | sincronización por identidad estable | Resuelto |
| Asteriscos en planes | match fallaba | anotaciones cosméticas | quitar asteriscos finales | Resuelto |
| UdeSA 403 | `httpx` no accede | protección/rendering | Playwright | Resuelto |
| `NoneType.replace` en UdeSA | sede faltante rompe normalizador | `comparison_key(None)` | fallback a cadena vacía | Resuelto |
| enum `tipo_sede` rechaza `Sede` | error PostgreSQL 22P02 | enum real no incluye valor | consultar OpenAPI; mapear satélites a `Otro` | Resuelto |
| Links UTDT 404/500 | 6 errores de descarga | URLs obsoletas/servidor | registrar y continuar; usar suplementos alternativos | Parcial |
| Auditoría crecía tras mejoras | 664 → 899 | más entidades/reglas | interpretar total con denominador | No es bug |

---

# 17. Pruebas realizadas

## Unitarias

35 tests vigentes cubren:

- variables y URL Supabase;
- contrato y 13 carreras UTDT;
- admisión;
- planes, años y exclusión de formularios;
- posgrados combinados, títulos, modalidad, duración, descripciones y materias;
- autoridades, profesores, perfiles y nombre canónico;
- becas/vida universitaria/intercambios;
- parsing de códigos, secciones, horarios y docentes del catálogo;
- deduplicación de horarios;
- equivalencias seguras;
- período académico argentino;
- UdeSA carreras, syllabus, adjuntos, sedes y contrato completo.

Resultado al corte:

```text
Ran 35 tests
OK
```

## Integración real UTDT

- Scrape principal ejecutado repetidamente.
- Carga exitosa de todas las secciones informadas.
- Catálogo: 2.248 horarios, 616 detalles, 299 materias, 819 comisiones, 2.246 horarios deduplicados y 1.591 asignaciones docentes en una corrida registrada.
- En corridas históricas reportadas, los vínculos plan-catálogo evolucionaron de 99 a 136 y luego 140 al refinar matching. No es un baseline actual reproducible: con los JSON locales y matcher vigentes pueden aparecer más candidatos, por lo que el conteo debe asociarse a una corrida/commit antes de compararlo.
- Auditoría bajó en iteraciones 854 → 817 → 743 → 717 → 691 → 668 → 664 antes de nuevas ampliaciones.

## Integración real UdeSA

- 18 carreras cargadas sin errores de descarga.
- 681 materias, sin duplicados exactos carrera+año+nombre.
- 4 sedes, 8 unidades y 31 ofertas verificadas en Supabase.
- 18/18 carreras con descripción.
- 53 recursos detectados: 18 imágenes, 18 documentos y 17 enlaces en la primera corrida verificada.

---

# 18. Estado actual del proyecto

## Funcionando

- Repo independiente, `.env` ignorado, credenciales no impresas.
- UTDT end-to-end principal, catálogo y auditoría.
- UdeSA grado end-to-end.
- Supabase con UTDT y UdeSA cargados.
- Tests y validadores.
- JSON regenerables localmente e ignorados por Git. Su reproducción histórica exacta requiere todavía manifiesto de versión/hash de fuentes.

## Parcialmente funcionando

- Trazabilidad a nivel registro, no todavía a nivel campo.
- Descripciones de materias mediante catálogo UTDT, no integradas al campo legacy.
- Perfil académico sólo para personas con perfil oficial.
- Posgrados UTDT amplios pero con títulos/modalidad/duración incompletos.
- Recursos UdeSA sólo en JSON.

## Pendiente

- UdeSA posgrados, docentes, autoridades, becas, servicios, alojamiento e internacional.
- Aranceles y fechas/cupos verificables.
- Correlatividades.
- PDF pipeline.
- Automatización programada.
- Auditoría multiuniversidad.
- Raw snapshots y change detection.

## Bloqueado

No hay bloqueo técnico total. Algunos campos están bloqueados por falta de fuente pública comprobada.

## Necesita revisión

- Semántica transversal de áreas.
- Qué tabla guardará recursos multimedia.
- Si ampliar enum `tipo_sede` fuera del repo.
- Qué faltantes son realmente accionables versus null correcto.

---

# 19. Qué falta para considerarlo MVP

## P0 — imprescindible

1. Completar UdeSA al mismo contrato funcional mínimo acordado o definir formalmente que el MVP sólo exige grado.
2. Agregar auditoría genérica por universidad.
3. Registrar cada ejecución, resultado y error de forma persistente.
4. Definir estrategia de cambios/bajas para no dejar ofertas obsoletas activas.
5. Automatizar al menos una ejecución controlada con secretos seguros.
6. Revisar y documentar `robots.txt`, términos aplicables, frecuencia, límites por host, User-Agent y canal de contacto antes de automatizar cada dominio. Que una página sea pública o no presente captcha no equivale por sí solo a permiso irrestricto.

## P1 — importante

1. Títulos otorgados UdeSA.
2. Admisión, fechas, becas y aranceles vigentes.
3. Persistencia de recursos públicos.
4. Programas/PDF y descripciones de materias.
5. Monitoreo de links rotos y cambios de estructura.

## P2 — mejora

1. Taxonomía transversal de áreas.
2. Correlatividades.
3. Más granularidad de requisitos y costos.
4. Dashboard de calidad.

## P3 — expansión futura

1. Nuevas universidades.
2. Otros países.
3. Datos de resultados, reviews o rankings sólo con fuentes comparables.
4. Detección asistida de esquemas sin usar IA en la publicación automática.

---

# 20. Plan para escalar 10x, 100x y 1000x

La escala no debe resolverse haciendo un scraper universal que “adivine” páginas. La unidad de trabajo sigue siendo un **adapter determinístico por universidad**, apoyado por componentes compartidos para descarga, normalización, validación, persistencia y observabilidad.

## Escala pequeña — hasta 10 universidades

**Objetivo:** terminar el contrato, aprender las variaciones reales y conservar máxima trazabilidad.

- Un módulo `spiders/<universidad>.py`, un parser y un validador específicos por institución.
- Ejecuciones manuales o programadas una vez por semana.
- Playwright sólo cuando una página dependa de JavaScript; `httpx` para HTML, JSON, CSV o APIs accesibles directamente.
- JSON intermedio por universidad para poder revisar antes de escribir.
- Cargas `upsert` idempotentes y auditoría de completitud después de cada corrida.
- Concurrencia baja por dominio, con espera y límites conservadores.
- Reintentos únicamente para errores transitorios: timeout, `429` y `5xx`.
- Pruebas unitarias con fixtures de las estructuras críticas.

Esto alcanza para UTDT, UdeSA y las siguientes instituciones mientras se estabiliza qué campos son realmente comunes.

## Escala media — hasta 100 universidades

**Objetivo:** separar descubrimiento, extracción y publicación para que una falla no invalide toda la corrida.

Flujo propuesto:

1. Un planificador crea trabajos por universidad y tipo de entidad.
2. Una cola distribuye `discover`, `fetch`, `parse`, `validate`, `diff` y `publish`.
3. Los workers aplican límites por dominio y reutilizan caché HTTP.
4. El almacenamiento de objetos conserva snapshots crudos y artefactos descargados.
5. Un staging guarda registros normalizados antes de Supabase de producción.
6. El publicador sólo aplica lotes que superan controles de calidad.

Requisitos técnicos:

- Estado de corrida persistente con universidad, etapa, timestamps, versión del adapter y resultado.
- Reintentos exponenciales con jitter y dead-letter queue para fallas definitivas.
- Locks por universidad/período para impedir corridas superpuestas.
- Escritura por lotes y paginación; no un request por fila cuando la API permita batch.
- Métricas por fuente: latencia, tasa de éxito, registros descubiertos, creados, actualizados, inactivados y rechazados.
- Alertas por caídas bruscas, por ejemplo si una fuente que tenía 800 materias devuelve 20.
- Versionado del contrato y migraciones coordinadas fuera de este repositorio si corresponden a la base.

## Escala grande — 1000 universidades, varios países y millones de páginas

**Objetivo:** operar como plataforma de adquisición de datos, no como colección de scripts.

- Orquestador distribuido con colas por prioridad y capacidad por dominio.
- Workers stateless y escalables horizontalmente para HTTP, browser, PDF y validación.
- Almacenamiento de objetos con hash de contenido para evitar duplicados.
- Catálogo de fuentes con país, institución, idioma, robots/política, frecuencia y responsable.
- Detección de cambios de esquema mediante selectores canarios, conteos históricos y validación de tipos.
- Particionado de ejecuciones por institución, período y clase de recurso.
- Actualizaciones incrementales basadas en `ETag`, `Last-Modified`, hash, sitemap o fecha de modificación cuando estén disponibles.
- Recorrida completa periódica para detectar bajas que los incrementales no revelan.
- Límite global y por host, ventanas horarias y circuit breaker.
- Separación entre datos crudos, normalizados, reconciliados y publicados.
- Linaje por campo y rollback a la última versión válida.
- Observabilidad central: logs estructurados, métricas, trazas, panel de frescura y calidad.
- Muestreo humano para fuentes nuevas o cambios de estructura relevantes.

## Estrategia de actualización

| Tipo de dato | Frecuencia inicial sugerida | Motivo |
|---|---:|---|
| Oferta, admisión, aranceles, becas | semanal en temporada; mensual fuera de temporada | Cambia por ciclo y afecta decisiones del usuario. |
| Catálogo, comisiones y horarios | al inicio del período y semanal durante ajustes | Es altamente temporal. |
| Planes de estudio y materias | mensual más una recorrida completa semestral | Cambian menos, pero una reforma curricular es importante. |
| Autoridades y docentes | mensual | Puede cambiar sin aviso. |
| Servicios, sedes, alojamiento e intercambio | mensual o trimestral | Menor volatilidad, salvo convocatorias. |
| Fotos, PDFs y recursos | por hash/fecha, con revisión trimestral | Evita descargar lo mismo. |

## Deduplicación a escala

- Mantener claves naturales por ámbito: institución + código, o institución + nombre normalizado + contexto.
- No fusionar automáticamente personas sólo por nombre entre universidades.
- Hash para archivos y contenido crudo.
- Tabla de alias para nombres históricos y variantes.
- Registro explícito de merges y posibilidad de revertirlos.
- Resolución automática sólo con evidencia suficiente; los casos ambiguos van a revisión.

## APIs y scraping híbrido

Orden preferido: API/JSON oficial, CSV oficial, datos embebidos, HTML semántico, PDF textual y, al final, navegador automatizado. Google puede ayudar a **descubrir** URLs públicas, pero no es la fuente probatoria del dato. No se deben sortear autenticaciones, paywalls ni accesos internos.

## IA en la extracción

**Decisión descartada para la arquitectura vigente:** usar un LLM en cada corrida. Contradice el requisito de no consumir tokens y complica reproducibilidad. Si la política cambiara, podría evaluarse sólo como asistencia offline para proponer selectores o clasificar pendientes; nunca para publicar hechos sin evidencia determinística.

---

# 21. Estrategia de enriquecimiento de datos

Cada enriquecimiento debe terminar con valor, URL exacta, fecha de obtención y nivel de confianza. La prioridad es la fuente más cercana al dueño del dato.

## Orden de búsqueda

1. Página oficial de la entidad específica: materia, carrera, posgrado, docente o beca.
2. Página oficial de la carrera/facultad cuando la entidad no tenga perfil propio.
3. PDF oficial: plan, programa, resolución, folleto o reglamento.
4. Buscador interno, sitemap y APIs/JSON usados por el sitio oficial.
5. Organismos públicos: reconocimiento oficial, acreditación y validez.
6. Schema.org, JSON-LD, OpenGraph y metadatos del sitio.
7. Redes institucionales verificadas sólo para datos de contacto o eventos que no aparezcan en el sitio.
8. Motores de búsqueda sólo para descubrimiento de una fuente primaria.

## Por tipo de faltante

| Faltante | Fuente a intentar | Tratamiento |
|---|---|---|
| Título otorgado | encabezado oficial, plan o resolución | Guardar literal y normalizar sólo espacios. |
| Descripción de materia | ficha del catálogo o programa PDF | Mantener período y URL; no mezclar años sin indicarlo. |
| Carga horaria | plan/programa oficial | Registrar unidad y alcance: semanal, total o créditos. |
| Correlatividades | plan o sistema público de cursos | Modelar relación, no texto libre solamente. |
| Arancel | página de admisiones/aranceles | Guardar moneda, período, concepto y fecha de vigencia. |
| Beca | bases y condiciones | Guardar beneficio, requisitos, cobertura, fechas y URL. |
| Autoridad/docente | directorio o perfil institucional | Una persona puede tener varios roles y unidades. |
| Foto | perfil oficial o metadata de imagen | Conservar URL, tipo, alt, atribución si existe y hash. |
| Intercambio | mapa/listado oficial y convocatoria | Vincular institución destino, país, carrera y vigencia si consta. |
| Modalidad/duración | ficha del programa | No inferir duración a partir de cantidad de materias. |
| Validez/CONEAU | organismo público o documento oficial | Separar número, tipo, fecha y vigencia. |

## Enriquecimientos no verificados

Rankings, empleabilidad comparada, opiniones, costo de vida, seguridad y reputación no están incorporados. Son candidatos futuros, pero necesitan fuentes comparables, licencia adecuada, fecha y metodología. No deben mezclarse con afirmaciones oficiales de la universidad.

---

# 22. Detección automática de faltantes

`audit_completeness.py` ya genera pendientes con entidad, registro, campo, severidad y motivo. Para volverlo genérico se propone que cada adapter declare reglas en vez de codificar una lista exclusiva de UTDT.

## Flags de registro

- `missing_required`: falta un dato necesario para identificar o publicar.
- `missing_recommended`: falta un dato útil pero el registro sigue siendo válido.
- `not_applicable`: el campo no corresponde a esa entidad.
- `not_public`: se buscó y no existe fuente pública comprobada.
- `source_error`: la fuente debería existir pero falló.
- `parse_error`: la fuente respondió, pero no se pudo interpretar.
- `stale`: el dato excedió su ventana de frescura.
- `conflict`: dos fuentes autorizadas discrepan.
- `suspected_schema_change`: estructura o conteo se salió de tolerancia.
- `unverified`: valor descubierto pero aún no validado para publicación.

## Reglas automáticas mínimas

- Campo vacío cuando el contrato lo define como requerido.
- URL inválida, no oficial o que responde `4xx/5xx` repetidamente.
- Fecha de cierre anterior a apertura.
- Duración, costo o carga horaria fuera de rangos configurados.
- Hijo sin padre: materia sin carrera, rol sin persona o comisión sin materia.
- Caída o crecimiento anormal contra la última corrida válida.
- Clave natural repetida con valores incompatibles.
- Registro activo no observado en varias corridas completas.
- Mismo hash de archivo asociado de forma contradictoria.

Los flags deben indicar si son bloqueantes. Un `not_applicable` o `not_public` confirmado no debería inflar indefinidamente el backlog de calidad.

---

# 23. Confidence score

**Estado: propuesto, no implementado.** No debe fingir precisión estadística. Es una regla explicable basada en procedencia, extracción y consistencia.

## Dimensiones sugeridas

| Dimensión | Peso orientativo | Pregunta |
|---|---:|---|
| Autoridad de fuente | 35 | ¿Es una página/API/documento oficial de la entidad? |
| Directitud | 25 | ¿El valor aparece literalmente o fue derivado? |
| Consistencia | 20 | ¿Coincide con otras fuentes oficiales y reglas internas? |
| Frescura | 15 | ¿La fuente corresponde al período vigente? |
| Calidad técnica | 5 | ¿Hubo parseo estructurado y validación sin ambigüedad? |

## Niveles

- **HIGH (85–100):** valor literal de fuente oficial específica, actual y consistente.
- **MEDIUM (60–84):** fuente oficial indirecta, derivación determinística o período no completamente explícito.
- **LOW (1–59):** descubrimiento externo, ambigüedad o dato antiguo; no publicar automáticamente si es material.
- **0 / UNKNOWN:** sin evidencia utilizable.

Ejemplo: una modalidad `Presencial` escrita en la ficha vigente es HIGH. Inferirla porque aparece una dirección física sería LOW y hoy debe quedar pendiente, no cargarse.

---

# 24. Trazabilidad y procedencia

## Lo que existe

- Muchos registros conservan `fuente_url` o URL de perfil.
- Los JSON intermedios preservan lo extraído antes de cargar.
- Git identifica la versión del scraper.
- El catálogo conserva año y semestre.

## Brecha actual

La procedencia es mayormente por registro. No siempre se sabe qué fuente justificó **cada campo**, qué fragmento se leyó ni en qué corrida cambió.

## Modelo propuesto por observación

Cada campo material debería poder apuntar a:

- `entity_type`, `entity_key` y `field_name`;
- valor normalizado y, cuando ayude, valor crudo;
- `source_url` y tipo de fuente;
- fecha/hora de obtención;
- período de vigencia observado;
- adapter y versión/commit;
- método: JSON, HTML, PDF, API o derivación;
- selector, JSONPath o referencia de página;
- hash del documento/respuesta;
- confidence y flags;
- estado: observado, publicado, reemplazado o descartado.

Para datos mutables no se debe sobrescribir sin historia. Una nueva observación puede reemplazar el valor publicado, pero ambas deben quedar auditables.

---

# 25. Exportación

## Formatos

- **JSON:** formato canónico por universidad para inspección, fixtures y reejecución del loader.
- **Base de datos:** formato operacional normalizado para la aplicación.
- **CSV:** exportación plana por entidad para QA y análisis; las relaciones N:M van en archivos separados.
- **Markdown:** reportes humanos de cobertura, cambios, errores y fuentes; no reemplaza el dataset.

## Reglas de exportación

- UTF-8, fechas ISO 8601 y números sin símbolos decorativos.
- IDs estables sólo para las entidades que hoy usan upsert/sincronización estable; claves naturales y `source_id` en exportaciones portables. Los IDs de tablas reconstruidas por corrida deben tratarse como efímeros hasta migrarlas a upsert.
- URLs completas y período explícito.
- `null` distinto de cadena vacía y distinto de `not_applicable`.
- Arrays como arrays en JSON; tablas puente en CSV/base.
- Nunca exportar `SUPABASE_SERVICE_ROLE_KEY` ni otros secretos.

## Ejemplo de registro canónico

Ejemplo simplificado, con campos demostrativos tomados del contrato real y sin completar datos no verificados:

```json
{
  "universidad": "Universidad Torcuato Di Tella",
  "carrera": "Abogacía",
  "materia": {
    "nombre": "Teoría General del Derecho",
    "anio_plan": 1,
    "turno": null,
    "descripcion": null,
    "regimen": null,
    "carga_horaria_semanal": null
  },
  "calidad": {
    "faltantes": ["turno", "descripcion", "regimen", "carga_horaria_semanal"],
    "estado": "parcial"
  }
}
```

El nombre, la carrera y el año del ejemplo corresponden al primer registro del JSON UTDT verificado al redactar este documento. Los `null` son intencionales: no deben convertirse en datos supuestos. La procedencia de esos campos sigue siendo una brecha cuando el registro no trae una URL específica.

---

# 26. Estructura futura de base de datos

## Actual confirmada

La base actual ya separa universidades, localidades, sedes, facultades, carreras, ofertas académicas, ciclos, materias, posgrados, actividades, autoridades, contactos, áreas, personas, roles académicos, catálogo, comisiones, horarios, becas, servicios, extracurriculares, alojamiento, programas internacionales y convenios. Hay además tablas operativas de scraping en el esquema observado.

## Propuesta de evolución

1. `source_documents`: URL, estado HTTP, content type, hash, fecha, almacenamiento y metadatos.
2. `field_observations`: procedencia a nivel campo, valor crudo/normalizado, versión y confidence.
3. `scrape_runs` y `scrape_run_items`: corrida, etapa, resultado, contadores y errores.
4. `data_quality_issues`: flag, severidad, estado, responsable y resolución.
5. `resources`: imagen, PDF, folleto, programa o enlace con hash, alt, licencia y relaciones polimórficas o tablas puente.
6. `entity_aliases`: nombres alternativos e históricos con alcance.
7. `curriculum_versions`: versión y vigencia del plan, en vez de tratar el plan como atemporal.
8. `subject_equivalences`: equivalencias confirmadas con fuente; no similitud inventada.
9. `admission_periods`, `fees` y `scholarship_calls`: separar la entidad estable de su edición temporal.
10. Historial de publicación o modelo temporal para detectar altas, cambios y bajas.

Esto es diseño futuro. Las migraciones SQL pertenecen al repositorio/flujo de base de datos, no deben agregarse a `rumbo-scraper` según la decisión explícita del proyecto.

---

# 27. Roadmap propuesto

## Etapa A — cerrar la segunda universidad

1. Implementar posgrados UdeSA con fuentes y validación.
2. Agregar becas, admisión, servicios, internacional y autoridades UdeSA donde haya fuente pública.
3. Persistir recursos UdeSA cuando el esquema de base esté definido.
4. Crear auditoría parametrizada por universidad.
5. Medir cobertura comparativa UTDT/UdeSA.

**Criterio de salida:** dos adapters reproducibles, idempotentes, auditables y sin datos inventados.

## Etapa B — robustez operativa

1. Corridas y errores persistentes.
2. Snapshots/hashes y detección de cambios.
3. Política de inactivación.
4. Batch, retry y límites por dominio.
5. Automatización con secretos seguros.

**Criterio de salida:** una falla o cambio de estructura se detecta sin publicar una degradación silenciosa.

## Etapa C — modelo común

1. Versiones de planes y períodos.
2. Recursos y procedencia por campo.
3. Estados de faltante y confidence explicable.
4. Taxonomía transversal revisada.
5. Exportadores y panel de calidad.

## Etapa D — expansión

1. Incorporar universidades por prioridad de negocio y disponibilidad de fuentes.
2. Crear generador de scaffold para adapters, sin extracción inteligente.
3. Paralelizar workers y separar staging/publicación.
4. Añadir otros países sólo después de resolver idioma, títulos, moneda y autoridades educativas.

---

# 28. Próximo paso exacto

> **COMPLETADO el 22-09-2026.** Los 41 posgrados que publica el índice oficial
> `https://udesa.edu.ar/posgrados` se descubren, extraen, validan y cargan. Dos
> corridas consecutivas produjeron contenido idéntico. Los conteos de este
> documento ya no deben leerse como fuente: ejecutar
> `python -m rumbo_scraper.manifest`, que los genera desde los artefactos.
>
> Diferencias respecto de lo planificado abajo:
>
> - El descubrimiento no necesita enumerar rutas a mano: el índice publica una
>   `EntityList` de entidades `Graduate` con nombre, URL y departamento.
> - Se extraen `materias` de posgrado desde `graduateSyllabus.stages[].body`:
>   612 filas en 27 de los 41 programas. El plan es prosa HTML, así que el
>   nombre se limpia con reglas explícitas que cortan sólo lo que la fuente
>   marca (atribución docente, frecuencia de cursada, tamaño de archivo,
>   descripción anexada) y se descartan las instrucciones. Los 14 programas sin
>   filas no publican plan o no publican lista.
> - **Límite conocido:** unas 30 filas de la Diplomatura DETE son enunciados de
>   competencias ("La capacidad de construir estrategias...") publicados dentro
>   de los "Ejes de trabajo", no nombres de materia. No se filtran porque toda
>   regla por forma probada también eliminaba materias reales como "La prueba de
>   los delitos sexuales". Separarlas requiere decidir qué etiquetas de stage no
>   son listas de materias.
> - `titulo_otorgado`, `requisito_titulo_previo` y `requiere_tesis_trabajo_final`
>   quedan nulos: no aparecen en ningún campo estructurado de las páginas.
> - Apareció una novena unidad académica, Departamento de Matemática y Ciencias,
>   que el catálogo de grado no cubría.
>
> **Próximo paso ahora:** auditoría parametrizada por universidad (Etapa A,
> punto 4), que sigue siendo exclusiva de UTDT.

El plan original era **completar posgrados de UdeSA de manera determinística**, porque:

- UdeSA grado ya corre end-to-end.
- El menú/dataset de la web ya permite descubrir URLs de posgrado.
- Es el faltante más visible para comparar ambas universidades.
- Obliga a validar que el contrato común soporta otra institución sin inventar campos.

## Implementación concreta

1. Partir de `https://udesa.edu.ar/estudia-en-udesa`, capturar `#__NEXT_DATA__` con el mecanismo Playwright ya implementado y enumerar las rutas que la navegación oficial clasifique como posgrado. El conteo esperado es **NO DEFINIDO** hasta guardar ese primer fixture; no fijar un número manual.
2. Extender `rumbo_scraper/parsers/udesa.py` para distinguir grado y posgrado y extraer sólo valores literales, configurados explícitamente o derivados por reglas testeadas.
3. Extender `rumbo_scraper/spiders/udesa.py` para recorrer exclusivamente URLs oficiales descubiertas y tolerar fallas parciales sin publicar un dataset vacío.
4. Extraer como mínimo nombre, tipo, unidad, URL, descripción, modalidad, duración, título y requisitos cuando aparezcan explícitamente.
5. Registrar recursos públicos asociados en el JSON, sin intentar guardarlos todavía en una tabla inexistente/no acordada.
6. Ampliar `rumbo_scraper/validators/udesa.py` y `tests/test_udesa.py` con un fixture real sanitizado que incluya índice, detalle completo, detalle parcial y link roto.
7. Extender `rumbo_scraper/database/load_udesa.py` para `posgrados`, con clave natural `universidad + nombre_programa`, upsert e idempotencia; verificar previamente que el esquema compartido admite todos los campos.
8. Ejecutar primero preview, revisar conteos, duplicados, URLs, distribución por tipo y faltantes, y recién después aplicar.
9. Reejecutar y exigir mismos conteos/IDs de posgrados; una caída mayor al umbral acordado debe bloquear publicación. El umbral exacto queda **NO DEFINIDO** hasta obtener el baseline inicial.
10. Incorporar UdeSA a una versión genérica de la auditoría.

**Definición de terminado:** todas las URLs de posgrado descubiertas están clasificadas como cargadas, excluidas con motivo o fallidas; no hay claves naturales duplicadas; el preview y dos aplicaciones consecutivas son idempotentes; cada valor publicado conserva URL de fuente; los campos ausentes quedan `null` y aparecen en auditoría.

## Comandos esperados cuando esté implementado

```bash
cd ~/Desktop/rumbo-scraper
source .venv/bin/activate

python -m unittest discover -v
python -m rumbo_scraper.spiders.udesa
python -m rumbo_scraper.database.load_udesa
python -m rumbo_scraper.database.load_udesa --apply
```

No crear SQL dentro de este repositorio. Si hacen falta tablas o columnas, entregar el SQL por separado y aplicarlo en el proyecto de base correspondiente.

---

# 29. Preguntas abiertas

1. ¿Cuál es la definición formal del MVP por universidad: grado solamente o también posgrado, vida estudiantil e internacional?
2. ¿Qué campos vacíos deben mostrarse al usuario como “sin información pública” y cuáles deben ocultarse?
3. ¿Dónde se versiona el esquema y el SQL de Supabase si está prohibido guardarlo en este repo?
4. ¿Cuál será el modelo definitivo de recursos y archivos?
5. ¿Se almacenan binarios propios o sólo URLs oficiales y hashes?
6. ¿Qué frecuencia y período histórico requiere cada universidad?
7. ¿Cuándo una entidad ausente se inactiva: una, dos o más corridas completas?
8. ¿Cómo se revisan conflictos entre sitio institucional, catálogo y organismo público?
9. ¿Qué granularidad tendrá la procedencia: sólo campos críticos o todos?
10. ¿Las áreas temáticas serán taxonomía institucional, transversal o ambas?
11. ¿Cómo se representarán dobles titulaciones, carreras compartidas y múltiples sedes?
12. ¿Se publicarán docentes sin perfil público individual, sólo con nombre y comisión?
13. ¿Qué tratamiento legal/licencia tendrán fotos, folletos y programas descargados?
14. ¿Las equivalencias entre materias serán únicamente oficiales o también sugerencias algorítmicas claramente separadas?
15. ¿Cuál es la próxima universidad después de UdeSA y qué prioridad de datos tiene?

---

# 30. HANDOFF PARA CLAUDE / CODEX / OTRA IA

## Qué debe saber antes de tocar el proyecto

- El scraper vive en `~/Desktop/rumbo-scraper`; no confundirlo con la app web.
- El objetivo es obtener datos públicos verificables de universidades argentinas sin LLMs ni consumo de tokens en producción.
- UTDT tiene el adapter más completo; UdeSA grado es el segundo adapter.
- `.env` contiene credenciales locales y está ignorado. Nunca leerlas en voz alta, imprimirlas, copiarlas al chat ni versionarlas.
- La carga usa service role/secret sólo en backend local o automatización segura.
- No se inventan datos ni se completan inferencias débiles.
- No se guarda SQL en este repo.
- No se deben romper IDs de entidades principales ni duplicar registros al reejecutar. **Limitación:** varias tablas de detalle se borran y reinsertan; sus IDs no deben ser consumidos como identificadores permanentes.

## Bootstrap y estado verificable

```bash
cd ~/Desktop/rumbo-scraper
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -v
```

Al redactar este documento, la suite confirmada tenía **35 tests aprobados**. Volver a ejecutar antes de cambiar código. Para regenerar datos, ejecutar después los spiders antes de sus loaders, usando los comandos del Apéndice C. La carga completa no es reproducible desde un clon limpio sin un `.env` válido y sin el esquema compatible de Supabase. **NO DEFINIDO/P0:** todavía falta identificar el repositorio o mecanismo único que versiona ese esquema, sus enums y constraints; el SQL no pertenece a este repo por decisión explícita.

## Archivos clave

- `rumbo_scraper/contracts.py`: contrato de dataset.
- `rumbo_scraper/settings.py`: configuración desde entorno.
- `rumbo_scraper/parsers/utdt.py`: transformación UTDT principal.
- `rumbo_scraper/parsers/utdt_catalog.py`: catálogo/horarios/contenidos.
- `rumbo_scraper/parsers/udesa.py`: transformación UdeSA.
- `rumbo_scraper/spiders/*.py`: adquisición y orquestación por fuente.
- `rumbo_scraper/validators/*.py`: invariantes antes de guardar.
- `rumbo_scraper/database/load_*.py`: preview y aplicación a Supabase.
- `rumbo_scraper/database/audit_completeness.py`: backlog de faltantes UTDT.
- `data/*.json`: salidas locales ignoradas y no disponibles en un clon; no asumir que están frescas sin mirar fecha/corrida. **PENDIENTE:** versionar un manifiesto sin datos sensibles con commit, hash, fecha y conteos de cada artefacto.
- `tests/`: regresiones determinísticas.

## Último estado funcional resumido

- UTDT: grado, posgrado, catálogo, personas/roles, vida estudiantil e intercambio cargados; persisten faltantes documentados.
- UdeSA: 18 carreras, 8 facultades/unidades, 4 sedes, 31 ofertas, 681 materias y 53 recursos en la corrida verificada; se cargó el núcleo, no los recursos.
- Supabase: integración real probada e idempotente en las rutas existentes.
- Próximo desarrollo: posgrados UdeSA y auditoría multiuniversidad.

## Protocolo de cambio

1. Leer este documento, `README.md`, el contrato y el adapter relevante.
2. Verificar `git status`; preservar cambios del usuario.
3. Capturar/guardar un fixture representativo sin secretos ni datos internos.
4. Escribir o ajustar tests primero para la estructura nueva.
5. Implementar extracción determinística con URL de procedencia.
6. Validar y generar JSON.
7. Ejecutar loader sin `--apply`.
8. Revisar conteos, diferencias y faltantes.
9. Aplicar sólo si la revisión es razonable.
10. Reejecutar para comprobar idempotencia.
11. Auditar completitud y documentar lo no público.

## Restricciones duras

- No usar páginas privadas ni credenciales académicas.
- No sortear controles de acceso.
- No convertir una hipótesis en hecho.
- No borrar registros en masa por una respuesta parcial.
- No hacer `push` de `.env`, JSON sensibles, cachés o entornos virtuales.
- No incorporar SQL al repositorio.
- No usar IA generativa en el pipeline salvo que el dueño del proyecto cambie explícitamente esa decisión.

---

# Apéndice A. Línea de tiempo técnica resumida

| Hito | Resultado |
|---|---|
| Estructura inicial | Paquete Python, entorno, `.env.example`, Supabase y carpetas base. |
| UTDT inicial | Carreras, materias, posgrados y loader. |
| Correcciones de conexión | Normalización de URL y uso correcto de secret/service role. |
| Autoridades y directorio | Personas y roles N:M; cientos de perfiles/roles. |
| Separación de responsabilidades | SQL retirado del scraper. |
| Vida estudiantil | Becas, servicios, extracurriculares, alojamiento e internacional. |
| Intercambio | 671 vínculos por programa. |
| Catálogo | Materias catálogo, comisiones, horarios, contenidos y docentes. |
| Auditoría | Pendientes priorizados y sucesivos refinamientos. |
| Posgrados | Perfiles, títulos, modalidad, duración, planes y admisión. |
| UdeSA | Segundo adapter determinístico con Playwright y `__NEXT_DATA__`. |

# Apéndice B. Glosario de estados

- **Confirmado:** existe evidencia en código, salida local, base consultada o conversación.
- **Inferido:** conclusión razonable a partir de evidencia, pero no afirmación literal de la fuente.
- **Hipótesis:** idea por validar; no debe publicarse.
- **Pendiente:** trabajo o dato faltante identificado.
- **No definido:** falta decisión de producto/esquema.
- **Descartado:** enfoque evaluado y rechazado para el alcance actual.
- **No aplica:** el campo no corresponde semánticamente al registro.
- **No público:** se investigó y no se encontró una fuente pública verificable.

# Apéndice C. Comandos operativos actuales

## UTDT principal

```bash
python -m rumbo_scraper.spiders.utdt
python -m rumbo_scraper.database.load_utdt
python -m rumbo_scraper.database.load_utdt --apply
```

## UTDT catálogo

```bash
python -m rumbo_scraper.spiders.utdt_catalog
python -m rumbo_scraper.database.load_utdt_catalog
python -m rumbo_scraper.database.load_utdt_catalog --apply
```

## UdeSA

```bash
python -m rumbo_scraper.spiders.udesa
python -m rumbo_scraper.database.load_udesa
python -m rumbo_scraper.database.load_udesa --apply
```

## Auditoría

```bash
python -m rumbo_scraper.database.audit_completeness
python -m rumbo_scraper.database.audit_completeness --apply
```

Usar `--apply` sólo después de revisar el preview y con credenciales válidas en `.env`.
