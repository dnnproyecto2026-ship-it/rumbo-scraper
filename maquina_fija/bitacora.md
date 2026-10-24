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

## 2026-10-22 (noche, 6) — Cierre de sesión
- Commiteado el trabajo de UNLP Periodismo (lector `plan_perio_unlp`, prueba, hoja CSV) que había quedado suelto; 876 pruebas OK.
- No se exportó: `verificar_catalogo` ajeno sigue corriendo (PID 829774). Pendiente exportar UNLP, UNQ y UCEMA cuando termine. Siguiente en cola: UNLP Trabajo Social.

## 2026-10-22 (noche, 7) — UNLP Trabajo Social
- El sitio de la facultad se rehízo (las URL viejas dan 404); los planes están como PDF en `trabajosocial.unlp.edu.ar/planes-de-estudio/`. Texto extraído con `pdftotext`; cada nombre comprobado contra el documento por `planes_manuales`.
- Cargados en la base del scraper: Lic. en Trabajo Social (30 materias) y Profesorado en Trabajo Social (38). Hojas en `data/planes_unlp_trabajo_social.csv` y `data/planes_unlp_prof_trabajo_social.csv` (cargado_por "IA operador"; se dejaron afuera "Trayecto Optativo", idioma y trabajo final: no son materias con nombre).
- Pendiente en esa facultad: Tecnicatura en Gestión comunitaria del riesgo y Lic. en Fonoaudiología (PDF en la misma página), si están en el catálogo sin plan.
- No se exportó: `verificar_catalogo` ajeno sigue corriendo (PID 829774). Sin credenciales de producción.

## 2026-10-22 (noche, 8) — UNLP Trabajo Social: Tecnicatura y Fonoaudiología
- Cargados en la base del scraper por `planes_manuales` (nombres comprobados contra los PDF oficiales de trabajosocial.unlp.edu.ar): Tecnicatura en Gestión Comunitaria del Riesgo (21 materias) y Lic. en Fonoaudiología (42; se dejó afuera la certificación de idioma). Hojas en `data/planes_unlp_tec_gestion_riesgo.csv` y `data/planes_unlp_fonoaudiologia.csv`.
- Facultad de Trabajo Social de UNLP completa. Sin credenciales de producción → "listo para cargar". Exportación pendiente: `verificar_catalogo` ajeno (PID 829774) sigue corriendo.

## 2026-10-22 (noche, 9) — Vigilancia: UDESA, UMSA, USAL revisadas
- UDESA "CAYÓ": la corrida nueva ya no trae la entidad "Sede Nordelta" (sedes 4→3, localidades 3→2, falta Tigre), aunque Nordelta sigue nombrada en 18 lugares del JSON (ofertas). Parece un cambio de la página de sedes; el catálogo no se toca. Para revisar: si el sitio dejó de publicar la dirección de Nordelta (Av. de los Fundadores 55).
- UMSA 26→23 y USAL 72→69 carreras: bajas sin "CAYÓ"; sin revisar por URL todavía (hacerlo como con Palermo). Catálogo intacto.
- No se exportó: `verificar_catalogo` ajeno (PID 829774) sigue corriendo. Sin credenciales de producción.

## 2026-10-22 (noche, 10) — Vigilancia: UMSA y USAL revisadas
- UMSA 26→23: no es baja. El sitio renombró los 3 ciclos ("Ciclo de Complementación Curricular" → "Ciclo de Licenciatura"); siguen publicados (API `carrera`). Al re-importar, los nombres cambian: cuidar de no duplicar.
- USAL 72→69 era un hueco del lector: `discover_programmes` solo tomaba enlaces cuyo nombre empieza con "Licenciatura/Ingeniería/…". Ahora, en el índice de grado, toma todo enlace dentro de `.propuesta_nombre`; prueba nueva. Re-corrida: 80 carreras (nuevas: Agronomía, Actuario, Corrector Literario, Martillero, Notariado ciclo, Higiene y Seguridad ciclo, 2 Ciclo Pedagógico; Dermatocosmiatría pasa a llamarse "Dermatocosmiatría (Tecnicatura)"). Veterinaria y Odontología siguen. 877 pruebas OK.
- Catálogo no tocado ni exportado (`verificar_catalogo` ajeno PID 829774 sigue). USAL: 8 carreras nuevas para cargar en el próximo ciclo (normalizar el nombre de la tecnicatura al re-importar). Sin credenciales de producción.

## 2026-10-22 (noche, 11) — Vigilancia: UTDT y UTN revisadas
- UTDT: materias 839→751 = la Maestría en Finanzas perdió sus 88 materias en la corrida (el log avisa "6 páginas no se pudieron descargar"); las 13 carreras siguen. Falla de descarga, no baja: catálogo intacto. Reintentar UTDT en la próxima rotación.
- UTN 99→98: se perdió la oferta de Ing. Eléctrica en FRCon (Concepción del Uruguay). La URL oficial `?page_id=789` ahora responde 301 a `/ingenieria-electrica/` (página movida). Pendiente: que el spider de UTN siga/descubra la URL nueva; no re-importar UTN desde esa corrida hasta entonces.
- Sin cambios de código, sin exportar (`verificar_catalogo` ajeno PID 829774 sigue). Sin credenciales de producción.

## 2026-10-22 (noche, 12) — UTN: "Ingeniería Eléctrica" FRCon aclarada
- Corregido lo anotado en (11): no es un hueco del lector ni hace falta seguir la redirección de la página. El spider lee el endpoint de catálogo de utn.edu.ar y la corrida nueva ya no trae la carrera "Ingeniería Eléctrica" (id del catálogo); sin errores de descarga. La oferta anterior era solo un enlace `?page_id=789` sin sede ni modalidad. "Ingeniería en Energía Eléctrica" sigue completa (plan y 12 sedes). Cambio de la fuente: sin código.
- UTN 98 carreras queda como base válida; al re-importar, la oferta de Eléctrica FRCon desaparece (la fuente ya no la publica). Sin exportar (`verificar_catalogo` ajeno PID 829774 sigue, 2 h 12 min). Sin credenciales de producción. 877 pruebas OK.

## 2026-10-22 (noche, 13) — UTDT: Maestría en Finanzas, causa aclarada
- Reintento de UTDT (`data/vigilancia/utdt_reintento.json`): mismo resultado, 751 materias; Finanzas 88→0. No es descarga fallida: la ficha (`id_contenido=7421`) y su página anexa (`618`, admisión) responden 200 y ya no traen lista de materias ni enlace al plan (solo dice "más de 70 materias electivas"). Las otras 8 páginas con error son 404/500 o desconexiones sueltas sin relación (las dos desconexiones respondieron 200 al reintentar).
- Cambio del sitio, no del lector: las 88 materias del baseline no se pueden volver a comprobar contra la fuente actual. Catálogo intacto; no re-importar UTDT desde la corrida nueva sin conservar las de Finanzas (o decidir si se retiran por no estar publicadas). Sin código nuevo; 877 pruebas OK.
- Sigue sin exportar: `verificar_catalogo` ajeno (PID 829774, 2 h 20 min). Sin credenciales de producción.

## 2026-10-22 (noche, 14) — UNLP Odontología: tecnicaturas
- Cargadas por `planes_manuales` (nombres comprobados contra los PDF oficiales de folp.unlp.edu.ar): Tec. en Asistencia Odontológica (24 materias) y Tec. en Prótesis de Laboratorio Odontológico (23). Los planes no indican año por materia: van sin año. Hoja en `data/planes_unlp_odontologia_tec.csv`.
- Pendiente en UNLP Odontología: la carrera de Odontología (6 años); su plan no está en el sitio de la facultad que leí (`/caratulacar/` solo trae logos). Siguiente: buscar el plan en `/creacion/` o en el sitio de la UNLP.
- Sin exportar (`verificar_catalogo` ajeno PID 829774 sigue). Sin credenciales de producción.

## 2026-10-22 (noche, 15) — UNLP Odontología: carrera de grado
- Plan leído de la tabla oficial de materias por año de la facultad (`folp.unlp.edu.ar/caratulacar/carrera/`, 1.º a 5.º año); `planes_manuales` comprobó cada nombre contra esa página. 60 materias cargadas en la base del scraper (hoja `data/planes_unlp_odontologia.csv`). Los nombres llevan "A/B" tal como los publica la facultad.
- Aviso: el catálogo tiene duración 6 años para Odontología, pero la tabla de la facultad llega a 5.º año (con las PPS). No se tocó la duración; revisar contra el plan de estudios oficial antes de cambiarla.
- UNLP Odontología completa. Sin exportar (`verificar_catalogo` ajeno PID 829774 sigue). Sin credenciales de producción.

## 2026-10-22 (noche, 16) — UNLP: Exactas bloqueada; Psicología (Licenciatura)
- UNLP Exactas: no se pudo leer. `www.exactas.unlp.edu.ar` agota el tiempo (curl código 28) y `exactas.unlp.edu.ar` responde con un certificado TLS que no coincide con el dominio (por http da 404). No se evadió (sin saltear la verificación del certificado); queda "bloqueada" por el sitio, reintentar en otra rotación. 9 ofertas de Exactas siguen sin plan.
- Cargada por `planes_manuales` la Lic. en Psicología (34 materias, cada nombre comprobado contra el PDF oficial del plan en psico.unlp.edu.ar; se dejó afuera capacitación en idioma y el TIF). Hoja en `data/planes_unlp_psicologia.csv`. La búsqueda web solo indicó dónde estaba el PDF.
- Pendiente: Profesorado en Psicología (plan propio, no buscado todavía). Sin exportar (`verificar_catalogo` ajeno PID 829774 sigue). Sin credenciales de producción.

## 2026-10-22 (noche, 17) — UNLP: Profesorado en Psicología, no cargado
- El plan oficial (`wp-psico-admin.psico.unlp.edu.ar/.../2025/06/Plan-de-estudio-profesorado.pdf`, 7 págs.) es un escaneo sin texto; la página web de la carrera se arma por JavaScript y no se puede leer con el lector del repo. Por OCR: nombres con errores ("Psicología ¡i", "Evolutiva !"), la pág. 7 sale vacía, 5.º año incompleto y 4.º año con materias a elegir entre dos. No se pueden comprobar todos los nombres → no se cargó (un plan malo es peor que ninguno).
- Pendiente: reintentar con otro render/OCR de las págs. 5–7, o esperar un plan con texto. Sin exportar (`verificar_catalogo` ajeno PID 829774 sigue). Sin credenciales de producción.

## 2026-10-22 (noche, 18) — Exportación al día
- Sin procesos ajenos. `verificar_catalogo` → `exportar_catalogo` corridos; termina con `Archivo: data/catalogo_depurado.json`. Incluye UNLP (Odontología, Psicología), UNQ y UCEMA. 877 pruebas OK.
- Sin credenciales de producción: sigue "listo para cargar". Siguiente: UNLP Económicas/Agrarias/Humanidades.

## 2026-10-22 (noche, 19) — UNLP Económicas: las 2 carreras sin plan
- Cargadas por `planes_manuales` (cada nombre comprobado contra la página oficial econo.unlp.edu.ar): Tecnicatura en Cooperativismo (19 materias, Plan de Estudios VII, años 1–3) y Ciencia de Datos en Organizaciones (28, años 1–4). En CDO se dejó afuera la "Optativa" (sin nombre de materia). Hojas: `data/planes_unlp_cooperativismo.csv`, `data/planes_unlp_cdo.csv`.
- UNLP Económicas completa. Exportación/verificación corridas al final del ciclo. Sin credenciales de producción. Siguiente: UNLP Agrarias (4) y Humanidades (11).

## 2026-10-22 (noche, 20) — UNLP Agrarias: Tec. en Agroecología
- Cargada por `planes_manuales` (19 materias, 1.º–3.º año; cada nombre comprobado contra el PDF oficial del Plan 1 en agro.unlp.edu.ar). Hoja: `data/planes_unlp_agroecologia.csv`.
- No cargadas (PDF del plan escaneado, sin texto): Ing. Agronómica (Plan 2023), Ing. Forestal y Tec. en Cultivos Protegidos. El OCR de Agronómica sale legible pero con errores ("Inegrción", "Agrarias", cortes) y la página de Materias del sitio mezcla planes viejos y nuevo sin año → no se puede comprobar cada nombre. Pendientes con motivo. Falta también Tec. Sup. en Producción Agropecuaria (sin facultad en el catálogo).
- Exportación/verificación lanzadas al final del ciclo. Sin credenciales de producción. Siguiente: UNLP Humanidades (11).

## 2026-10-23 — Cadena de exportación del ciclo 20 completada
- `exportar_catalogo` → `verificar_catalogo` → `exportar_catalogo` corridos en segundo plano, sin errores; ambas exportaciones terminan con `Archivo: data/catalogo_depurado.json`. Incluye la Tec. en Agroecología de UNLP. 877 pruebas OK.
- Sin credenciales de producción: sigue "listo para cargar". Siguiente: UNLP Humanidades (11).

## 2026-10-23 (2) — UNLP Humanidades: 5 carreras de Lenguas Modernas
- Los planes de FaHCE están como PDF con texto en la página de cada carrera (`.../deptos/<depto>/carreras/<carrera>`). Cargadas por `planes_manuales` (cada nombre comprobado contra el PDF oficial): Prof. Lengua y Literatura Inglesas (21), Trad. Público Nacional Inglés (23), Prof. Lengua y Literatura Francesas (20), Trad. Público Nacional Francés (22), Prof. en Portugués (28). Hoja `data/planes_unlp_lenguas.csv`.
- Solo materias obligatorias, sin año de la tabla "sugerido" movido: las optativas ("a elegir entre") y las capacitaciones en idiomas quedan afuera y está anotado en la hoja.
- Pendiente en Humanidades (PDF con texto ya identificado): Lic. Inglés Ling./Lit., Lic. Francés Ling./Lit. (régimen de licenciaturas 2012 + plan 2016, hay que leerlos), Lic. Bibliotecología, Lic. Cs. de la Educación. Ojo: las hojas de Geografía/Historia/Filosofía/Letras/Sociología del catálogo ya tenían materias en la base (mi primer conteo del JSON era erróneo: las materias no vienen dentro de cada carrera).
- Exportación/verificación lanzadas. Sin credenciales de producción.

## 2026-10-23 (3) — UNLP Humanidades: Lic. en Bibliotecología y Ciencia de la Información
- Cargada por `planes_manuales` (24 materias, 1.º–4.º año; cada nombre comprobado contra el PDF de correlatividades de fahce.unlp.edu.ar; el año sale del PDF de tramo sugerido). Hoja `data/planes_unlp_biblio.csv`. Afuera: capacitaciones en idioma, Seminarios 1–3 a elegir y práctica/tesina.
- Pendiente en Humanidades: Lic. Inglés Ling./Lit., Lic. Francés Ling./Lit., Lic. Cs. de la Educación. El Profesorado en Bibliotecología ya tenía 28 materias.
- `verificar_catalogo` (PID 972835, mío) sigue corriendo; la cadena exportará al terminar e incluirá esta carrera. Sin credenciales de producción.

## 2026-10-23 (4) — UNLP Humanidades: Lic. en Cs. de la Educación
- Cargada por `planes_manuales` (23 materias, 1.º–4.º año; cada nombre comprobado contra el PDF oficial del plan A2002 en fahce.unlp.edu.ar). Hoja `data/planes_unlp_cseducacion.csv`. Afuera: Didáctica a elegir (3.º), capacitaciones en informática e idiomas y 5.º año (tres orientaciones, optativas, tesina). Duración del catálogo sin tocar.
- Pendiente en Humanidades: Lic. Inglés Ling./Lit., Lic. Francés Ling./Lit., Profesorado en Cs. de la Educación (no mirado).
- La cadena de exportación (`verificar_catalogo` PID 972835, mío) sigue corriendo; exportará al terminar e incluirá esta carrera. Sin credenciales de producción.

## 2026-10-23 (5) — UNLP Humanidades: Lic. en Inglés (Orientación Lingüística)
- Cargada por `planes_manuales` (17 materias, 1.º–5.º año; cada nombre comprobado contra el PDF oficial del Plan 2016 en fahce.unlp.edu.ar). Hoja `data/planes_unlp_ingles_ling.csv`. Afuera: electivas a elegir, seminarios de licenciatura, tesina, capacitaciones en idioma e "Introducción a los Estudios del Lenguaje y de la Comunicación" (el PDF la abrevia y no se puede comprobar el nombre literal).
- Pendiente en Humanidades: Lic. Inglés Orientación Literaria, Lic. Francés (ambas orientaciones), Prof. Cs. de la Educación. Las PDFs están en las páginas de carrera (`.../carreras/<carrera>/@@edit/...@@download/0`).
- `verificar_catalogo` (PID 972835, mío) sigue corriendo; la cadena exportará al terminar. Sin credenciales de producción.

## 2026-10-23 (6) — UNLP Humanidades: Lic. en Inglés (Orientación Literaria)
- Cargada por `planes_manuales` (17 materias, 1.º–5.º año; cada nombre comprobado contra el PDF oficial del Plan 2016 en fahce.unlp.edu.ar). Hoja `data/planes_unlp_ingles_lit.csv`. Afuera: electivas/optativas a elegir, seminarios de licenciatura, tesina, capacitaciones en idioma e "Introducción a los Estudios del Lenguaje y de la Comunicación" (nombre abreviado en el PDF).
- Pendiente en Humanidades: Lic. Francés (ambas orientaciones), Prof. Cs. de la Educación. `verificar_catalogo` (PID 972835, mío) sigue corriendo; exportación pendiente de su fin. Sin credenciales de producción.

## 2026-10-23 (7) — UNLP Humanidades: Lic. en Francés (Lingüística y Literaria)
- Cargadas por `planes_manuales` (14 materias cada una, 1.º–5.º año; cada nombre comprobado contra el PDF oficial del Plan 2016 en fahce.unlp.edu.ar, enlace `download/1`; el `download/0` es el Régimen de Licenciaturas, no el plan). Hojas `data/planes_unlp_frances_ling.csv` y `data/planes_unlp_frances_lit.csv`.
- Afuera: electivas/optativas a elegir, seminarios de licenciatura, tesina, capacitaciones en idioma, Introducción a los Estudios del Lenguaje (abreviada en el PDF) y, en Lingüística, Literatura Francesa Contemporánea ("LITER." abreviado).
- Humanidades: solo queda Prof. en Cs. de la Educación (no mirado). `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (8) — UNLP Humanidades completa
- Prof. en Cs. de la Educación ya tenía 33 materias (carga del 28/9); comparadas con el PDF oficial A2002 de fahce.unlp.edu.ar: mismos nombres y años. No hizo falta cargar nada. Humanidades queda completa.
- Siguiente: UNLP Exactas (reintentar, estaba bloqueada por timeout/TLS) o UNC. `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (9) — UNC Sociales: Sociología y Ciencia Política
- UNLP Exactas sigue sin abrir (TLS). UNC: seis sitios de facultad están detrás de Anubis (prueba de trabajo/JS): FCM, FAUD, Agropecuarias, Psicología, Comunicación y Esc. Belgrano → **bloqueadas**, no se evaden. Sin respuesta (desconexión/DNS): FFyH (sitio.ffyh/blogs.ffyh) y Monserrat.
- Cargadas por `planes_manuales` (34 y 35 materias, 1.º–5.º año; nombres comprobados contra las páginas oficiales de plan de sociales.unc.edu.ar; año = cuatrimestre/2). Hoja `data/planes_unc_sociales.csv`. Afuera: Ciclo de Nivelación, optativa del 4.º cuatrimestre, Sociología Especial, trabajo final; "Teoría Sociológica III" (el sitio la escribe sin espacio, no se pudo comprobar literal).
- Pendiente en Sociales: Lic. en Trabajo Social (la página de la carrera no enlaza el plan). Otras UNC alcanzables: Derecho, Químicas, Odontología, Artes, Lenguas, Letras, Económicas, Exactas (FCEFyN), FAMAF.
- `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (10) — UNC Derecho: Abogacía
- Cargada por `planes_manuales` (38 materias, 1.º–6.º año; cada nombre comprobado contra la grilla de programas de derecho.unc.edu.ar/programas-carrera-de-abogacia). Hoja `data/planes_unc_derecho.csv`. Afuera: Opcionales I–IV e Idiomas. El PDF del Plan 2000 está en Google Drive (no es del dominio oficial), por eso se usó la grilla.
- Pendiente UNC alcanzable: Notariado, Prof. Cs. Jurídicas (Derecho), Químicas, Odontología, Artes, Lenguas, Letras, Económicas, FCEFyN, FAMAF, Trabajo Social.
- `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (11) — UNC Derecho: Notariado y Prof. en Cs. Jurídicas (no cargados)
- Planes oficiales encontrados: Notariado (`derecho.unc.edu.ar/wp-content/uploads/sites/21/2025/08/plan-de-estudio-notariado-digesto-2001.pdf`) y Profesorado (`.../Plan-de-Estudios-Profesorado-en-Ciencias-Juridicas.pdf`). Descargados a /tmp, leídos con pdftotext.
- **Notariado: no se carga.** Es un ciclo notarial de 3 semestres posterior a Abogacía; la tabla repite "Derecho Notarial II" (el tercer semestre y la fila 07 de correlatividades; evidente errata de "III") y no da años. No se puede comprobar el nombre literal ni el año.
- **Profesorado: no se carga.** Los nombres son legibles pero el semestre de cada materia sale de una tabla con rótulos desalineados; el año sería una inferencia por posición. Un plan con años dudosos es peor que ninguno. Reintentar solo con una fuente por año (programas o grilla en HTML).
- Siguiente en UNC: Químicas, Odontología, Artes, Lenguas, Letras, Económicas, FCEFyN, FAMAF. `verificar_catalogo` (PID 972835, mío) sigue. Sin credenciales de producción.

## 2026-10-23 (12) — UNC Económicas y Químicas (nada cargado)
- Económicas: Contador Público (36), Lic. en Administración (35) y Lic. en Economía (28) ya tienen materias en la base (las lee el spider); el catálogo exportado estaba viejo. Sin trabajo. Pendiente del mismo sitio: Lic. en Gestión Universitaria y Prof. en Cs. Económicas (la página no lista materias; el plan está en el Digesto).
- Químicas, Lic. en Química: el PDF oficial (`fcq.unc.edu.ar/wp-content/uploads/carreras/Plan-Lic-Quimica-ampliado.pdf`) agrupa por ciclo (básico/intermedio/superior), no por año, y abrevia nombres. **No se carga**: el año sería inferido. Farmacia/Bioquímica: planes nuevos recién aprobados (vigencia 2028), no mirados.
- Siguiente UNC: Lenguas (lenguas.unc.edu.ar/carreras-de-grado responde 200), Odontología (fo.unc.edu.ar sin respuesta), FAMAF (rutas viejas 404). `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (13) — UNC Lenguas: Traductorado de Alemán y Lic. en Italianas
- Lenguas ya tenía 13 de 15 carreras con plan (las lee el spider). Cargadas por `planes_manuales` las dos que faltaban: Traductorado Público Nacional de Alemán (30 materias) y Lic. en Lengua y Literatura Italianas (31), 1.º–5.º año; nombres comprobados contra las páginas oficiales de lenguas.unc.edu.ar. Hoja `data/planes_unc_lenguas.csv`. Afuera: Ciclo de Nivelación, optativas de Latina (Alemán) y "Gabinete de Traducción o Introducción a la Interpretación" (a elegir).
- Pendiente UNC alcanzable: Odontología (sin respuesta), FAMAF, Letras, Artes, FCEFyN, Trabajo Social. `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (14) — UNC Artes: Profesorado en Teatro
- Cargado por `planes_manuales` (31 materias, 1.º–4.º año; nombres comprobados contra el PDF oficial `artes.unc.edu.ar/files/Prof-Teatro.pdf`). Hoja `data/planes_unc_artes.csv`. Afuera: Curso de Nivelación, tres seminarios electivos y prueba de idioma.
- **Lic. en Teatro: no se carga.** El PDF (`artes.unc.edu.ar/files/Lic-en-Teatro.pdf`) está en OCR, con los números romanos rotos ("Actuación 11", "Escenotecnia 11") y tres orientaciones (Actuación, Teatrología, Escenotécnicas) en el mismo documento; no se puede comprobar el nombre literal.
- Pendiente en Artes: Música, Artes Visuales, Cine (cada departamento enlaza sus planes desde `?page_id=` de "Carreras y Programas"; no mirados). `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (15) — UNC Artes: Lic. en Cine y Artes Audiovisuales
- Cargada por `planes_manuales` (32 materias, 1.º–5.º año; nombres comprobados contra el PDF oficial `artes.unc.edu.ar/files/Plan-de-estudios-2018-Licenciatura-en-Cine-y-Medios-Audiovisuales.pdf`; año de la tabla de cursado y de los contenidos mínimos, que coinciden). Hoja `data/planes_unc_artes_cine.csv`. Afuera: 6 optativas, 2 electivas, Trabajo Final y prueba de idioma.
- Pendiente en Artes: Música (6 PDF de plan en `departamento-de-musica/carreras/`) y Artes Visuales (`Licenciatura.pdf`, `profesorado.pdf`); no mirados aún. `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (16) — UNC Artes: Visuales y Música (nada cargado)
- Artes Visuales: `artes.unc.edu.ar/files/Licenciatura.pdf` (Plan 26/85) trae Pintura, Grabado y Escultura en un mismo documento; desde 3.º año cada orientación cambia sus materias (Pintura II / Grabado II / Escultura II, Diseño Gráfico solo en Grabado). La base tiene una sola "Licenciatura en Artes Visuales" (y un solo Prof. en Educación Plástica y Visual): cargar una orientación sería inventar, mezclar sería un plan malo. **No se carga.**
- Música: Lic. en Educación Musical (`RHCS_810_2012-Lic-en-Educ-Musical.pdf`) es un escaneo OCR ilegible ("C6rdoba"). Prof. en Educación Musical (`PEM-2013-RHCD_151_2013.pdf`): tabla por año legible, pero los números romanos salen rotos ("Audioperceptiva 11", "Práctica Instrumental 1I", "Residencia 11" por III) y no se puede comprobar el nombre literal (mismo motivo que Lic. Teatro, bitácora 14). **No se carga.** Lic. Composición Musical: PDF con orientaciones, no mirado a fondo.
- UNC Artes queda cerrada: cargadas Cine y Prof. Teatro; el resto con motivo registrado. Siguiente UNC: Letras, FCEFyN, FAMAF, Odontología (sin respuesta), Trabajo Social. `verificar_catalogo` (PID 972835, mío) sigue; exportar al terminar. Sin credenciales de producción.

## 2026-10-23 (17) — UNC Filosofía y Humanidades: Prof. en Geografía y Prof. en Letras Modernas
- FFyH responde en `ffyh.unc.edu.ar` (el sitio viejo `sitio.ffyh`/`blogs` sigue sin respuesta). Planes en `ffyh.unc.edu.ar/academica/planes-de-estudios/` (PDF de resoluciones).
- Cargadas por `planes_manuales` (nombres comprobados contra el PDF): Prof. en Geografía (25, 1.º–4.º; `Profesorado_Geografia_OHCD_01-2021.pdf`) y Prof. en Letras Modernas (33, 1.º–4.º; Ordenanza HCD 03/22, cuadro 7.2). Afuera: nivelación y optativas. Hoja `data/planes_unc_ffyh.csv`.
- No cargables: Prof. Filosofía (PDF escaneado, OCR ruidoso) y las resoluciones ministeriales de Historia, Lic. Letras, Lic. Geografía, etc. (escaneos sin texto). Los "Ord.-Res.-*" son índices de resoluciones, no planes. Antropología (24 pág.) sin texto.
- Pendiente UNC: Odontología (sin respuesta), FAMAF, FCEFyN, Trabajo Social. Exportación en curso; sin credenciales de producción.

## 2026-10-23 (18) — Cierre de la cadena exportar→verificar→exportar
- `verificar_catalogo` terminó (ofertas verificadas 14523; materias 182820) y la exportación final cerró con `Archivo: data/catalogo_depurado.json`. Incluye Prof. Geografía y Prof. Letras Modernas de UNC. Tests: 877 OK.
- USPT: 45 ofertas con fuente caída en la verificación (sitio sin respuesta); revisar en vigilancia.
- Sin credenciales de producción ni de GitHub: nada cargado ni empujado. Siguiente UNC: Letras, FCEFyN, FAMAF, Trabajo Social, Odontología.

## 2026-10-23 (19) — UNC FAMAF: Analista y dos tecnicaturas (nada cargado)
- FAMAF ya tiene plan en la base para Lic. Computación, Física, Matemática, Mat. Aplicada, Astronomía, Hidrometeorología y los profesorados (el lector `plan_famaf` los toma). Faltaban Analista en Computación, Tec. Univ. en Matemática Aplicada y Tec. Univ. en Astronomía.
- Las tres páginas (`famaf.unc.edu.ar/academica/grado/...`) responden 200 pero no traen `div.year`: ningún plan en HTML. Analista no enlaza ningún documento; las dos tecnicaturas enlazan `corr_602.pdf` / `corr_611.pdf`, que son las correlatividades de las **licenciaturas** (602 Mat. Aplicada, 611 Astronomía), no de la tecnicatura. **No se cargan**: el tramo de la tecnicatura sería una inferencia.
- Sin cambios de código ni de datos; tests 877 OK. Pendiente UNC: Letras, FCEFyN, Trabajo Social, Odontología (sin respuesta). Sin credenciales de producción ni de GitHub.

## 2026-10-23 (20) — UNC Letras: Lic. en Letras Clásicas y Tec. en Corrección Literaria
- Cargadas por `planes_manuales` (nombres comprobados contra los PDF oficiales de `ffyh.unc.edu.ar/wp-content/uploads/2024/04/`): Lic. en Letras Clásicas (25, 1.º–5.º) y Tec. en Corrección Literaria (21, 1.º–3.º). Hoja `data/planes_unc_letras.csv`. Afuera: optativas, seminarios electivos, prueba de idioma, TFL y examen de habilitación.
- **Lic. en Letras Modernas: no se carga.** El PDF trae 1.º–3.º común y 4.º–5.º en tres orientaciones (Literarios, Lingüísticos, Crítico del Discurso); la base tiene una sola licenciatura. Prof. en Letras Clásicas: PDF de 133 mil caracteres (`CLASICAS-PLAN-NUEVO-PROF.pdf`), no mirado.
- Tec. en Corrección Literaria queda sin duración en la base (el PDF muestra 3 años, pero la herramienta no la escribe). Verificación y exportación final en curso; sin credenciales de producción ni de GitHub.
- Pendiente UNC: Prof. Letras Clásicas, Trabajo Social, Ciencias Biológicas y su profesorado, Odontología (sin respuesta).

## 2026-10-23 (21) — UNC Letras: Profesorado en Letras Clásicas
- Cargado por `planes_manuales` (27 materias, 1.º–5.º; nombres comprobados contra `ffyh.unc.edu.ar/wp-content/uploads/2024/04/CLASICAS-PLAN-NUEVO-PROF.pdf`, cap. 4.2). Hoja `data/planes_unc_letras_prof.csv`. Afuera: Optativas I y II y Literatura Argentina/Latinoamericana I y II (a elegir).
- Pendiente: cadena exportar→verificar→exportar (la verificación se corta en la herramienta; hacerla desde el lanzador). UNC restante: Trabajo Social, Biológicas (FCEFyN), Odontología (sin respuesta). Sin credenciales de producción ni de GitHub.

## 2026-10-23 (22) — UNC FCEFyN: Ciencias Biológicas (Plan 2015)
- Cargada por `planes_manuales` (33 materias, 1.º–5.º; nombres comprobados contra el reporte oficial `fcefyn.unc.edu.ar/documents/576/Ciencias_Biologicas_bxgf4em.pdf`). Año = semestre/2 según las secciones "PRIMER…OCTAVO SEMESTRE" del PDF (coincide con la página `…/ciencias-biologicas/plan-2015/`); Tesina de Grado en 5.º. Afuera: Ciclo de Nivelación, selectivas y optativas. Hoja `data/planes_unc_biologicas.csv`.
- La base tenía 4 años de duración; la facultad dice cinco de cursado. La herramienta no escribe la duración: queda a corregir.
- **Prof. en Ciencias Biológicas: no se carga.** Su PDF (`documents/575/archivo_90.pdf`, plan 1990) es un reporte de correlativas por ciclo, sin año por materia.
- **Lic. en Trabajo Social: no se carga.** `sociales.unc.edu.ar/content/plan-de-estudio` no trae plan (sin texto ni PDF; solo noticias). Plan no publicado en el sitio.
- UNC restante: solo Odontología (sin respuesta). Pendiente: cadena exportar→verificar→exportar desde el lanzador. Sin credenciales de producción ni de GitHub.

## 2026-10-23 (23) — UNR FCEIA: Ingeniería Electrónica
- Cargada por `planes_manuales` (45 materias, 1.º–5.º; nombres comprobados contra `web.fceia.unr.edu.ar/images/PDF/planes_de_estudio/electronica_grilla_plan_2014.pdf`, Res. 372/2014). Año = cuatrimestre/2. Afuera: optativas, electivas. Hoja `data/planes_unr_electronica.csv`.
- **No cargables (FCEIA):** Ing. Civil, Eléctrica, Industrial y Lic. Matemática/Física: PDF escaneado sin texto. Lic. Ciencias de la Computación: el PDF legible es del plan 2010 y la página vigente dice plan 2024 (PDF escaneado): un plan viejo no se carga. Ing. Mecánica no mirada.
- **FCEcon (Económicas UNR):** `portal.fcecon.unr.edu.ar` arma el plan por JavaScript/API; el HTML no trae materias. Pendiente: encontrar el endpoint antes de escribir lector.
- Exportación en curso; verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.

## 2026-10-23 (24) — Revisión: FCEcon UNR ya tiene lector
- La nota del ciclo 23 ("FCEcon por JS, falta endpoint") estaba desactualizada: `rumbo_scraper/database/planes_unr.py` ya lee el servicio `admin.fceyeua.fcecon.unr.edu.ar` (Contador, Administración, Economía, Estadística, Turismo). Sin cambios de datos ni de código; tests 877 OK.
- Pendiente sin cambios: verificación completa y exportación final desde el lanzador; sin credenciales de producción ni de GitHub. Siguiente: UNR (Medicina, Derecho, Humanidades, Arquitectura, Agrarias, Veterinaria, Bioquímica), luego UNLZ/UNAJ.

## 2026-10-23 (25) — UNR Derecho (Abogacía): no se carga
- `fder.unr.edu.ar/secretaria-academica/carreras-de-grado/` enlaza `PLAN_2012-1.pdf` (Res. CS 447/2011): escaneo sin texto, OCR ruidoso ("Derechó'", "introducción" en minúscula). Además la misma página publica un "plan de transición entre los Planes 2011 y 2015" (Res. CD 728/18), así que el plan 2012 puede no ser el vigente; la Res. 385/15 también es escaneo sin texto. Un plan viejo o con OCR dudoso no se carga.
- Sin cambios de código ni de datos; tests 877 OK. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Medicina, Humanidades, Arquitectura, Agrarias, Veterinaria, Bioquímica; luego UNLZ/UNAJ. Verificación completa y exportación final siguen pendientes desde el lanzador.

## 2026-10-23 (26) — UNR FCEIA: Ing. Mecánica y Agrimensura: no se cargan
- Los PDF oficiales del plan 2014 (`fceia.unr.edu.ar/images/PDF/planes_de_estudio/Res_375_2014_CS_Plan_2014__Ingenieria_Mecanica_1.pdf` y `Res_374_2014_CS_Plan_2014__Agrimensura.pdf`) son escaneos sin texto (`pdftotext` devuelve ~25 bytes). Sin plan en HTML. Un plan por OCR sin comprobar no se carga.
- FCEIA queda cerrada: solo Electrónica tiene texto. Sin cambios de código ni de datos; tests 877 OK. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Medicina, Humanidades, Arquitectura, Agrarias, Veterinaria, Bioquímica; luego UNLZ/UNAJ.

## 2026-10-23 (27) — UNR Medicina Veterinaria: ya estaba cargada
- La lista de "sin plan" sale del catálogo exportado, que está atrasado respecto de la base del scraper: Medicina Veterinaria figuraba sin plan pero ya tiene 47 materias (1.º–6.º). Comparada con `fveter.unr.edu.ar/catedras.html` falta **Fisiología** (2.12, 2.º año); no se puede agregar con `planes_manuales` (la carrera ya tiene materias). Pendiente de corrección puntual por una persona.
- Sin cambios de código ni de datos; tests 877 OK. Sin credenciales de producción ni de GitHub.
- Regla para los próximos ciclos: sacar "sin plan" de la base (`materias.carrera_id`), no del catálogo exportado. UNR sin plan en la base: Medicina, Farmacia, Bioquímica, Psicología, Enfermería, Arquitectura, Agronómica, Odontología no figura (ya tiene), Letras, Bellas Artes, Química, Biotecnología, Diseño Gráfico/Industrial/Indumentaria, Física/Matemática (escaneo), etc.

## 2026-10-23 (28) — UNR: Licenciatura en Diseño Gráfico
- Cargada por `planes_manuales` (30 materias, 1.º–4.º; nombres comprobados contra `fapyd.unr.edu.ar/wp-content/uploads/2022/05/220304_LDG_PLAN_DE_ESTUDIOS.pdf`; año de cada materia comparado con las fichas "Año:" del PDF). Hoja `data/planes_unr_diseno_grafico.csv`. Afuera: 2 optativas. PSE y PPS puestas en 3.º (Ciclo Medio, 2.º–3.º; el año exacto no figura en una ficha).
- Exportación del catálogo en curso; verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR sin plan en la base: Medicina, Arquitectura, Bellas Artes, Diseño Industrial/Indumentaria, Psicología, Farmacia, Bioquímica, Enfermería, Agronómica, Letras.

## 2026-10-23 (29) — UNR: Licenciatura en Diseño Industrial
- Cargada por `planes_manuales` (34 materias, 1.º–5.º; nombres comprobados contra `fapyd.unr.edu.ar/licenciatura-en-diseno-industrial/`, plan por semestres 1.º–10.º; año = semestre/2). Hoja `data/planes_unr_diseno_industrial.csv`. Afuera: Opcional I a IV.
- Exportación hecha (`Archivo: data/catalogo_depurado.json`); verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR sin plan en la base: Arquitectura (no figura en la lista: ya tiene), Diseño de Indumentaria, Bellas Artes, Medicina, Psicología, Farmacia, Bioquímica, Enfermería, Agronómica, Letras.

## 2026-10-23 (30) — UNR: Diseño de Indumentaria y Arquitectura: no se cargan
- Lista de UNR sin materias sacada de la base del scraper (55 carreras sin plan). Lic. en Diseño de Indumentaria: `fapyd.unr.edu.ar/licenciatura-en-diseno-de-indumentaria/` da 404 y la búsqueda del sitio (API de WordPress) no devuelve página ni PDF del plan; solo una nota de convocatoria. Plan no publicado/no hallado en el sitio de la facultad.
- Arquitectura: la facultad está cambiando el plan (Consejo Directivo aprobó una grilla "preliminar"); un plan en transición no se carga hasta que haya uno vigente.
- Sin cambios de código ni de datos; tests 877 OK. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Medicina, Psicología, Farmacia, Bioquímica, Enfermería, Agronómica, Letras, Bellas Artes, Química, Biotecnología; luego UNLZ/UNAJ.

## 2026-10-23 (31) — UNR Medicina y Psicología: no se cargan
- Medicina (`fcm.unr.edu.ar/wp-content/uploads/2019/08/PLAN_DE_ESTUDIOS_MEDICINA.pdf`, Res. CS 158/2001): tiene texto, pero es un mapa curricular por áreas y ciclos vitales (semanas), sin materias por año; además hay una resolución posterior (`CS-31-24.pdf`) sin revisar. No se carga.
- Psicología (`fpsico.unr.edu.ar`, plan 2014 Res. CS 437): PDF escaneado sin texto (`pdftotext` ~21 bytes). No se carga.
- Firecrawl (búsqueda web) sin créditos: no se usa; los PDF se leen con curl + user agent del spider (el cliente por defecto da 403 en fcm.unr).
- Sin cambios de código ni de datos; sin credenciales de producción ni de GitHub.
- Siguiente UNR: Farmacia, Bioquímica, Enfermería, Agronómica, Letras, Bellas Artes, Química, Biotecnología; luego UNLZ/UNAJ.

## 2026-10-23 (32) — UNR: Farmacia y Bioquímica
- Cargadas por `planes_manuales` (Farmacia 39 materias 1.º–5.º; Bioquímica 38 materias 1.º–6.º). Fuente: tabla HTML del plan en `www.fbioyf.unr.edu.ar/website/ofertaeducativa/{farmacia,bioquimica}.php`; nombres comprobados literalmente. Hoja `data/planes_unr_farmacia_bioquimica.csv`. Se tomó el primer bloque (códigos F25xx, plan vigente); el bloque "Plan de Estudios 2018" de la misma página queda afuera. Afuera: Optativas/Electivas.
- Exportación hecha (`Archivo: data/catalogo_depurado.json`); verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Enfermería, Agronómica, Letras, Bellas Artes, Química, Biotecnología, Terapia Ocupacional, Fonoaudiología; luego UNLZ/UNAJ.

## 2026-10-23 (33) — UNR FCByF: Biotecnología, Ciencia y Tecnología de los Alimentos, Prof. en Química
- Cargadas por `planes_manuales` (Biotecnología 30 materias 1.º–5.º; Alimentos 36, 1.º–5.º; Prof. Química 27, 1.º–4.º). Fuente: tabla HTML del plan en `www.fbioyf.unr.edu.ar/website/ofertaeducativa/{licbiotecnologia,liccytalimentos,profquimica}.php`; nombres comprobados literalmente. Hoja `data/planes_unr_fbioyf_2.csv`. Afuera: Optativas/Electivas.
- **Lic. en Química NO se carga:** la página publica dos planes (uno sin correlativas y "Plan de Estudios 2018", con materias y cargas distintas) sin decir cuál rige. Pendiente de que una persona confirme el vigente.
- Exportación lanzada; verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Enfermería, Terapia Ocupacional, Fonoaudiología (Ciencias Médicas), Agronómica, Letras, Bellas Artes, Ciencias de la Computación/Matemática (FCEIA); luego UNLZ/UNAJ.

## 2026-10-23 (34) — UNR: Ingeniería Agronómica
- Cargada por `planes_manuales` (44 materias, 1.º–5.º; nombres comprobados contra `fcagr.unr.edu.ar/wp-content/uploads/2024/08/CS-416-23-2-Plan-de-Estudios-IA.pdf`, RCS 416/2023, "vigente desde 2024" según la página). Hoja `data/planes_unr_agronomica.csv`. Afuera: Optativas I y II, Electivas, y Inglés, Informática y Práctica Social Educativa (la grilla no les da año; el cargador exige año en todas o en ninguna).
- Exportación hecha (`Archivo: data/catalogo_depurado.json`); verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Enfermería, Terapia Ocupacional, Fonoaudiología, Letras, Bellas Artes, Ciencias de la Computación/Matemática (FCEIA); luego UNLZ/UNAJ.

## 2026-10-23 (35) — UNR: Enfermería
- Cargada por `planes_manuales` (40 materias, 1.º–5.º; nombres comprobados contra `fcm.unr.edu.ar/wp-content/uploads/2019/08/LicEnfermeria-Plan2017.pdf`, plan 2017; año según la tabla de asignación horaria). Hoja `data/planes_unr_enfermeria.csv`. Afuera: Materias Optativas.
- Exportación y verificación completa pendientes desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Terapia Ocupacional, Fonoaudiología (plan 2024 en fcm.unr.edu.ar/fonoaudiologia/), Letras, Bellas Artes, Ciencias de la Computación/Matemática (FCEIA); luego UNLZ/UNAJ.

## 2026-10-23 (36) — UNR: Terapia Ocupacional (Fonoaudiología no)
- Terapia Ocupacional cargada por `planes_manuales` (19 materias, 1.º–5.º; nombres comprobados contra `fcm.unr.edu.ar/wp-content/uploads/2025/12/769-2025-TEO.pdf`, RCS 769/2025, plan 2025, año según el anexo de carga horaria). Hoja `data/planes_unr_terapia_ocupacional.csv`. Ojo: el catálogo trae duración 4 años y el plan son 5; no se tocó (revisar).
- Fonoaudiología NO se carga: el plan 2024 de `fcm.unr.edu.ar/fonoaudiologia-plan-2024/` se publica solo como descarga de Google Drive (fuera del dominio de la UNR, el cargador lo rechaza).
- Exportación hecha (`Archivo: data/catalogo_depurado.json`); verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Letras, Bellas Artes, Ciencias de la Computación/Matemática (FCEIA); luego UNLZ/UNAJ.

## 2026-10-23 (37) — UNR Humanidades y Artes: Indumentaria y 3 tecnicaturas de música
- Cargadas por `planes_manuales` desde el plan en texto de cada página de carrera en `fhumyar.unr.edu.ar` (nombres comprobados literalmente): Lic. en Diseño de Indumentaria (y Textil; 37 materias, 1.º–4.º), Tec. en Acordeón (22), Bajo Eléctrico (21) y Guitarra Eléctrica (23), 1.º–3.º. Hoja `data/planes_unr_humanidades.csv`. Afuera: electivas/optativas con opciones y Trabajo Final. (La carrera de Indumentaria es de Humanidades, no de FAPyD: corrige la bitácora 30.)
- **NO se cargan:** Lic. en Letras, Lic. y Prof. en Bellas Artes — 4.º y 5.º año por orientación (ciclos/orientaciones mezclados). El PDF del plan está solo en Google Drive.
- Exportación hecha (`Archivo: data/catalogo_depurado.json`); verificación completa desde el lanzador. Sin credenciales de producción ni de GitHub.
- Siguiente UNR: FCEIA (Computación, Matemática, Física), Tec. Gestión Cultural; luego UNLZ/UNAJ.

## 2026-10-23 (38) — UNR: Tec. en Gestión Cultural
- Cargada por `planes_manuales` (27 materias, 1.º–3.º; nombres comprobados literalmente contra el plan en texto de `fhumyar.unr.edu.ar/tecnicatura-en-gestion-cultural/`). Hoja `data/planes_unr_gestion_cultural.csv`.
- FCEIA (Computación, Matemática, Física) ya estaba cerrada desde las bitácoras 23 y 26 (PDF escaneados o plan viejo); el "siguiente" de la 37 estaba desactualizado.
- **Lic. y Prof. en Interpretación NO se cargan:** son nombres genéricos de una lista vieja; Humanidades hoy publica una carrera por instrumento (Canto, Piano, Guitarra, Órgano, Cuerdas, Vientos), que ya tienen plan. Revisar si sobran en el catálogo.
- Cadena exportar→verificar (UNR: materias 2239/2260, sin "no lo dice")→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Lic. Recursos Naturales, Lic. Sistemas Integrales de Cuidado, Ciencia de Datos, tecnicaturas del Politécnico (ips.edu.ar) y de Ciencia Política; luego UNLZ/UNAJ.

## 2026-10-23 (39) — UNR: Lic. en Sistemas Integrales de Cuidado
- Cargada por `planes_manuales` (24 espacios, 1.º–4.º; nombres comprobados literalmente contra `famhyc.unr.edu.ar/wp-content/uploads/2025/10/b.-ESPACIOS-CURRICULARES-Y-CORRELATIVIDADES-Licenciatura-en-Sistemas-Integrales-de-Cuidado.pdf`, enlazado desde la página de la carrera; año según el código del espacio). Hoja `data/planes_unr_cuidado.csv`. El plan no tiene optativas; da título intermedio de Bachiller Universitario (1500 h), no cargado aparte.
- Lic. en Recursos Naturales: `fcagr.unr.edu.ar/?page_id=39` no respondió al lector; reintentar.
- Cadena exportar→verificar (UNR: materias 2263/2284)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Tec. Acompañamiento Terapéutico (PDF `DI-SSPU-1120-25` en fpsico.unr.edu.ar), Recursos Naturales, Ciencia de Datos (página "en construcción"), tecnicaturas del Politécnico; luego UNLZ/UNAJ.

## 2026-10-23 (40) — UNR: Tec. Universitaria en Acompañamiento Terapéutico
- Cargada por `planes_manuales` (16 materias, 1.º–2.º; nombres comprobados literalmente contra `fpsico.unr.edu.ar/wp-content/uploads/2025/11/DI-SSPU-1120-25-TECNICO_A-UNIVERSITARIO_A-EN-ACOMPANAMIENTO-TERAPEUTICO.pdf`, anexo de la DI-2025-1120-APN-SSPU, RCS 503/2025, enlazado desde la página de la carrera). Hoja `data/planes_unr_acompanamiento.csv`. Los códigos 11 y 12 tienen dos módulos (a y b) cada uno: se cargaron los 4 módulos por separado, como los nombra la página.
- Ojo: el catálogo trae duración 1 año; la página y el plan dicen 2 años. No se tocó (revisar, como Terapia Ocupacional).
- Cadena exportar→verificar (UNR: materias 2279/2300, las 16 nuevas verificadas)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Recursos Naturales (reintentar `fcagr.unr.edu.ar/?page_id=39`), Ciencia de Datos, Tec. Tecnología Alimentaria (Politécnico, Baigorria); luego UNLZ/UNAJ.

## 2026-10-23 (41) — UNR: Tec. Universitaria en Administración Pública
- Cargada por `planes_manuales` (19 asignaturas, 1.º–3.º; nombres comprobados literalmente contra `fcpolit.unr.edu.ar/wp-content/uploads/2020/04/Tecnicatura-Universitaria-en-Administración-Pública-PlanVigente.pdf`, RCD 586/15, enlazado desde `fcpolit.unr.edu.ar/escuelacienciapolitica/tuap/`). Hoja `data/planes_unr_administracion_publica.csv`. La RCS 229/2018 (vigente 2017, también enlazada) solo cambia correlatividades y horas y deja 2.13.2 sin la alternativa (b): se cargó como "Régimen Jurídico de la Administración Pública Provincial y Local". Incluye Taller y Trabajo Final (asignatura anual con código).
- Recursos Naturales: `fcagr.unr.edu.ar/?page_id=39` sigue sin responder (segundo intento).
- Cadena exportar→verificar (UNR: materias 2298/2319)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Prof. Comunicación Educativa y Educación Física (buscar facultad), Ciencia de Datos, Tec. Tecnología Alimentaria (Politécnico); Recursos Naturales en otro ciclo; luego UNLZ/UNAJ.

## 2026-10-23 (42) — UNR: Prof. Comunicación Educativa y Prof. Educación Física
- Prof. de Comunicación Educativa cargado por `planes_manuales` (26 espacios, 1.º–4.º; nombres comprobados literalmente contra `fcpolit.unr.edu.ar/wp-content/uploads/2020/04/Profesorado-Comunicación-Educativa-PlanVigente.pdf`, CD 2586/14, CS 1075/14, RM 222/17, enlazado desde `fcpolit.unr.edu.ar/?page_id=6966`; nombres de los contenidos mínimos, año según el código). Hoja `data/planes_unr_comunicacion_educativa.csv`. Sin optativas.
- Prof. Universitario en Educación Física cargado (33 espacios, 1.º–4.º; contra la tabla `famhyc.unr.edu.ar/wp-content/uploads/2025/10/b.-ESPACIOS-CURRICULARES-Y-CORRELATIVIDADES-Profesorado-en-Educacion-Fisica.pdf`, enlazada desde la página de la carrera; año según el código). Hoja `data/planes_unr_educacion_fisica.csv`. Afuera: Optativa I y II. El plan (PE) dice 4 años, como el catálogo; nombra 4.2.32 "Educación e Inclusión" y la tabla "Educación Física e Inclusión" (se usó la tabla).
- Cadena exportar→verificar (UNR: materias 2357/2378, las 59 nuevas verificadas)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente UNR: Ciencia de Datos, Tec. Tecnología Alimentaria (Politécnico); Recursos Naturales en otro ciclo; luego UNLZ/UNAJ.

## 2026-10-23 (43) — UNR: Tec. Universitaria en Gestión y Producción (Politécnico)
- Cargada por `planes_manuales` (42 asignaturas, 1.º–3.º; nombres comprobados literalmente contra `ips.edu.ar/wp-content/uploads/2018/05/TUGP.pdf`, enlazado desde `ips.edu.ar/gestion`; año según el código). Hoja `data/planes_unr_gestion_produccion.csv`. Es el mismo plan que el "Nuevo Plan de Estudio 2012" de la página de planes (solo cambian de cuatrimestre 2.16.1 y 2.23.2, y la ortografía). Incluye Proyecto Final (tiene código).
- El verificador ahora toma `ips.edu.ar` (Instituto Politécnico Superior, enlazado desde `unr.edu.ar/tecnicaturas/`) como dominio de la UNR, como UNTREF con untrefvirtual.
- **Resto del Politécnico pendiente** (Química, Plásticos y Elastómeros, Sistemas Electrónicos, Construcciones, Mecatrónica, Óptica, Analista en Sistemas): cada página enlaza un PDF en ips.edu.ar y además un "Plan vigente" solo en Google Drive; la descarga de Drive no respondió. No se cargan sin confirmar que el PDF del sitio es el vigente.
- **Ciencia de Datos NO se carga:** la tabla de `fcecon.unr.edu.ar/.../licenciatura-en-ciencia-de-datos-pagina-en-construccion` está vacía y el plan 2024 está solo en Google Drive. Ojo: la página muestra 5 años (1.º–5.º) y el catálogo dice 4.
- Cadena exportar→verificar UNR (materias 2399/2420, las 42 nuevas verificadas)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Vigilancia sin Claude del 23/10: mismas caídas que el 22/10 (Austral, Palermo posgrados, UB, UBA); UCEMA ahora 16→17 carreras (el 22/10 daba 14). No re-importar desde esas corridas.
- Siguiente: Recursos Naturales (reintento), Tec. Tecnología Alimentaria (Baigorria); luego UNLZ/UNAJ.

## 2026-10-23 (44) — UNR: Lic. en Recursos Naturales
- Los "reintentos" de las bitácoras 39 y 41 leían un fallo guardado el 27/9 en `data/verificacion/` (caché de `Fuentes`); borrada esa entrada, `fcagr.unr.edu.ar/?page_id=39` da 404: la página se mudó a `fcagr.unr.edu.ar/agro/licenciatura-rrnn`. Ojo con otros "no respondió": mirar si es caché vieja.
- Cargada por `planes_manuales` (34 espacios, 1.º–5.º; nombres comprobados literalmente contra `fcagr.unr.edu.ar/wp-content/uploads/2024/02/Asignaturas-Plan-de-estudios-Lic.-en-RRNN-FCA-UNR.pdf`, RCS 311/13, RM 2381/2013, enlazado desde la página, que lista las mismas por año). Hoja `data/planes_unr_recursos_naturales.csv`. Incluye Informática (2.º) e Inglés (3.º), pruebas de suficiencia con código, y Tesina; afuera los 210 h de cursos electivos. Título intermedio de Bachiller (1500 h), no cargado aparte.
- Cadena exportar→verificar (UNR: materias 2433/2454, las 34 nuevas verificadas)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: Tec. Tecnología Alimentaria (Baigorria, sin duración en la base); luego UNLZ/UNAJ.

## 2026-10-23 (45) — UNR: "Tecnicatura en Tecnología Alimentaria en Baigorria" retirada
- No es educación superior: la fila salía de una noticia del 19/8/2024 (`unr.edu.ar/tecnicatura-en-tecnologia-alimentaria-en-granadero-baigorria/`) sobre la sede Baigorria del Politécnico ("cursar toda la escuela", "completar su formación secundaria"). `ips.edu.ar/especialidades` la lista entre las "tecnicaturas de nivel medio" (Técnico/a en Tecnología de los Alimentos) y no está en `ed-superior`.
- Borrada de la base del scraper (no tenía materias, actividades ni ofertas). Ojo: una corrida genérica nueva de unr.edu.ar podría volver a tomar esa noticia como carrera.
- Cadena exportar→verificar (UNR: ofertas 210/217, materias 2433/2454)→exportar completa (`Archivo: data/catalogo_depurado.json`, sin la fila). Sin credenciales de producción ni de GitHub.
- Siguiente: UNR queda sin pendientes fáciles (Politécnico solo en Drive); pasar a UNLZ/UNAJ.

## 2026-10-23 (46) — UNLZ: 9 licenciaturas de Ciencias Sociales
- Cargadas por `planes_manuales` (276 materias, sin año: los planes numeran las asignaturas sin decir el año), comprobadas literalmente contra los PDF que enlaza cada página de carrera de `sociales.unlz.edu.ar/index.php/<carrera>/`: Periodismo (30, RM 1081/12), Publicidad (31, RM 1266/12), Relaciones Públicas (31, RM 1183/12), Relaciones Laborales (30, RM 2109/12), Psicopedagogía (33, RM 1272/12), Trabajo Social (32, RM 1549/88), Letras (29, RM 635/88), Comunicación Social (30, RM 319/12) y Ciencias de la Educación (30, RM 736/88). Hoja `data/planes_unlz_sociales.csv`. Cada licenciatura incluye el tramo de tecnicatura/profesorado/tronco común del mismo documento; afuera las optativas genéricas y los 2 niveles de idioma.
- **Ingeniería (Industrial, Mecánica, Mecatrónica, Ferroviaria) NO cargable:** "Ver plan de estudio" lleva a carpetas de Google Drive.
- **Lic. Higiene y Seguridad, Gestión de la Información y Gestión de Sistemas de Automatización y Robótica pendientes:** los PDF de `ingenieria.unlz.edu.ar/oferta-academica/grado/*.pdf` son escaneos de la resolución ministerial (sin texto; el verificador no les hace OCR). El OCR se lee bien (Higiene: 13 asignaturas en 3 cuatrimestres); probar `planes_escaneados UNLZ`.
- Los sitios de las facultades se mudaron: `economicas.unlz.edu.ar`, `agrarias.unlz.edu.ar` y `derecho.unlz.edu.ar` responden (las direcciones viejas `www.economicas…`, `agrarias…/web18/`, `www.derecho…/web2017/` no).
- Cadena exportar→verificar (UNLZ: ofertas 68/69, materias 473/473)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNLZ Económicas (Contador, Administración, tecnicaturas), Agrarias (tecnicaturas) y Derecho (Prof. Cs. Jurídicas); luego UNAJ.

## 2026-10-23 (47) — UNLZ: Económicas (Contador, Lic. Administración y sus títulos intermedios)
- Cargadas por `planes_manuales` (119 materias, con año), comprobadas literalmente contra las páginas de carrera (el plan está en el HTML): `www.economicas.unlz.edu.ar/nuevosite/index.php/contador-publico/` → Contador Público (36, incluye PPS; 2708 h) y Tec. Universitaria Contable (23, título intermedio); `…/licenciatura-en-administracion/` → Lic. en Administración (37, incluye PPS; 2772 h) y Tec. Universitaria en Administración y Gestión (23). Hoja `data/planes_unlz_economicas.csv`. Solo se ajustaron mayúsculas/tildes contra la lista de programas de la misma página.
- Las dos tecnicaturas siguen sin duración en la base: la página dice 3 años y medio (no se carga por `planes_manuales`).
- **Técnico en Comercio Internacional y Aduanas:** no aparece en el sitio de Económicas; buscar de qué facultad es.
- Cadena exportar→verificar (UNLZ: ofertas 68/69, materias 592/592)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Vigilancia sin Claude del 23/10: USAL creció 72→80 carreras (trabajo nuevo, revisar); el resto igual que el 22/10.
- Siguiente: UNLZ Agrarias (5 tecnicaturas + Agroecología) y Derecho (Prof. Cs. Jurídicas); luego UNAJ.

## 2026-10-23 (48) — UNLZ: Agrarias, 4 tecnicaturas
- Cargadas por `planes_manuales` (62 materias), comprobadas literalmente contra los PDF que enlaza `agrarias.unlz.edu.ar/oferta-academica/` (`/DOCS/OFERTA ACADEMICA/GRADO/…`): Tec. Agroecología (21, Res. CS 111/20, con año), Procesamiento Agroalimentario (21, plan 002/18, RM 1021/20, **sin año**: el rótulo de año está centrado al costado de la tabla y no marca dónde empieza cada año), Arboricultura y Vivericultura (10 asignaturas anuales + nada más: 480+480+576+288 = 1824 h, plan 047/14) y Diseño y Mantenimiento de Espacios Verdes (10, plan 045/14). Hoja `data/planes_unlz_agrarias.csv`.
- **Producción Animal y Producción Vegetal NO cargables:** cada PDF trae dos planes (orientaciones Producción Extensiva e Intensiva, distintos desde la materia 16/17).
- Grado de Agrarias (Agronómica, Zootecnista, Economía Social, Enseñanza de las Cs. Biológicas, Gestión de la Calidad) no figura entre las ofertas sin plan de la base: revisar si faltan en la base.
- Cadena exportar→verificar (UNLZ: materias 654/654)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNLZ Derecho (Prof. Cs. Jurídicas), Comercio Internacional y Aduanas; luego UNAJ.

## 2026-10-23 (49) — UNLZ: Derecho y escaneos de Ingeniería (sin carga)
- `derecho.unlz.edu.ar/carreras-2/` lista Abogacía, Lic. en Seguridad, Lic. en Comercio Internacional y Aduanas (ciclo de complementación, 18 materias en la página), Corredor y Martillero, Técnico Superior en Seguridad y Despachante de Aduana. **Prof. en Ciencias Jurídicas y "Técnico en Comercio Internacional y Aduanas" no figuran:** vienen de la guía del Ministerio (sin página de origen); razón: plan no publicado en el sitio de la facultad.
- **Faltan en la base:** Lic. en Comercio Internacional y Aduanas (CCC) y Lic. en Seguridad: entran con una corrida del spider de UNLZ, no a mano.
- `planes_escaneados UNLZ` da 0 planes: las licenciaturas de Ingeniería (Higiene y Seguridad, Gestión de la Información, Automatización y Robótica) no tienen `url_oficial` en sus ofertas, así que no encuentra el PDF. Pendiente: que la corrida del spider les asigne la página (`ingenieria.unlz.edu.ar/oferta-academica/grado/`).
- Sin cambios en la base. Siguiente: UNAJ.

## 2026-10-23 (50) — UNAJ: 5 ingenierías (plan nuevo)
- Cargadas por `planes_manuales` (236 materias, con año), comprobadas literalmente contra los listados "Materias y Correlatividades" del plan nuevo (`unaj.edu.ar/wp-content/uploads/2025/11/Materias-y-Correlatividades-<CARRERA>-NP.pdf`, enlazados desde cada página de carrera junto a su resolución): Petróleo (47, Res. CS 188/22), Bioingeniería (48, incluye PPS, Res. CS 189/22), Electromecánica (49, Res. CS 192/22), Informática (47, Res. CS 191/22) e Industrial (45, Res. CS 122/24). Hoja `data/planes_unaj_ingenierias.csv`. Afuera: optativas, Inglés extracurricular y la PPS que va aparte del cuadro por año. Se controló que ningún código de asignatura del documento quedara afuera (las filas cortadas por el salto de página, Reservorios I y Proyecto Informático, entraron).
- **Bioquímica NO cargable:** el listado Plan 2015 parte los nombres en varios renglones, le faltan filas (14, 29) y trae orientaciones (Infectología, …).
- Resto de UNAJ: cada página enlaza un PDF de "Listado de asignaturas y correlatividades" o la resolución; pendiente revisar uno por uno (lista en esta bitácora: Economía, Administración, Trabajo Social, Enfermería, Kinesiología, LOAQ, Obstetricia, Emergencias, Información Clínica, Adm. Agraria a distancia, CCC de Matemática y Cs. Naturales).
- Cadena exportar→verificar (UNAJ: ofertas 88/88, materias 273/273)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.

## 2026-10-23 (51) — UNAJ: CCC Didáctica de la Matemática; resto de los listados NO cargables
- Cargada por `planes_manuales` la Lic. en Didáctica de la Matemática (CCC): 17 espacios, 1.º–2.º, del listado `unaj.edu.ar/wp-content/uploads/2023/06/Correlatividades-Did-Matematica.pdf` (afuera Inglés e Informática extracurriculares). Hoja `data/planes_unaj_ccc.csv`. **Ojo:** la exportación no incluye esa carrera (UNAJ exporta 24 de 30), así que la verificación siguió en 273 materias; queda en la base del scraper. Revisar por qué el exportador la excluye.
- **Ojo con el verificador:** una primera hoja tenía nombres con las correlativas pegadas adelante ("2 2, 5 12 Investigación en…") y `planes_manuales` los aceptó igual, porque ese texto está en el documento. Se corrigió antes de cargar; revisar a ojo los nombres que salen de tablas.
- **NO cargables por ahora** (listados PDF con nombres partidos en filas distintas de la tabla, que ni el verificador lee enteros, filas que se pierden en la extracción, y en varios casos orientaciones o grupos optativos): Economía, Administración (grupo PyME), Trabajo Social, Enfermería (orientaciones Cuidados Críticos / Problemas Comunitarios), Kinesiología, LOAQ, Obstetricia, Emergencias Sanitarias, Información Clínica, Adm. Agraria a distancia, CCC Enseñanza de las Cs. Naturales. Haría falta un lector por posición de palabras (en `parsers/`) y que el verificador junte los renglones de una misma fila.
- Cadena exportar→verificar (UNAJ: ofertas 88/88, materias 273/273)→exportar completa (`Archivo: data/catalogo_depurado.json`).
- Siguiente: UNTREF / UNO / UNAHUR / UNPAZ (GBA).

## 2026-10-23 (52) — UNTREF Virtual: 10 carreras
- Cargadas por `planes_manuales` (291 materias), cada lista cotejada con el PDF del plan que enlaza la pestaña "Plan de Estudios" de `untrefvirtual.edu.ar/carrera/<n>` (`materiales.untrefvirtual.edu.ar/planes/…`). Con año: Contador Público (35, hoja "Plan 2019", igual a la nómina de la Res. CS de 2020: 34 + PPS), Martillero y Corredor (20, plan 2022), Migraciones Internacionales (22), Marketing (30, nómina del plan RCS 27/25; afuera electivas, optativas y TFA) y Sociología (32). Sin año: Gestión de Políticas Públicas (33; el cuadro por año del PDF nombra distinto varias materias), Industria Musical (22), Turismo (32, sin el seminario optativo), Medios Digitales (23) y Gestión y Desarrollo de Personas (42, tecnicatura + ciclo superior). Afuera el Trabajo Final. Hoja `data/planes_untref_virtual.csv`.
- **Ojo:** la página de Contador corta su lista en la materia 31 (le faltan Derecho Comercial, Auditoría, Actuación Pericial y PPS), y el caché del verificador tenía la página vieja de Marketing (plan anterior): por eso esas dos se cargaron desde el PDF.
- Pendientes UNTREF: Administración, Cs. Políticas, Adm. Tributaria y Gestión Logística (solo PDF/resolución, sin revisar); Políticas y Adm. de la Cultura (la página repite "Inglés Nivel II" y no enlaza PDF); Edición (la página trae errores tipo "Edición 11"; revisar el PDF); presenciales: Artes Electrónicas, Cs. de la Educación, Geografía (Compl.), Prof. Geografía, Gestión Educativa, Instrumentación Quirúrgica, Resolución de Conflictos (no las toma `plan_untref`).
- Cadena exportar→verificar (UNTREF: ofertas 135/135, materias 1936/1936)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.

## 2026-10-24 (53) — UNTREF: Lic. en Administración y Lic. en Ciencias Políticas
- Cargadas por `planes_manuales` (58 materias, con año), cada nombre comprobado literalmente contra el PDF del plan que enlaza la página de carrera de `untrefvirtual.edu.ar`: Administración (35; `materiales…/planes/lic_y_tec/administracion.pdf`, plan 2018/2019, año por cuatrimestre; afuera Taller y Trabajo Final) y Ciencias Políticas (23; `…/ciencias_politicas.pdf`, plan 8.4 por año; afuera optativas, Trabajo Final y las materias complementarias obligatorias, que no tienen año). Hoja `data/planes_untref_adm_cpol.csv`. La primera vista previa rechazó Ciencias Políticas por mezclar filas con y sin año; se quitaron las complementarias y quedó anotado en la hoja.
- **Gestión Logística NO cargable:** la resolución RCS 3/21 es un PDF escaneado (40 páginas, texto solo en las páginas 17–18, la nómina sin años). La base la tiene como Licenciatura con duración 3 años; el plan dice tecnicatura de 3 y licenciatura de 5: revisar la duración de esa oferta.
- Pendientes UNTREF: Edición (página con errores, revisar PDF), Prof. Geografía, Lic. Gestión Educativa, Artes Electrónicas, Cs. de la Educación, Políticas y Adm. de la Cultura.
- Cadena exportar→verificar (UNTREF: ofertas 135/135, materias 1994/1994)→exportar completa (`Archivo: data/catalogo_depurado.json`). La verificación completa tardó unas 3 h 40 min (todo el catálogo). Sin credenciales de producción ni de GitHub.
- Siguiente: UNO (15 sin plan), UNAHUR (14), UNPAZ (14), UNSO (16); luego las pendientes de UNTREF.

## 2026-10-24 (54) — UNO: Tec. Gestión y Administración Contable
- Cargada por `planes_manuales` (23 materias, con año, 3 años), copiada del PDF del plan que enlaza la página de la carrera (`uno.edu.ar/images/documentos/escuelas/Tec Univ en Gestion y Administracion Contable- Plan de Estudios.pdf`); cada nombre comprobado literalmente por el verificador (vista previa OK, luego `--apply` a la base del scraper). Hoja `data/planes_uno_tecnicaturas.csv`. Afuera: Electiva (de otra escuela) y Optativa I.
- **Por qué no se cargaron las otras 14 de UNO:** `planes_documentos` no encuentra la URL de sus ofertas (vista previa: 0 planes); las páginas sí responden y enlazan PDF de plan, pero la mayoría de esos PDF son tablas donde cada nombre parte en 2–3 renglones (Abogacía, Ing. Ambiental, Ing. en Energía, Enfermería, Matemática, Informática, Acomp. Terapéutico, Redes, Prof. Informática). `plan_uno` no los lee (0 materias). Se copian a mano solo si el nombre sale entero y el año es claro; pendiente decidir un lector o revisarlos uno por uno.
- Pendiente UNO sin plan: Arquitectura (página de biblioteca), Ing. Química (página sin PDF de plan), Odontología, Matemática, Informática, Enfermería, Ing. Ambiental, Ing. en Energía, Prof. Informática, Tec. Redes, Tec. Investigación Criminal, Tec. Acomp. Terapéutico, Tec. Administración (el PDF enlazado es un mapa de sedes).
- Cadena exportar→verificar UNO (45/45 ofertas, 219/219 materias)→exportar completa (`Archivo: data/catalogo_depurado.json`). Verificación solo de UNO; tests sin cambios de código. Sin credenciales de producción (23 materias solo en la base del scraper).
- Siguiente: UNO (resto, revisar), UNAHUR (14), UNPAZ (14), UNSO (16); luego las pendientes de UNTREF.

## 2026-10-24 (55) — UNAHUR: profesorados 2024, Mant. Hospitalario y Chino; limpieza de nombres rotos
- **Limpieza:** 6 carreras de UNAHUR tenían nombres con la columna de campo pegada ("Física C CFB", "Inglés I CFC"), ligaduras rotas ("Quı mica general") o basura ("APN-ME Diseño curricular…"), y salían exportadas: Ing. Agronómica, Lic. Gestión del Mantenimiento, Prof. Chino, Tec. Viverismo, Tec. Prod. Agroecológica Periurbana y Lic. Diseño Industrial. Además las 60 "materias" de sus 10 especializaciones eran el menú del sitio ("Contactanos", "UNAHUR EN CIFRAS 2025", "Ver video en YouTube"). Se borraron las 296 filas; copia en `data/unahur_materias_retiradas_2026-10-24.json` (local, ignorado por git). `planes_documentos UNAHUR` no las vuelve a cargar (0 planes).
- **Lector nuevo `plan_unahur_campos`** (`parsers/planes_sitios.py`, al final de `plan_unahur_todos`, con pruebas): tabla sin número de materia ("Zoología  C  CFE  6 …", o "Física  CFB  Cuatr. …"), nombre largo centrado en su fila, corte de página. Devuelve nada si encuentra una fila que no entiende (así se detectó que "C." y "C1" se salteaban "Tecnología educativa").
- Cadena exportar→verificar UNAHUR (ofertas 52/52, materias 770/770; Matemática se exporta como "Profesorado Universitario en Matemática": alias agregado en `data/unahur_planes.json`)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Cargadas por `planes_manuales` (hoja `data/planes_unahur_campos.csv`, "lector plan_unahur_campos", cada nombre comprobado contra el PDF; contraprueba: filas con código de campo = materias leídas): Prof. Biología (39), Geografía (37), Educación Física (39), Letras (38), Inglés (33), Matemática (35), Chino (35, plan RCS 008/2026), Tec. Mantenimiento Hospitalario (20). 276 materias. Geografía: la tabla dice "territoriales capitalistas centrales" (errata); se cargó "territorios", como la lista del mismo documento.
- **NO cargables por ahora:** Lic. Diseño Industrial (el lector la lee entera, 36, pero el texto del PDF pega "TecnologíaI", "InglésI", "Proyectoﬁnal" y el verificador no los encuentra); Lic. Gestión del Mantenimiento (filas partidas: la "C" en un renglón, campo y horas en otro); Viverismo, Periurbana, Agronómica, Tec. Metalurgia, Tec. Energía Eléctrica (tabla por cuatrimestre con código), Lic. Tecnología de los Alimentos (tabla por cuatrimestre con columnas IPS/IPP), Enfermería, Desarrollo Agrario: otros formatos, sin revisar uno por uno. Lic. Educación: el plan tiene "Unidad curricular electiva 1–4" (CCC). Tec. IA: tabla limpia de 20 materias ("Total 1° Año"), falta lector.

## 2026-10-24 (56) — UNPAZ: 6 licenciaturas con `plan_unpaz`
- `planes_documentos UNPAZ` daba 0 planes: la base guarda páginas viejas de facultad (`csyd.`/`cjys.unpaz.edu.ar/node/…`); los planes están en las páginas nuevas (`unpaz.edu.ar/<carrera>`, enlace "PLAN DE ESTUDIO", folleto PDF por año).
- `plan_unpaz` ajustado (con prueba): códigos de 4 cifras (LGTI "6001"), el año en la misma línea del encabezado ("Tercer año   Código   Asignatura") y una correlatividad suelta al lado del resto de un nombre partido ("producción audiovisual I      -", que antes cortaba "Taller de realización y").
- Cargadas por `planes_manuales` (hoja `data/planes_unpaz.csv`, "lector plan_unpaz", vista previa OK y `--apply`; filas al azar cotejadas con el PDF): Enfermería (37, afuera Electiva 1-2), Gestión Gubernamental (36, afuera Optativa I-III), Producción y Gestión Audiovisual (42), Gestión de Tecnologías de la Información (41, afuera Optativa I-II), Trabajo Social (32, afuera Seminario Optativo I-II), Producción de Bioimágenes (28). 216 materias, con año. El PDF "INGRESÁ AQUÍ" de Gestión Gubernamental (2026-10-16) es el folleto de la modalidad a distancia, no un plan.
- **NO cargables:** Lic. Administración (5.º año por orientaciones), Medicina (tabla con columna de ciclo, sin revisar a fondo), Abogacía (lista numerada de optativas "1. Derecho Romano" dentro del plan; sin revisar a fondo), Puericultura y Crianza (las materias 17-20 en una tabla sin año), Biotecnología (filas duplicadas en el texto del PDF, última tabla sin año, optativas con sub-ítems 37a/42b). Sin revisar: Prof. Educación Física (la página `/educacionfisica` no existe), Prof. Educación Especial (sin URL), Tec. Adm. y Gestión Universitaria.
- Cadena exportar→verificar UNPAZ (ofertas 44/48, 4 fuente caída; materias 478/497; las 216 nuevas, verificadas)→exportar completa (`Archivo: data/catalogo_depurado.json`). **Para revisar:** Prof. Universitario de Inglés (cargado antes) tiene 19 materias sin fuente y 7 que el documento no dice. Sin credenciales de producción ni de GitHub.
- Siguiente: UNPAZ (Prof. Inglés y las 3 sin revisar), UNSO (16), resto de UNO/UNAHUR/UNTREF.

## 2026-10-24 (57) — UNPAZ: Prof. Educación Física y Prof. Inglés
- Cargados por `planes_manuales` (hoja `data/planes_unpaz_profesorados.csv`, "lector plan_unpaz", vista previa OK y `--apply`; cotejados renglón por renglón con el PDF y 10 filas al azar de la base): Prof. Universitario en Educación Física (51, 4 años; página nueva `unpaz.edu.ar/puef`, folleto `2021-11-23 PUEF_plan A4.pdf`) y Prof. Universitario de Inglés (42, 4 años; `unpaz.edu.ar/profingles`, folleto 2023-05-22; afuera Optativa 1 y 2, que son menús). 93 materias.
- **Limpieza:** las 28 materias que tenía Inglés eran nombres rotos (columnas pegadas, "comunitaria", "UC especíﬁca de", el título como materia). Se borraron antes de cargar el plan nuevo; copia en `data/unpaz_materias_retiradas_2026-10-24.json` (local, ignorado por git). **En producción pueden estar esos nombres rotos: la importación de UNPAZ tiene que reemplazarlos.**
- **NO cargable:** Prof. Educación Especial (Sordas/os e Hipoacúsicas/os): el PDF del plan (`/educacionespecial1`) es de Illustrator con el texto en curvas (sin texto); el .docx "accesibilizado" es una conversión con los años mezclados ("Tercer año / Cuarto año" en medio de 2.º) y el verificador no lee .docx.
- **No publicada:** Tec. en Administración y Gestión Universitaria no está en `unpaz.edu.ar/carreras` ni en el buscador del sitio.
- Cadena exportar→verificar UNPAZ (ofertas 44/48, 4 fuente caída; materias 571/571, sin "sin fuente" ni "no lo dice")→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNSO (16), resto de UNO/UNAHUR/UNTREF.

## 2026-10-24 (58) — UNSO: 15 planes con `plan_unso`
- La base no tenía URL en ninguna oferta de UNSO. El sitio (`unso.edu.ar`, Angular) lee todo de `api.unsanisidro.edu.ar`: `/resumenes` (lista) y `/getPublicacion?tipo=3&id=…` (ficha), que enlaza "Plan de estudios" en `/files/carreras/…pdf`. Los PDF "Acercá la documentación" son instructivos de inscripción, no planes. `unsanisidro.edu.ar` es el dominio propio de UNSO (campus, SIU, mails): agregado a `OTROS_DOMINIOS` de `verificacion`.
- **Lector nuevo `plan_unso`** (`parsers/planes_sitios.py`, con 3 pruebas): tabla por año/cuatrimestre con horas a la derecha, nombres partidos en 2 renglones (horas arriba, abajo o en medio), número caído al renglón de abajo, total fuera de lugar (Criminalística), filas sin separar (Edición/Sonido, "Postproducción Audiovisual" / "1  64"). Devuelve nada si un grupo de filas no se puede separar.
- Cargadas por `planes_manuales` (hoja `data/planes_unso.csv`, "lector plan_unso", 15/15 aceptadas, `--apply`; 10 filas al azar cotejadas con el PDF): 476 materias con año (ver lista en estado.md). Afuera: electivas, y PPS/Trabajo final que el plan pone después del total anual, sin año.
- **NO cargable:** Lic. en Enfermería: el PDF ("Lic. en Enfermería Universitaria") trae solo 3 años y cierra en 2334 h; no es el plan entero.
- **Para revisar:** Tec. Análisis Contable figura con 4 años en la base y el plan tiene 3. Faltan en la base 4 CCC que UNSO publica (Instrumentación Quirúrgica, Gestión Educativa, Gestión Pública, Psicopedagogía), con plan legible salvo Gestión Pública CCC (palabras pegadas en el PDF).
- Cadena exportar→verificar UNSO (ofertas 15/16; materias 476/476)→exportar completa (`Archivo: data/catalogo_depurado.json`). La exportación llama "Profesorado de Educación Inicial" a la carrera que UNSO y la base llaman "en": alias agregado en `data/unso_planes.json` (local); esa oferta queda "no lo dice" por el nombre. Sin credenciales de producción ni de GitHub.
- Siguiente: resto de UNO/UNAHUR/UNTREF; cargar las 4 CCC de UNSO (re-correr la guía o `agregar_carrera`).

## 2026-10-24 (59) — UNTREF presenciales: Prof. Geografía y Lic. Gestión Educativa
- **Lector nuevo `plan_untref_anexo`** (`parsers/planes_sitios.py`, con 2 pruebas; registrado para los documentos de `untref.edu.ar` en `planes_documentos`): el anexo del Ministerio que enlaza "Programas para descargar", con cada nombre centrado sobre su fila y partido en varios renglones ("Introducción a la" / "592 Problemática del Mundo" / "Contemporáneo"). `plan_dngu` los partía. Por coordenadas (`-bbox-layout`): cada fila toma, en orden, los renglones cuyo centro promedio es el suyo (la cercanía sola falla: "Introducción a la" queda a 11,3 pt de dos filas); la última fila de una página puede cortar en su renglón; un renglón que sobra anula el plan. El año sigue de una página a la otra.
- **Arreglo en `_NO_ES_MATERIA`:** "^resolución" se comía "Resolución de Conflictos Institucionales" (Gestión Educativa); ahora deja pasar "Resolución de conflictos/problemas" (con prueba).
- Cargadas por `planes_manuales` (hoja `data/planes_untref_presenciales.csv`, generada con la salida de los lectores; vista previa y `--apply`; 10 filas al azar cotejadas): Prof. en Geografía (34, plan 2019, anexo RM 1145/2020; afuera electiva, seminarios optativo/electivo, idiomas sin cuatrimestre y TFA) y Lic. en Gestión Educativa (14, ciclo de 4 cuatrimestres, lista de la página: el PDF del plan 1998 es escaneado; afuera Trabajo Final). 48 materias con año.
- **NO cargables por ahora:** Lic. Artes Electrónicas: el lector la lee entera (23 materias del plan 2019, RM 1311/2020), pero el 4.º año son solo "Materia Optativa" y `planes_manuales` la rechaza por año faltante (regla correcta, no se forzó). Lic. Ciencias de la Educación: 13 materias de la página, rechazada porque la base le pone 4 años y la página dice "cuatro cuatrimestres" (articulación para profesores): **corregir la duración (2) o marcarla como ciclo** y recargar la hoja.
- Pendientes UNTREF: Edición y Políticas y Adm. de la Cultura (virtuales, ver bitácora 52), Geografía (Compl.), Instrumentación Quirúrgica (CCC), Resolución de Conflictos (CCC), Gestión Logística (escaneada).
- Cadena exportar→verificar UNTREF (ofertas 135/135, materias 2042/2042)→exportar completa (`Archivo: data/catalogo_depurado.json`). Tests: 887 OK. Sin credenciales de producción ni de GitHub.
- Siguiente: resto de UNO/UNAHUR; cargar las 4 CCC de UNSO; probar `plan_untref_anexo` con los demás anexos de UNTREF.

## 2026-10-24 (60) — UNAHUR: Tec. Inteligencia Artificial con `plan_untref_anexo`
- El PDF que enlaza la página (`RES-790-23-TEC-UNIV-EN-INTELIGENCIA-ARTIFICIAL.pdf`, anexo IF-2023-28361910) es el mismo formato de anexo del Ministerio que UNTREF: nombres centrados sobre su fila. `plan_untref_anexo` leía la 1.ª página y devolvía nada por la 2.ª: sin título de cuatrimestre arriba, la cabecera "COD ASIGNATURA" quedaba a menos de 30 pt de la primera fila y se tomaba como nombre. Arreglo: solo cuentan renglones debajo de "ASIGNATURA" (con prueba). Tests: 888 OK.
- Cargada por `planes_manuales` (hoja `data/planes_unahur_anexo.csv`, "lector plan_untref_anexo", vista previa OK y `--apply`; las 21 cotejadas renglón por renglón con el PDF): 21 materias en 5 cuatrimestres (años 1–3, duración 2,5). Afuera Electiva (menú de 6) y Créditos. "Asignatura UNAHUR" queda como materia, igual que en los profesorados (bitácora 55).
- **UNSO, 4 CCC:** no se agregan. Los lectores de guías descartan a propósito los ciclos de complementación (`es_ciclo` en `guias_nacionales._carrera`: no son carreras para empezar). Queda registrado como decisión, no como hueco.
- Cadena exportar→verificar UNAHUR (ofertas 52/52, materias 791/791)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: probar `plan_untref_anexo` con los demás PDF de UNAHUR por cuatrimestre (Metalurgia, Energía Eléctrica, Viverismo, Periurbana, Agronómica); resto de UNO.

## 2026-10-24 (61) — UNAHUR: Tec. Energía Eléctrica y Tec. Metalurgia con `plan_unahur_numerado`
- Las páginas de carrera enlazan dos PDF: la resolución del Ministerio (`RES-2394-16`, `RES-2396-16`: escaneos sin texto) y el folleto del plan (`2023/04/…Energia-Electrica-1.pdf`, `2023/05/…Metalurgia.pdf`), con tabla numerada por cuatrimestre. `plan_untref_anexo` y `plan_unahur_todos` no los leían; `plan_por_columnas` sí, pero sin año.
- **Lector nuevo `plan_unahur_numerado`** (`parsers/planes_sitios.py`, al final de `plan_unahur_todos`, con 2 pruebas): filas numeradas en orden bajo "1er. cuatrimestre"/"3° Cuatrimestre", nombre centrado sobre su fila (un renglón arriba del número, el resto abajo), dos cuatrimestres por año, corta en "Créditos". Un renglón que ninguna fila toma o un número fuera de orden anula el plan. "Metalurgia ll"/"Análisis Matemático l" (la tabla escribe eles) quedan "II"/"I", como dice el mismo documento en contenidos mínimos. Tests: 890 OK.
- Cargadas por `planes_manuales` (hoja `data/planes_unahur_numerado.csv`, vista previa 2/2 OK y `--apply`; cotejadas renglón por renglón con la tabla y 5 filas al azar de la base por carrera): Tec. Energía Eléctrica (21) y Tec. Metalurgia (21), años 1–3.
- **Siguen NO cargables:** Viverismo (nombres partidos debajo de filas con nombre y columna de campo; `plan_por_columnas` pega las palabras: "Introducciónal viverismo"), Periurbana (texto con ligaduras rotas "Biologıá", columnas mezcladas), Agronómica, Desarrollo Agrario y Tecnología de los Alimentos (ningún lector los toma; la resolución RES-1372-17 de Alimentos es escaneo). Sin revisar: Enfermería (RCS 385/2024).
- Cadena exportar→verificar UNAHUR (ofertas 52/52, materias 833/833)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNAHUR Enfermería y Viverismo (lector por posición de palabras); resto de UNO.

## 2026-10-24 (62) — UNAHUR: Lic. Enfermería con `plan_unahur_numerado`
- El plan (RCS 385/2024, EXP. 999/2024, punto 8 "Estructura del plan de estudio") es una tabla numerada por año ("1° Año"), con nombres centrados también en filas que tienen nombre ("Deontología y aspectos legales" / "27 del ejercicio profesional de la" / "Enfermería") y renglones de ciclo y del título intermedio entre filas.
- `plan_unahur_numerado` generalizado (con prueba nueva): títulos de año además de cuatrimestre; cada fila toma abajo tantos renglones como tiene arriba; de un renglón partido solo cuenta la primera columna ("Práctica pre- Profesional   Mensual"); saltea "Primer/Segundo Ciclo", el título intermedio ("Enfermero/a Universitario/a  1977 …") y el número de página; corta en "TOTAL"; "Créditos ACA" no es materia. Energía Eléctrica y Metalurgia dan exactamente lo ya cargado. Tests: 891 OK.
- Cargada por `planes_manuales` (hoja `data/planes_unahur_enfermeria.csv`, vista previa OK y `--apply`; cotejada renglón por renglón con la tabla y 6 filas al azar de la base): 39 materias, años 1–5 (afuera los 3 "Créditos ACA"). "Práctica pre- Profesional" queda como lo escribe el plan.
- Cadena exportar→verificar UNAHUR (ofertas 52/52, materias 872/872)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNAHUR Viverismo (lector por posición de palabras); resto de UNO.
- (62, después) `plan_unahur_numerado`: un renglón en blanco cierra la fila abierta (Desarrollo Agrario alinea los nombres arriba, no centrados; sigue dando nada). Las tres hojas cargadas salen iguales; `planes_documentos UNAHUR` (vista previa, sin `--apply`) solo propone Diseño Industrial, ya NO cargable por palabras pegadas.

## 2026-10-24 (63) — UNO: 8 planes con `plan_uno_codigos`
- Las páginas de carrera de UNO responden y enlazan "Plan de Estudios" (`images/documentos/escuelas/…pdf`, Abogacía en `images/contenidos/`). Son tablas con código por fila y el nombre partido arriba, al lado o abajo del código; `plan_uno` (pdfplumber) solo lee Matemática.
- **Lector nuevo `plan_uno_codigos`** (`parsers/planes_sitios.py`, `-bbox-layout`, con 3 pruebas; `plan_uno_todos` prueba `plan_uno` y después este, registrado para `uno.edu.ar` en `planes_documentos`): cada renglón de la columna del nombre es del código más cercano; un renglón casi igual de cerca de dos códigos, o lejos de todos dentro de la tabla, anula el plan. Control: la columna a la derecha del nombre tiene un valor por fila; si la cuenta no da (fila sin código), nada. Títulos de año en renglón propio ("1º AÑO", "Primer Año -Ciclo Inicial-"); notas, subtotales, "Título obtenido" y la capa "CICLO INICIAL Hs 2432" de las ingenierías no son materias. Tests: 894 OK.
- Cargadas por `planes_manuales` (hoja `data/planes_uno_codigos.csv`, vista previa 8/8 y `--apply`; listas cotejadas con el PDF y 16 filas al azar de la base, nombre literal y año): Abogacía (44), Ing. Ambiental (42, plan 2026), Ing. en Energía (41, plan 2026), Prof. Informática (40), Lic. Informática (48, plan 2022), Lic. Matemática (20, ciclo de 2 años, `plan_uno`), Tec. Acomp. Terapéutico (18), Tec. Investigación Criminal (18). 271 materias. Afuera electivas y optativas, Inglés (otros requisitos) y Trabajo Final de Matemática (sin cuatrimestre).
- **NO cargables por ahora:** Tec. Redes Informáticas (la Electiva no tiene código: el control la rechaza, si no se pegaba a "Análisis y Producción del Discurso"), Enfermería (sin códigos; columna de áreas y nombres partidos debajo), Odontología (PDF gráfico). Siguen sin plan Arquitectura, Ing. Química y Tec. Administración (bitácora 54).
- Cadena exportar→verificar UNO (ofertas 45/45, materias 490/490)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguiente: UNO Redes (permitir una fila sin código si tiene su propio valor), Enfermería; UNAHUR Viverismo; resto de UNTREF.

## 2026-10-24 (64) — UNO: Tec. Redes Informáticas con `plan_uno_codigos`
- `plan_uno_codigos` ajustado (2 pruebas): una fila sin código cuenta como fila propia solo si su nombre es "Electiva"/"Optativa N" y tiene su valor al lado, a menos de 30 pt de las filas con código (no es materia: `_agregar` la saca); cualquier otra fila sin código sigue anulando el plan. Además, el "2º AÑO" que cae sobre la columna de cuatrimestre ya no se cuenta como valor (era el otro motivo por el que Redes daba nada). Los 8 planes del ciclo 63 salen idénticos a la hoja cargada. Tests: 895 OK.
- Cargada por `planes_manuales` (hoja `data/planes_uno_redes.csv`, salida del lector; vista previa OK y `--apply`; cotejada renglón por renglón con el PDF y 7 filas al azar de la base): Tec. Redes Informáticas (21, años 1–3, duración 2,5). Afuera Electiva, Optativa I, Inglés I y Trabajo Social Obligatorio (otros requisitos).
- Cadena exportar→verificar UNO (ofertas 45/45, materias 511/511)→exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub.
- Siguen sin plan en UNO: Enfermería (sin códigos), Odontología (PDF gráfico), Arquitectura, Ing. Química, Tec. Administración.
- Siguiente: UNAHUR Viverismo (lector por posición de palabras); resto de UNTREF (corregir duración de Cs. de la Educación).

## 2026-10-24 (65) — UNTREF: duraciones de los ciclos y Lic. Cs. de la Educación
- La base tenía Cs. de la Educación en 4 años; la página dice "Duración y título: Cuatro cuatrimestres" y pide título de profesor (es un ciclo). `planes_manuales` rechazaba la hoja por eso ("faltan años").
- `parsers/duracion.py` (2 pruebas): entiende el rótulo "Duración y título"; "dos (2) años y medio (5 cuatrimestres)"; no cuenta el título que pide el ingreso ("de no menos de cuatro años de duración", el párrafo "Condiciones de ingreso" hasta "Plan de estudios"). `completar_duraciones --corregir`: también reemplaza una duración guardada que la página contradice por 2 años o más, salvo que el plan cargado tenga materias en un año posterior (Adm. Pública: la página da 2+2 años por tramo, queda en 4); `--apply` solo pisa si sigue la duración que vio la vista previa. Tests: 896 OK.
- Aplicado a UNTREF (vista previa revisada página por página): Cs. de la Educación 4→2; Historia (CCC), Instrumentación Quirúrgica (CCC), Gestión del Deporte (CCC), Gestión Educativa: 2; Geografía (Compl.): 2,5. Resolución de Conflictos sigue sin duración (la página no la dice).
- Cargada por `planes_manuales` (hoja `data/planes_untref_presenciales.csv`, vista previa OK y `--apply`; cotejada con la página): Lic. Cs. de la Educación, 13 materias, años 1–2 (afuera Trabajo Final).
- Cadena exportar→verificar UNTREF→exportar completa (`Archivo: data/catalogo_depurado.json`; UNTREF exporta 44 carreras y 2065 materias, Cs. de la Educación con 2 años y 13). Sin credenciales de producción ni de GitHub.
- Siguiente: correr `completar_duraciones --corregir` por otras universidades con ciclos (vista previa, revisar cada una); UNAHUR Viverismo (lector por posición de palabras).

## 2026-10-24 (66) — `completar_duraciones --corregir` en GBA, UNQ, UNR, UNLP
- Vista previa en UNSO, UNAHUR, UNPAZ, UNO, UNAJ, UNLZ, UNR y UNLP: ninguna duración contradicha ni nueva.
- UNQ: la vista previa bajaba Prof. Comunicación Social, Historia y Cs. Sociales de 4,5 a 2. Las páginas dicen "duración de 4 ½ años", y "2 (dos) años" es la de cada ciclo ("los que tienen respectivamente una duración"). Error del lector: NFKD deja "½" como "1⁄2" y no lo leía. Arreglado en `parsers/duracion.py` (con prueba; tests 897 OK). Repetida la vista previa, queda solo Lic. Geografía (CCC) → 2,5 ("posee una duración de 2 (dos) años y medio"), aplicada.
- Cadena exportar→verificar UNQ (ofertas 102/102, materias 321/321)→exportar completa (`Archivo: data/catalogo_depurado.json`). La CCC de Geografía no sale en la exportación (ciclo). Sin credenciales de producción ni de GitHub.
- Siguiente: UNAHUR Viverismo (lector por posición de palabras); resto de UNTREF (Edición, Políticas y Adm. de la Cultura).

## 2026-10-24 (67) — UNTREF Virtual: Tec. Edición y Lic. Políticas y Adm. de la Cultura
- Páginas `untrefvirtual.edu.ar/carrera/113` (Edición) y `/35` (Cultura). La de Edición copia el OCR de la RCS ("Edición 11", "lntroducción"); la de Cultura repite "Inglés Nivel II" donde va el III. Se usaron los documentos con texto que enlazan: anexo de la RM 1199/21 (Edición, 5 cuatrimestres) y punto 9 de la RCS 009/22 (Cultura, años I–IV; igual a la nómina de la RM 2587/23).
- Cargadas por `planes_manuales` (hoja `data/planes_untref_edicion_cultura.csv`, vista previa 2/2 y `--apply`; listas cotejadas con las tablas y filas al azar de la base): Edición 21 materias (años 1–3), Cultura 35 (años 1–4; afuera Trabajo Final, "otros requisitos").
- **Exportador:** `nombre_de_la_materia` tiraba toda materia con la palabra "editorial" (filtro de bibliografía): "Introducción al Diseño y Arte Editorial", "Diseño Editorial" (17), "Taller Editorial I"… ~80 en 31 universidades. Ahora solo descarta "Editorial" seguida del nombre de la editorial ("Editorial Paidós"). Además, en `tests/test_nombre_de_la_materia.py` un `if __name__` en el medio dejaba sin correr 2 pruebas; movido al final, una fallaba (la nota "(***) La carga horaria…" salía como materia) y se arregló. Tests: 900 OK.
- Cadena exportar→verificar (las 31 universidades afectadas; materias verificadas 185989→186058, no_lo_dice sin cambios)→exportar completa (`Archivo: data/catalogo_depurado.json`; 70 materias con "Editorial" exportadas). Sin credenciales de producción ni de GitHub.
- Siguen sin plan en UNTREF: Geografía (Compl.), Instrumentación Quirúrgica (CCC), Resolución de Conflictos (CCC), Gestión Logística (escaneada), Artes Electrónicas (NO cargable).
- Siguiente: UNTREF Geografía (Compl.) e Instrumentación Quirúrgica; UNAHUR Viverismo (lector por posición de palabras).

## 2026-10-24 (68) — UNTREF: Instrumentación Quirúrgica y Resolución de Conflictos (CCC)
- **Instrumentación Quirúrgica (CCC):** el PDF de la RM 205/17 está escaneado, pero la página tiene el plan en párrafos sueltos (sin guion) bajo cada cuatrimestre. `plan_untref` ahora los toma cuando el bloque no tiene guiones ni listas, y corta en "Otros requerimientos". Resultado: 19 materias, años 1–2. Afuera Inglés, Informática y Trabajo Final.
- **Resolución de Conflictos y Mediación (CCC):** se leyó el Anexo I de la RSPU 477/22, que no tiene columna de código y donde "CUATRIMESTRE" se sale de la columna del nombre. `plan_untref_anexo` ahora reconoce el título de cuatrimestre mirando el renglón entero. Resultado: 25 materias, años 1–3 (5 cuatrimestres). Afuera Trabajo Final. Inglés e Informática Nivel I–II entran porque el plan los pone en el 5.º cuatrimestre. Ni la página ni la resolución dan la duración en años, así que queda vacía.
- **Geografía (Compl.):** se leyó el anexo de la RM 1134/20. `plan_untref_anexo` ahora pasa los renglones que quedan debajo de la última fila de una página a la primera fila de la página siguiente ("Seminario de Investigación" + "167 Integrada"). Da 15 materias, iguales al PDF, pero `planes_manuales` la rechaza: "Seminario de Investigación Integrada" no aparece literal porque entre las dos partes están el pie y la cabecera de página. **NO cargada.** La fila queda en la hoja.
- Tests: 902 OK. Los planes que ya estaban cargados con `plan_untref_anexo` (Prof. Geografía y Artes Electrónicas de UNTREF, Tec. IA de UNAHUR) salen idénticos.
- Carga con `planes_manuales` (hoja `data/planes_untref_ccc.csv`, vista previa y `--apply`): 2 aceptadas, 44 materias. Se cotejaron 8 filas al azar de la base con el PDF o la página.
- Cadena exportar → verificar UNTREF (ofertas 135/135, materias 2117/2117) → exportar completa (`Archivo: data/catalogo_depurado.json`). Las dos carreras cargadas no salen en la exportación porque el exportador descarta los ciclos por diseño. Sin credenciales de producción ni de GitHub.
- Siguiente: decidir si el verificador acepta un nombre cortado por el salto de página (Geografía Compl.); UNAHUR Viverismo (lector por posición de palabras).

## 2026-10-24 (69) — USAL: 6 carreras nuevas de la vigilancia del 23/10
- La corrida del 23/10 (`data/vigilancia/usal_completo.json`) trae 80 carreras, contra 72 en la base. `load_usal --apply` **no se puede usar**: sincroniza las materias con las de la corrida, que no trae ninguna (los planes de USAL vienen de otros lectores), y borraría todas. Tampoco sirve `agregar_carrera`: su lector genérico toma "Secretaría de Ingreso" como nombre.
- Nuevo `load_usal --solo-nuevas`: agrega solo las carreras que no están (comparando las palabras del nombre) a la base y a `data/usal_completo.json` (carrera, oferta con su URL, arancel). No toca materias. El artefacto se valida antes de escribir. Ya no validaba antes de este ciclo (144 programas descubiertos contra 147 resueltos, por carreras agregadas a mano); ahora se revisa todo menos ese conteo.
- Cargadas (título, duración y facultad cotejados con cada página usando `parse_facts`): Agronomía (5), Actuario (4), Martillero y Corredor Universitario (Pregrado), Corrector Literario, Notariado (CCC a distancia, 1), Higiene y Seguridad en el Trabajo (CCC).
- Quedaron afuera:
  - "Dermatocosmiatría (Tecnicatura)": es la "Tecnicatura en Dermatocosmiatría" ya cargada (21 materias); se conserva el nombre de la base.
  - Los 2 Ciclos Pedagógicos: el título es "Profesor en (la disciplina que corresponda)", así que no es una carrera propia.
- Cambios en el parser de USAL: la marca "(pregrado)" del índice fija el nivel y sale del nombre; la duración se lee también como "(2 años y 1 cuatrimestre)" y "(2 años )".
- Cambio en `parsers/duracion.py`: "con planes de estudio de 3 (tres) años de duración" es el título que se pide para entrar, no la duración. Sin esto, `completar_duraciones` proponía 3 para Higiene (CCC), que dura 2; esa duración no se aplicó.
- Tests: 906 OK.
- Cadena exportar → verificar USAL (ofertas 142/142) → exportar. Salen 4 de las 6; las 2 CCC no, por diseño. Sin credenciales de producción ni de GitHub.
- Pendiente: Martillero (2,5) y Higiene CCC (2) siguen sin duración en la base. La próxima corrida de USAL ya las lee con el parser arreglado; hay que pasarlas a la base. Corrector Literario no tiene duración en la página: solo dice "Título Intermedio: 2 años y 1 cuatrimestre". Ninguna de las 6 tiene plan.
- Siguiente: planes de las 6 nuevas de USAL; Geografía (Compl.) de UNTREF; UNAHUR Viverismo.

## 2026-10-24 (70) — USAL: duraciones que da la página entre paréntesis
- `completar_duraciones USAL` no encontraba nada. Las páginas de USAL ponen la duración entre paréntesis, al lado del título ("(2 años y 1 cuatrimestre)"). `parsers.usal` lee ese formato y `parsers.duracion` no.
- Cambio: `completar_duraciones` ahora consulta el lector propio de la universidad (`LECTORES_PROPIOS`, por ahora solo USAL) cuando el lector general no da nada. Prueba nueva en `tests/test_duracion_leida.py`. Tests: 909 OK.
- Vista previa: 6 duraciones, cada una cotejada con el texto de su página. Aplicadas con `--apply`:
  - Martillero: 2,5
  - Higiene y Seguridad (CCC): 2
  - Organización de Eventos: 2,5
  - Corrección de Textos Digitales: 2,5
  - Yoga: 2,5
  - Arquitectura: 5
- Corrector Literario sigue sin duración: la página solo da la del título intermedio.
- Cadena exportar → verificar USAL (ofertas 142/142) → exportar completa (`Archivo: data/catalogo_depurado.json`). Sin credenciales de producción ni de GitHub; commit c67d1be queda local.
- Siguiente: planes de las 6 carreras nuevas de USAL; UCEMA (la vigilancia del 23/10 da 17 carreras contra 16); Geografía (Compl.) de UNTREF; UNAHUR Viverismo.

## 2026-10-24 (71) — UCEMA: BA nuevo, sitemap movido a cl2 y eventos fuera
- Hoy el sitemap de UCEMA lista las páginas bajo `cl2.ucema.edu.ar`, y el spider encontraba 0 programas. El validador lo dejaba pasar porque no había nada descubierto. Ahora el spider toma cualquier subdominio de ucema.edu.ar, pero lee y guarda la dirección pública (`ucema.edu.ar/...`). Además, un sitemap sin programas es un error. Esto evita un "CAYÓ" a 0 en la vigilancia de esta noche.
- "Experiencia Ucema" y "Elegí Tu Futuro" (y el posgrado "Mayo31 Charlas") son eventos: su "Duración" es "90 minutos" o "Martes 18 y Jueves 20 de octubre, 17h.". Ahora quedan excluidos. Los cursos que se cuentan en clases ("46 clases") siguen entrando.
- Nuevo `load_ucema --solo-carreras`: agrega las carreras que faltan en la base y completa solo los campos vacíos. No toca materias: `--apply` entero las borraría, como en USAL. La lectura pasa a ser `data/ucema_completo.json`. El README tenía `--apply` entero para UCEMA y USAL: corregido.
- Cargado (cotejado con cada página):
  - BA - Artes Liberales y Ciencias (Licenciado/a, 4 años, RM 2864/21).
  - Ing. en Inteligencia Artificial: título y 5 años, que estaban vacíos.
- Plan del BA con `planes_adaptador ucema --apply`: 32 materias, años 1–4. Los 32 nombres aparecen literal en la página y en su año (16 son electivas "libre"/"focalizada", como las publica el plan). Solo se escribió el BA; los otros 10 planes ya tenían materias.
- Tests: 914 OK. Cadena exportar → verificar UCEMA (ofertas 27/27, materias 577/577) → exportar completa (`Archivo: data/catalogo_depurado.json`). UCEMA queda con 15 carreras, todas con título, duración y plan.
- Sin credenciales de producción ni de GitHub.
- Siguiente: planes de las 6 carreras nuevas de USAL; Geografía (Compl.) de UNTREF; UNAHUR Viverismo.

## 2026-10-24 (72) — USAL: planes de Actuario, Agronomía y Martillero desde el folleto
- Las 6 carreras nuevas de USAL (ciclo 69) no tenían plan. `planes_folletos USAL` no tomaba ninguno: el lector OCR (`parsers/folleto_usal.py`) tiraba cada folleto entero por restos de la letra de duración ("e]", "[el", "<"), el nombre del título dibujado grande en medio de la columna ("Actuario", "Ingeniero Agrónomo") y "Idioma (Optativa 11)".
- Cambios en el lector: no toma palabras de más de 2,5 veces la altura mediana (el título mide 73–85 px y las materias ≤ 37 px); saca esos restos de duración; lee el numeral entre paréntesis; devuelve la "É" que tesseract pierde ("Etica" → "Ética"); un guion no cuenta como letra suelta ("Trabajo Integrador Final - TIF"). Prueba nueva en `tests/test_folleto_usal.py`. Tests: 917 OK.
- Cargadas con `planes_folletos --apply` (los 111 nombres y años cotejados uno por uno con la imagen del folleto):
  - Actuario: 43 materias (1.º–4.º).
  - Agronomía: 46 materias (1.º–5.º).
  - Martillero y Corredor Universitario: 22 materias (1.º–3.º; "Tasación y Venta de Bienes III" sale como II del OCR y la renumeración de la serie lo corrige).
- No cargables:
  - Corrector Literario: tesseract mezcla las dos columnas del folleto ("TERCERANÑO", renglones de dos materias). El lector lo descarta.
  - Notariado (CCC) e Higiene y Seguridad (CCC): son ciclos de complementación, que `planes_folletos` saltea por diseño.
- En la base ya hay 11 materias de USAL que empiezan con "Etica" (cargadas antes, probablemente la misma pérdida del OCR). No se tocaron: hay que cotejarlas con sus folletos.
- Cadena exportar → verificar USAL (ofertas 142/142; las materias de folleto quedan "sin_fuente" porque son una imagen) → exportar completa (`Archivo: data/catalogo_depurado.json`). Las 3 carreras salen con su plan.
- Sin credenciales de producción ni de GitHub.
- Siguiente: las 11 "Etica" de USAL contra sus folletos; Geografía (Compl.) de UNTREF; UNAHUR Viverismo.

## 2026-10-24 (73) — USAL: la "É" de "Ética" en los planes de folleto
- Las 11 materias de USAL que empezaban con "Etica" venían de los folletos leídos el 01/10 y el 14/10. Las 11 imágenes del caché están cotejadas a ojo: 10 dicen "Ética", y el folleto de Sociología imprime "Etica" sin tilde, así que ese nombre queda como está.
- Nuevo `planes_folletos --tildes [--apply]`: relee los folletos de las carreras que ya tienen plan. Solo renombra una materia si la lectura de hoy da el mismo nombre con "É" y en el mismo año. Prueba nueva en `tests/test_planes_folletos.py`.
- Corregidas 10, con su año: Ética Profesional en Com. Internacional (Francia), Periodismo, Relaciones Públicas y Publicidad (4.º), y en Administración, Musicoterapia y Cs. de la Comunicación (3.º); Ética en Nutrición y Sistemas de Información (4.º); Ética y Deontología en Veterinaria (3.º).
- Tests: 919 OK. Cadena exportar → verificar USAL (ofertas 142/142) → exportar completa (`Archivo: data/catalogo_depurado.json`).
- Sin credenciales de producción ni de GitHub.
- Siguiente: Geografía (Compl.) de UNTREF (el verificador tiene que unir un renglón cortado por el pie de página); UNAHUR Viverismo.

## 2026-10-24 (74) — UNTREF: Lic. Geografía (Complementación), 15 materias
- `verificacion.dice` ahora encuentra un nombre que el fin de página corta en dos: la cabeza unas palabras antes del pie ("Página 1 de 2") y la cola enseguida después de la cabecera de la página siguiente ("Seminario de Investigación" / "167 Integrada"). Solo para nombres de 15 letras o más, y con un pie de página entre las dos partes. Prueba nueva en `tests/test_verificacion.py`.
- `planes_manuales` toma "(Complementación)" en el nombre de la carrera como ciclo, igual que "(CCC)". El anexo de la RM 1134/20 la llama "ciclo de complementación curricular". Prueba en `tests/test_planes_manuales.py`.
- Cargada con `planes_manuales data/planes_untref_ccc.csv --apply`: 15 materias. Años: cuatrimestres 1.º–2.º → 1.º, 3.º–4.º → 2.º. Leídas de vuelta de la base y cotejadas con la tabla del anexo. Afuera: Idioma Extranjero I y TFA (otros requisitos) y Trabajo Final (5.º cuatrimestre).
- Tests: 920 OK. Cadena exportar → verificar UNTREF → exportar completa (`Archivo: data/catalogo_depurado.json`). La carrera no sale en el catálogo exportado porque el exportador deja afuera los ciclos (`_UN_CICLO`), igual que las CCC del ciclo 68. Queda en la base del scraper.
- Sin credenciales de producción ni de GitHub.
- Siguiente: UNAHUR Viverismo / Periurbana / Agronómica (ningún lector los toma); UCASAL (registrar el motivo de cada carrera).

## 2026-10-24 (75) — UCASAL: 8 planes desde el folleto y el motivo de cada carrera sin plan
- De 86 carreras de UCASAL, 6 tenían plan. Releídas las 86 páginas y sus PDF de "PLAN DE ESTUDIO".
- `plan_ucasal` tiraba folletos enteros con nombres completos: tomaba cualquier nombre de exactamente 20 letras por cortado ("DERECHO COMERCIAL II", "PRÁCTICA PROFESIONAL"). Ahora un folleto se toma por cortado solo si ningún nombre pasa de 20 letras. Además: lee "1° CUAT." y "CUATRIM.", une un nombre partido en dos renglones (si el primero termina en coma o "PARA", o si juntos siguen una serie del plan: "ADMINISTRACIÓN" / "FINANCIERA II"), saca la nota "(1)", y no toma un folleto con acentos graves ("PATOLOGÌA") ni con un menú de electivas en otra columna. `con_tildes` pone mayúscula tras "(" ("(Seguros de Cosas)"). Pruebas nuevas en `tests/test_planes_sitios.py`. Tests: 921 OK.
- Cargadas con `planes_documentos --apply UCASAL` (321 materias, todas presentes literal en su PDF; años contados por los rótulos "AÑO"): Administración de Empresas (49), Recursos Humanos (42), Criminalística (36), Relaciones Públicas e Institucionales (40), Diseño Gráfico (41), Diseño Industrial (42; el folleto imprime "Diseño de Produtos V", cargado tal cual), Gestión Eficiente de la Energía (42), Tec. Gestión de Bancos (29).
- Leídas y NO cargadas: Ing. Informática (el folleto es el plan 2015; la página publica un plan nuevo con nombres cortados) e Imagen y Sonido (las siglas TV, AV, EIAS quedarían "Tv", "Av", "Eias").
- Las 72 que siguen sin plan tienen su motivo en `relevamiento/planes_sin_cargar.json` (registro nuevo, por carrera): 35 plan de Alumnos cortado a 20 letras, 6 grillas abreviadas, 6 folletos abreviados, 6 ciclos, 3 escaneados, 3 tablas con nombre completo que ningún lector toma, y casos sueltos.
- Cadena exportar → verificar UCASAL (ofertas 122/122, materias 569/569) → exportar completa (`Archivo: data/catalogo_depurado.json`). Las 8 carreras salen con su plan.
- Sin credenciales de producción ni de GitHub.
- Siguiente: lector para las tablas de UCASAL con código y nombre completo (Relaciones Internacionales, Criminología); UNAHUR Viverismo / Periurbana / Agronómica.

## 2026-10-24 (76) — UCASAL: Lic. Criminología, 40 materias (tabla con código)
- Vigilancia sin novedades (Austral 1375→1095 materias, igual que el 23/10).
- `plan_ucasal` lee las planillas de Jurídicas ("Cód.", "MATERIA", "Régimen", un año por "PRIMER AÑO"): un nombre largo partido alrededor del código ("Negociación comercial, transcultural y" / "6 Semestral" / "relaciones humanas") se une; un código sin nombre en el texto descarta el plan entero. Corta en "SEMINARIOS ELECTIVOS". Prueba nueva en `tests/test_planes_sitios.py`. Tests: 922 OK.
- Cargada con `planes_documentos --apply UCASAL` (solo Criminología en el archivo de hallados): 40 materias, 10 por año. Leídas de vuelta de la base: 38 literales en el PDF; las 2 partidas (cód. 14 y 32) cotejadas con la imagen.
- NO cargables: Relaciones Internacionales (los 5 nombres de cód. 1–5 están dibujados como curvas, sin texto); Corretaje (CCC) se lee entero (20) pero es ciclo: `planes_documentos` lo saltea y el exportador lo deja afuera. Motivos en `relevamiento/planes_sin_cargar.json` (71 UCASAL sin plan).
- La vista previa vuelve a traer Ing. Informática e Imagen y Sonido: siguen afuera (bitácora 75); antes de `--apply UCASAL` hay que filtrar `data/planes_documentos.json`.
- Cadena exportar → verificar UCASAL (ofertas 122/122, materias 609/609; las 40 verificadas) → exportar completa (`Archivo: data/catalogo_depurado.json`).
- Sin credenciales de producción ni de GitHub.
- Siguiente: UNAHUR Viverismo / Periurbana / Agronómica; UCASAL Traductorado y Filosofía.

## 2026-10-24 (77) — UNAHUR: Ing. Agronómica (53) y Tec. Viverismo (23)
- Vigilancia sin novedades (Austral e ITBA, igual que el 23/10).
- `plan_unahur_numerado`: lee una fila con el campo enseguida del nombre ("1  Introducción al  CFE  4  64"), un nombre que sigue debajo de su fila en minúscula y sin renglón en blanco (Viverismo), saltea el lema de cada página ("“75 avo aniversario …”") y corta en "40 créditos externos". Prueba nueva y una ajustada en `tests/test_planes_sitios.py`. Tests: 923 OK.
- Cargadas con `planes_documentos --apply UNAHUR` (Diseño Industrial sacado del archivo de hallados): Ing. Agronómica 53 (EXP. 764/2024; afuera "Materia electiva" y el menú de electivas) y Tec. Viverismo 23 (EXP. 189/2020). Leídas de vuelta: las 76 literales en su PDF; años cotejados con la tabla.
- El verificador daba "Química general" e "Inglés I" como no_lo_dice: su caché del PDF de Viverismo era del 24/09 (solo pdfplumber, palabras pegadas). Borrada esa entrada de `data/verificacion/`, UNAHUR verifica 948/948.
- Siguen sin plan 6 de UNAHUR, cada una con su motivo en `relevamiento/planes_sin_cargar.json` (nuevo para UNAHUR): Desarrollo Agrario (nombres partidos ambiguos sin posición), Tecnología de los Alimentos, Educación (CCC), Diseño Industrial, Periurbana, Gestión del Mantenimiento.
- Cadena exportar → verificar UNAHUR → exportar completa (`Archivo: data/catalogo_depurado.json`). Las 2 salen con su plan.
- Sin credenciales de producción ni de GitHub.
- Siguiente: UCASAL Traductorado y Filosofía; lector por posición de palabras para Desarrollo Agrario.

## 2026-10-24 (78) — UCASAL: Traductorado Público en Inglés, 59 materias
- Vigilancia sin novedades (Austral, ITBA y Palermo, igual que el 23/10).
- `planes_documentos` no aceptaba el folleto: pide que el documento nombre la carrera y la hoja dice "TRADUCTOR PÚBLICO EN INGLÉS", no "Traductorado". `_nombra` ahora toma "traductor" por "traductorado". Prueba nueva en `tests/test_plan_folleto_austral.py`. Tests: 924 OK.
- Cargada con `planes_documentos --apply UCASAL` (Ing. Informática e Imagen y Sonido sacadas del archivo de hallados, bitácora 75): 59 materias (13/16/16/14), plan 2002. Leídas de vuelta de la base: las 59 en el PDF; años cotejados con la hoja. "Lingüística" lleva la diéresis que el folleto en mayúsculas no imprime ("LINGUÍSTICA").
- Sacada de `relevamiento/planes_sin_cargar.json` (70 UCASAL sin plan).
- Cadena exportar → verificar UCASAL (ofertas 122/122, materias 668/668) → exportar completa (`Archivo: data/catalogo_depurado.json`).
- Sin credenciales de producción ni de GitHub.
- Siguiente: UCASAL Filosofía (anexo de la DI-2026-392); lector por posición de palabras para Desarrollo Agrario (UNAHUR).

## 2026-10-24 (79) — UCASAL: Lic. Trabajo Social, 47 materias (anexo DNGU con código)
- Vigilancia sin novedades (la corrida del lanzador de hoy: Austral, ITBA y Palermo, igual que el 23/10).
- `plan_ucasal` lee el anexo del Ministerio con "COD / ASIGNATURA / REGIMEN" (`_ucasal_anexo_con_codigo`): el código y el régimen van en el renglón del medio del nombre, con tantos renglones arriba como abajo; así se separa la cola de un nombre de la cabeza del siguiente. Si la cuenta no cierra, si los códigos no van 1, 2, 3… o si un "AÑO" cae dentro de un nombre, no se lee. `con_tildes` deja en mayúsculas los números romanos con dos puntos ("IV: Familia") y las siglas entre paréntesis ("(TIF)"). Pruebas nuevas en `tests/test_planes_sitios.py` y `tests/test_titulo.py`. Tests: 926 OK.
- Cargada con `planes_documentos --apply UCASAL` (Ing. Informática e Imagen y Sonido sacadas del archivo de hallados): 47 materias (11/12/11/10/3), plan 2022 (IF-2022-01530633). Leídas de vuelta: las 47 literales en el PDF; años cotejados con la tabla.
- NO cargables (motivo en `relevamiento/planes_sin_cargar.json`, 69 UCASAL sin plan): Filosofía (el anexo de la DI-2026-392 abrevia y corta nombres: "INTERP.", "CONTEMP.", "FILOSOFIA CONTEMPO"); Imagen y Sonido (las siglas ya salen bien, pero el folleto pone "ELEMENTAL" en el renglón de "PENSAMIENTO FILOSÓFICO I").
- Cadena exportar → verificar UCASAL (ofertas 122/122, materias 715/715) → exportar completa (`Archivo: data/catalogo_depurado.json`). Trabajo Social sale con 47.
- Sin credenciales de producción ni de GitHub.
- Siguiente: UCASAL Producción Animal (plan completo de la facultad); lector por posición de palabras para Desarrollo Agrario (UNAHUR).

## 2026-10-24 (80) — UCASAL: Lic. Producción Animal, 45 materias (nómina del plan de la facultad)
- Vigilancia sin novedades (la corrida del lanzador de hoy: Austral, ITBA, Palermo y UADE, igual que el 23/10).
- `plan_ucasal` lee la "Nómina de Asignaturas por régimen de cursado" al final del plan completo de la facultad (`_ucasal_nomina`): una fila por materia con "1º Sem."; el código ("1.3") en la fila o en un renglón propio; una fila sin nombre lo tiene en el renglón siguiente ("2.11 … 2º Sem." / "Ética Profesional I"). Los nombres de cada año tienen que ser tantos como sus códigos, de 1 a n; si no, no se lee. Prueba nueva en `tests/test_planes_sitios.py`. Tests: 927 OK.
- Cargada con `planes_documentos --apply UCASAL` (Ing. Informática e Imagen y Sonido sacadas del archivo de hallados): 45 materias (12/12/10/11), plan 2019. Leídas de vuelta: las 45 literales en la tabla del PDF; años cotejados con la tabla. Ningún otro PDF del caché trae esa nómina.
- Sacada de `relevamiento/planes_sin_cargar.json` (68 UCASAL sin plan).
- Cadena exportar → verificar UCASAL (ofertas 122/122, materias 760/760) → exportar completa (`Archivo: data/catalogo_depurado.json`).
- Sin credenciales de producción ni de GitHub.
- Siguiente: lector por posición de palabras para Desarrollo Agrario (UNAHUR); UCASAL: los 3 PDF escaneados (OCR).
