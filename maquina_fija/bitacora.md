# Bitácora de la máquina fija

## 2026-10-22 — UNQ (Universidad Nacional de Quilmes)
- Elegida por GBA: 38 de 43 carreras de grado/pregrado sin plan (catálogo del 16/10). El lector de UNQ que había (`plan_unq`) no tomaba ninguna.
- Nuevo lector `planes_sitios.plan_unq_cursos`: las tablas por ciclo y núcleo (columna de cursos + créditos). Deja afuera las electivas y los lugares a elegir ("Curso Electivo 1", "Créditos en…"), y no lee la página si los créditos de una tabla no dan su total, si hay orientaciones o si una tabla sigue sin encabezado.
- Cargadas en la base del scraper (134 materias, sin año: UNQ no publica años): Lic. en Historia (28), Lic. en Educación (28), Prof. de Educación, Prof. de Ciencias Sociales y Prof. de Comunicación Social (26 c/u). Cada nombre comprobado literalmente contra la página oficial.
- Quedan pendientes: Informática (tablas cortadas sin encabezado + orientación), Comunicación Social y Ciencias Sociales (dos orientaciones), Prof. de Historia (resumen de créditos con tabla de continuación), Arquitectura Naval y varias tecnicaturas (bolsas de complementarias que no suman el total), tecnicaturas de música (16 materias obligatorias, menos que el mínimo de 20 sin año), Biotecnología, Turismo y Comercio Internacional (la página no lista materias por tabla).
- Producción: sin credenciales en esta máquina → UNQ queda "listo para cargar".
- Ojo: `data/planes_documentos.json` apareció reemplazado por una copia del 13/10 a mitad de la sesión (algo sincroniza `data/`); se repitió la vista previa antes de aplicar.

## 2026-10-22 (tarde) — Austral: lector de folletos
- Cerrado el arreglo que había quedado sin commitear: `plan_folleto_columnas` pega la segunda línea de un nombre cortado por la celda y descarta "Optativa" suelta y la nota debajo; `_parece_el_plan_entero` rechaza nombres que terminan en coma o con paréntesis abierto. Prueba nueva en `tests/test_plan_folleto_austral.py`; 871 pruebas OK.
- La "CAYÓ" de Austral en vigilancia (materias 1375→1051) viene de este lector más estricto, no de un cambio del sitio. Palermo (carreras 73→66, posgrados 18→14) sí es un cambio a revisar en el próximo ciclo antes de confiar en esa corrida.
- Nada cargado a producción (sin credenciales).

## 2026-10-22 (noche) — Palermo: revisión de la "CAYÓ"
- Comparé `data/vigilancia/palermo_completo.json` con `data/palermo_completo.json` (23/09). Los nombres con el sufijo "Conocé la carrera" ahora salen limpios (mejora, no pérdida).
- Sí desaparecieron 9 carreras: Actuación Profesional, Escribanía, Lic. en Arte, en Ciencias del Comportamiento, en Humanidades y Ciencias Sociales, en Periodismo, en Psicología, en Relaciones Internacionales y en Relaciones Internacionales y Ciencia Política. Aparecen 3 nuevas (Diseño y Estéticas de la Moda, Diseño y Negocios de la Moda, Lic. en Administración de Sistemas: ciclo de complementación).
- No sé si es un cambio del sitio o del lector: la corrida de vigilancia no se carga. Pendiente: abrir el listado oficial de Palermo y confirmar si esas 9 siguen publicadas antes de tocar el catálogo.

## 2026-10-22 (noche, 2) — Palermo: "CAYÓ" resuelta
- Comparando por URL (no por nombre) las 75 carreras del 23/09 contra las 74 de la corrida de vigilancia: coinciden salvo una (Lic. en Administración de Sistemas y Empresas, URL `.../licenciatura-administracion-sistemas-y-empresas/`, que sigue respondiendo 200 pero ya no sale del listado; la corrida trae una de ciclo de complementación nueva).
- Las "9 desaparecidas" eran un artefacto de nombres: el sufijo "Conocé la carrera" ya no se arrastra. No es pérdida de datos; el catálogo no se toca.
- Pendiente (menor): confirmar si esa carrera se renombró en el sitio. Nada cargado a producción.

## 2026-10-22 (madrugada) — UB: "CAYÓ" resuelta en parte
- Posgrados 13→0: el sitio ahora enlaza los posgrados con el prefijo `/index.php/` y `discover_programmes` los descartaba. Arreglado (se quita el prefijo y la URL queda canónica); prueba nueva en `tests/test_ub.py`. Re-corrida de vigilancia: 12 posgrados (el 13.º, Maestría en Traducción, queda por revisar), 872 pruebas OK.
- Carreras 37→25: las 10 de modalidad virtual (FEDEV, ciclos de complementación y tecnicaturas) siguen en el sitio (200) pero sus páginas ya no traen la ficha con título/duración/materias; el lector las excluye ("no publica datos"). Es un cambio del sitio, no del lector. El catálogo (corrida del 10/10) no se toca; si se vuelve a exportar UB hay que no reemplazar esas 10 por nada.
- Nada cargado a producción (sin credenciales).

## 2026-10-22 (noche, 3) — UBA: "CAYÓ" revisada
- Posgrados 592→394: faltan los de Psicología, Ciencias Médicas, Veterinarias y Farmacia (`indices_de_posgrado_vacios`: 7 índices). Comprobé con una sola petición cada uno: Psicología responde 403 (bloqueo, no se evade), Médicas no conecta, Farmacia da 503; Veterinarias publicó el índice vacío. Es el sitio, no el lector. Las materias 336→160 vienen de lo mismo (planes que no se descargaron).
- El catálogo de UBA (corrida del 23/09) no se toca; no re-importar UBA desde la corrida de vigilancia. Psicología queda como "bloqueada" (403) para posgrados. Reintentar Médicas/Farmacia en una próxima rotación.
- Nada cargado a producción (sin credenciales).

## 2026-10-22 (noche, 4) — UNLP Periodismo: tecnicaturas
- Nuevo lector `planes_sitios.plan_perio_unlp` (páginas "Asignaturas ..." de perio.unlp.edu.ar: un encabezado por año, materias por renglón; deja afuera el "Tramo inicial" y las optativas a elegir; no lee planes por ciclos). Prueba en `tests/test_plan_perio_unlp.py`.
- Cargadas en la base del scraper por `planes_manuales` (cada nombre comprobado contra la página oficial): Comunicación Digital (24), Periodismo Deportivo plan 2017 (29), Comunicación Pública y Política (25). Hoja en `data/planes_perio_unlp.csv`.
- Pendientes de Periodismo: Lic. en Comunicación Social (dos orientaciones, planes 1998 y 2017 juntos), Profesorado (electivas por tramo y ciclos), Tecnicatura en Comunicación Popular (el plan 2013 va por ciclos; hay reforma 2017 sin página de materias).
- Producción: sin credenciales → UNLP "listo para cargar".

## 2026-10-22 (noche, 5) — UCEMA: "CAYÓ" resuelta
- Carreras 16→14: el sitio movió Actuario e Ingeniería en Inteligencia Artificial de `/grado/` a `/carrera-grado/` (siguen publicadas con título, duración y reconocimiento) y `discover_programmes` solo miraba `/grado/`. Arreglado; prueba nueva en `tests/test_cinco_universidades.py`.
- Re-corrida de vigilancia: 17 carreras (las 16 anteriores + "BA - Artes Liberales y Ciencias", 4 años, nueva). "BA College UCEMA" no publica ficha y queda excluida. 876 pruebas OK.
- No se exportó ni se tocó el catálogo: había un `verificar_catalogo` ajeno corriendo (PID 829774). UCEMA queda para re-exportar cuando termine. Nada cargado a producción.
