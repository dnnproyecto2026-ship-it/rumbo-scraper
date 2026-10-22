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
