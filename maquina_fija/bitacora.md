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
