# Estado de la máquina fija

Actualizado: 2026-10-22 (ciclo 3)

## Producción
- Sin credenciales de producción en `~/Desktop/Rumbo/.env`: no se carga nada; lo listo queda abajo.

## Git
- Esta máquina no tiene credenciales de GitHub ni identidad de git: los commits quedan locales en la rama `maquina-fija` (autor del historial pasado con `-c user.name/-c user.email`). Hace falta que una persona haga `git push -u origin maquina-fija`.

## Listo para cargar (cuando haya credenciales, 01:00–08:00, lotes ≤ 8)
- UNQ (planes de UNQ por núcleos; ver bitácora 2026-10-22)

## Cola de próximas (ofertas de grado/pregrado sin plan, catálogo exportado 2026-10-16)
Prioridad CABA/GBA, Córdoba, Rosario, Salta:
1. UNQ — resto: páginas con orientaciones, bolsas de electivas que no suman, o tablas sin encabezado (Informática); ver bitácora
2. UNLP (87/151 sin plan)
3. UNC (77/114)
4. UCASAL (73/79) — lectura previa: el plan detallado corta cada nombre a 20 letras (commit 859fc87); falta registrar motivo por carrera
5. UNR (60/110)
6. UNLZ (32/38), UNAJ (23/24), UNTREF (19/44), UNSO (16/16), UNO (15/23), UNAHUR (14/34), UNPAZ (14/23)
7. Resto del país: UADER, UNT, UNSJ, UNCuyo, USPT, UNMdP, UNaM, UNNE…

## Bloqueadas (relevamiento/instituciones.json)
- UNdeC, UNSAM, UNLaR y otras 4: el sitio no deja leer sus carreras (registrado 2026-10-10).

- UB: 10 carreras virtuales (FEDEV) sin ficha en el sitio desde la corrida del 22/10; no re-importar UB desde una corrida nueva sin conservar esas 10. Maestría en Traducción (posgrado) sin leer.
- UBA: corrida de vigilancia del 22/10 incompleta (Psicología 403 en posgrados; Médicas y Farmacia sin descargar). No re-importar UBA desde ella; reintentar Médicas/Farmacia en otra rotación.

## Notas
- El relevamiento de universidades está casi completo (136 cargadas); el trabajo grande son los planes faltantes.
- `relevamiento/terciarios.json` no tiene campo de estado: es un índice nombre → CUE.
