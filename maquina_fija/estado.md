# Estado de la máquina fija

Actualizado: 2026-10-23 (ciclo 35: UNR Enfermería cargada; falta exportar y verificar desde el lanzador)
- Exportado 2026-10-22 (noche, 18): UNLP, UNQ y UCEMA incluidos.

- Cadena exportar→verificar→exportar del ciclo 20 completada (2026-10-23, incluye Agroecología); termina con `Archivo: data/catalogo_depurado.json`.

- Ciclo 18: cadena exportar→verificar→exportar completa (cierra con `Archivo: data/catalogo_depurado.json`, incluye Geografía y Letras Modernas de UNC). No hay procesos míos corriendo.

- Ciclo 20: `verificar_catalogo` se cortó dos veces por el límite de tiempo de la herramienta (10 min y 2 h); no hay procesos míos corriendo. Falta la verificación completa y la exportación final (`Archivo: ...`) con Letras Clásicas y Corrección Literaria; el catálogo exportado (09:39) ya los incluye pero sin verificar. Reintentar fuera de la herramienta de segundo plano (lanzador).

## Producción
- Sin credenciales de producción en `~/Desktop/Rumbo/.env`: no se carga nada; lo listo queda abajo.

## Git
- Esta máquina no tiene credenciales de GitHub ni identidad de git: los commits quedan locales en la rama `maquina-fija` (autor del historial pasado con `-c user.name/-c user.email`). Hace falta que una persona haga `git push -u origin maquina-fija`.

## Listo para cargar (cuando haya credenciales, 01:00–08:00, lotes ≤ 8)
- UNR: Enfermería (40), Ing. Agronómica (44), Farmacia (39), Bioquímica (38), Lic. Biotecnología (30), Lic. Cs. y Tec. de los Alimentos (36), Prof. Química (27), Ingeniería Electrónica (45), Lic. Diseño Gráfico (30), Lic. Diseño Industrial (34)
- UNC: Ciencias Biológicas (33), Prof. Letras Clásicas (27), Lic. Letras Clásicas (25), Tec. Corrección Literaria (21), Prof. Geografía (25), Prof. Letras Modernas (33), Lic. Cine y Artes Audiovisuales (32), Prof. en Teatro (31), Lic. Sociología (34), Lic. Ciencia Política (35), Abogacía (38), Trad. Alemán (30) y Lic. Italianas (31)
- UNQ (planes de UNQ por núcleos; ver bitácora 2026-10-22)
- UNLP (Económicas: Tec. Cooperativismo y Ciencia de Datos; Tec. Agroecología; Humanidades: Lic. Francés Or. Ling. y Lit. (14 c/u), Lic. Inglés Or. Lingüística (17), Lic. Inglés Or. Literaria (17), Lic. Cs. de la Educación (23), Lic. Bibliotecología, 5 carreras de Lenguas (Prof. Inglesas/Francesas/Portugués, Trad. Inglés/Francés); 3 tecnicaturas de Periodismo + Trabajo Social completo + 2 tecnicaturas de Odontología: Lic., Profesorado, Tec. Gestión del riesgo y Fonoaudiología, Psicología (Lic., 34 materias), Odontología (grado, 60 materias; duración del catálogo 6 vs 5 años de la tabla: revisar); ver bitácora)

## Cola de próximas (ofertas de grado/pregrado sin plan, catálogo exportado 2026-10-16)
Prioridad CABA/GBA, Córdoba, Rosario, Salta:
1. UNQ — resto: páginas con orientaciones, bolsas de electivas que no suman, o tablas sin encabezado (Informática); ver bitácora
2. UNLP (84/151 sin plan; Periodismo hecho salvo Lic., Profesorado y Com. Popular; Trabajo Social: Lic. y Profesorado hechos, Trabajo Social completo; Odontología hecha; Psicología: Profesorado pendiente (PDF escaneado, OCR incompleto, ver bitácora 17); Exactas bloqueada por el sitio (timeout + certificado TLS), reintentar; Económicas hecha; Agrarias: Agroecología hecha, Agronómica/Forestal/Cultivos Protegidos con PDF escaneado (bitácora 20), Prod. Agropecuaria sin buscar; Humanidades: Lenguas hecha (5); Lic. Francés Ling. y Lit. hechas (bitácora 7); Prof. Cs. de la Educación ya estaba cargado (33 materias, coincide con el PDF A2002; Humanidades completa); Lic. Inglés Lingüística hecha (bitácora 5); Lic. Cs. de la Educación hecha (1.º–4.º, bitácora 4), Lic. Bibliotecología hecha, fuente: PDFs en las páginas de carrera de fahce.unlp.edu.ar)
3. UNC (75/114): Sociales hecha salvo Trabajo Social; Derecho: Abogacía hecha (bitácora 10), Notariado y Prof. Cs. Jurídicas NO cargables por ahora (errata en nombre / semestre inferido, bitácora 11); BLOQUEADAS por Anubis: FCM, FAUD, Agropecuarias, Psicología, Comunicación, Belgrano; FFyH y Monserrat sin respuesta (bitácora 9); Lenguas hecha (bitácora 13); Artes: Prof. Teatro y Lic. Cine hechos (bitácora 15), Lic. Teatro NO cargable (OCR, bitácora 14); Artes Visuales (orientaciones mezcladas) y Música (OCR/romanos rotos) NO cargables (bitácora 16), Artes cerrada; FFyH: Prof. Geografía y Prof. Letras Modernas hechos (bitácora 17), el resto escaneos sin texto; FAMAF cerrada (Analista y tecnicaturas sin plan publicado, bitácora 19); Letras: Clásicas y Corrección hechas, Lic. Letras Modernas NO cargable (orientaciones, bitácora 20), Prof. Letras Clásicas hecho (bitácora 21); Biológicas hecha (bitácora 22), Prof. Biológicas y Trabajo Social NO cargables (bitácora 22); solo queda Odontología (sin respuesta)
4. UCASAL (73/79) — lectura previa: el plan detallado corta cada nombre a 20 letras (commit 859fc87); falta registrar motivo por carrera
5. UNR (59/110): FCEIA Electrónica hecha (bitácora 23); Diseño Gráfico y Diseño Industrial hechas (bitácora 28-29); Indumentaria sin plan publicado y Arquitectura con plan en transición (bitácora 30); resto de FCEIA escaneado o plan vigente sin texto; FCEcon ya cargada (planes_unr.py); Derecho NO cargable (escaneo, plan 2012 posiblemente no vigente, bitácora 25); Veterinaria ya cargada (47; falta Fisiología, bitácora 27); Lic. Química NO cargable (dos planes en la página, bitácora 33); falta Medicina, Humanidades, Arquitectura, Agronómica, Bioquímica, Farmacia, Psicología, Enfermería (listar desde la base, no desde el catálogo exportado)
6. UNLZ (32/38), UNAJ (23/24), UNTREF (19/44), UNSO (16/16), UNO (15/23), UNAHUR (14/34), UNPAZ (14/23)
7. Resto del país: UADER, UNT, UNSJ, UNCuyo, USPT, UNMdP, UNaM, UNNE…

## Bloqueadas (relevamiento/instituciones.json)
- UNdeC, UNSAM, UNLaR y otras 4: el sitio no deja leer sus carreras (registrado 2026-10-10).

- UB: 10 carreras virtuales (FEDEV) sin ficha en el sitio desde la corrida del 22/10; no re-importar UB desde una corrida nueva sin conservar esas 10. Maestría en Traducción (posgrado) sin leer.
- UBA: corrida de vigilancia del 22/10 incompleta (Psicología 403 en posgrados; Médicas y Farmacia sin descargar). No re-importar UBA desde ella; reintentar Médicas/Farmacia en otra rotación.

## Notas
- El relevamiento de universidades está casi completo (136 cargadas); el trabajo grande son los planes faltantes.
- `relevamiento/terciarios.json` no tiene campo de estado: es un índice nombre → CUE.
- UTDT: Maestría en Finanzas ya no publica su lista de materias (corrida 22/10); no re-importar UTDT desde esa corrida sin conservar las 88 del baseline.
