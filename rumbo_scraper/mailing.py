"""Send one email campaign to a list of contacts who agreed to receive it.

    python -m rumbo_scraper.mailing campanas/<nombre> contactos.csv          # vista previa
    python -m rumbo_scraper.mailing campanas/<nombre> contactos.csv --apply  # envía

A campaign is a folder with `asunto.txt` and `cuerpo.html` (and optionally
`cuerpo.txt`); `{nombre}` in any of them is replaced by the contact's name.
The contacts file is a CSV with at least `email` and `consentimiento`; a row
is sent only when `consentimiento` says yes. Scraped addresses never carry
that column, so a list built from institution pages cannot be mailed by
mistake: consent has to be recorded by whoever collected the address.

Sending goes through the authenticated SMTP server of Rumbo's professional
Donweb mailbox, from the Contabo VPS, with the same variable names as the
Rumbo app: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
RUMBO_MAIL_FROM. Every message carries a footer and a
List-Unsubscribe header pointing to MAILING_BAJA (defaults to the sender).
Whoever replies BAJA is added to data/mailing/bajas.txt by hand, and that
list wins over any contacts file.

What was sent is appended to data/mailing/enviados.csv as it happens, so an
interrupted run resumes without mailing anyone twice, and the daily cap
(MAILING_LIMITE_DIARIO, 50 by default until the Donweb plan's limit is
confirmed) counts the
messages already sent today across every campaign.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import smtplib
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from pathlib import Path

from dotenv import load_dotenv

ESTADO = Path("data/mailing")
SI = {"si", "sí", "s", "yes", "y", "true", "1", "x"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PIE_TEXTO = (
    "\n\n--\nRecibís este correo porque aceptaste novedades de Rumbo. "
    "Para no recibir más, respondé con la palabra BAJA o escribí a {baja}."
)
PIE_HTML = (
    '<hr><p style="font-size:12px;color:#666">Recibís este correo porque aceptaste '
    "novedades de Rumbo. Para no recibir más, respondé con la palabra BAJA o "
    'escribí a <a href="mailto:{baja}?subject=BAJA">{baja}</a>.</p>'
)


def leer_campana(carpeta: Path) -> dict[str, str]:
    asunto = (carpeta / "asunto.txt").read_text(encoding="utf-8").strip()
    html = (carpeta / "cuerpo.html").read_text(encoding="utf-8")
    texto_path = carpeta / "cuerpo.txt"
    texto = texto_path.read_text(encoding="utf-8") if texto_path.exists() else _html_a_texto(html)
    if not asunto:
        raise ValueError(f"{carpeta}/asunto.txt está vacío")
    return {"nombre": carpeta.name, "asunto": asunto, "html": html, "texto": texto}


def _html_a_texto(html: str) -> str:
    texto = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>", "\n", html)
    texto = re.sub(r"<[^>]+>", "", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def leer_bajas(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        linea.strip().lower()
        for linea in path.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.startswith("#")
    }


def leer_enviados(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def elegir_destinatarios(
    filas: list[dict[str, str]],
    campana: str,
    bajas: set[str],
    enviados: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Return the contacts to mail and how many were left out, by reason."""
    ya = {e["email"].lower() for e in enviados if e.get("campana") == campana}
    vistos: set[str] = set()
    elegidos: list[dict[str, str]] = []
    motivos = {"sin_consentimiento": 0, "email_invalido": 0, "baja": 0, "ya_enviado": 0, "repetido": 0}
    for fila in filas:
        email = (fila.get("email") or "").strip().lower()
        if not EMAIL.match(email):
            motivos["email_invalido"] += 1
        elif (fila.get("consentimiento") or "").strip().lower() not in SI:
            motivos["sin_consentimiento"] += 1
        elif email in bajas:
            motivos["baja"] += 1
        elif email in ya:
            motivos["ya_enviado"] += 1
        elif email in vistos:
            motivos["repetido"] += 1
        else:
            vistos.add(email)
            elegidos.append({"email": email, "nombre": (fila.get("nombre") or "").strip()})
    return elegidos, motivos


def enviados_hoy(enviados: list[dict[str, str]], hoy: str) -> int:
    return sum(1 for e in enviados if e.get("fecha", "").startswith(hoy))


def armar_mensaje(campana: dict[str, str], contacto: dict[str, str], remitente: str, baja: str) -> EmailMessage:
    nombre = contacto["nombre"] or ""
    def completar(s: str) -> str:
        return s.replace("{nombre}", nombre).replace("{baja}", baja)
    msg = EmailMessage()
    msg["Subject"] = completar(campana["asunto"])
    msg["From"] = remitente
    msg["To"] = formataddr((nombre, contacto["email"])) if nombre else contacto["email"]
    msg["Message-ID"] = make_msgid(domain=parseaddr(remitente)[1].split("@")[-1] or None)
    msg["List-Unsubscribe"] = f"<mailto:{baja}?subject=BAJA>"
    msg.set_content(completar(campana["texto"]) + PIE_TEXTO.format(baja=baja))
    msg.add_alternative(completar(campana["html"]) + PIE_HTML.format(baja=baja), subtype="html")
    return msg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campana", type=Path, help="carpeta con asunto.txt y cuerpo.html")
    parser.add_argument("contactos", type=Path, help="CSV con email, nombre, consentimiento")
    parser.add_argument("--apply", action="store_true", help="enviar de verdad")
    parser.add_argument("--prueba", help="mandar solo a esta dirección, sin registrar nada")
    parser.add_argument("--pausa", type=float, default=2.0, help="segundos entre envíos")
    args = parser.parse_args(argv)

    load_dotenv()
    campana = leer_campana(args.campana)
    remitente = os.getenv("RUMBO_MAIL_FROM", "").strip()
    baja = os.getenv("MAILING_BAJA", "").strip() or parseaddr(remitente)[1]
    limite = int(os.getenv("MAILING_LIMITE_DIARIO", "50"))
    ESTADO.mkdir(parents=True, exist_ok=True)
    enviados_path = ESTADO / "enviados.csv"
    enviados = leer_enviados(enviados_path)
    hoy = datetime.now().strftime("%Y-%m-%d")

    if args.prueba:
        destinatarios = [{"email": args.prueba.strip().lower(), "nombre": "Prueba"}]
        motivos: dict[str, int] = {}
    else:
        with args.contactos.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        if filas and "consentimiento" not in filas[0]:
            print("El CSV no tiene la columna 'consentimiento': no se manda nada.")
            return 2
        destinatarios, motivos = elegir_destinatarios(filas, campana["nombre"], leer_bajas(ESTADO / "bajas.txt"), enviados)

    cupo = max(0, limite - enviados_hoy(enviados, hoy))
    tanda = destinatarios if args.prueba else destinatarios[:cupo]
    print(f"Campaña: {campana['nombre']} — asunto: {campana['asunto']}")
    print(f"Destinatarios válidos: {len(destinatarios)}; hoy entran {len(tanda)} (cupo diario {limite}, quedan {cupo})")
    for motivo, n in motivos.items():
        if n:
            print(f"  fuera por {motivo}: {n}")
    if not args.apply:
        for c in tanda[:5]:
            print(f"  vista previa → {c['email']}")
        print("VISTA PREVIA (no se envió nada). Agregá --apply para enviar.")
        return 0

    faltan = [v for v in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "RUMBO_MAIL_FROM") if not os.getenv(v)]
    if faltan:
        print("Faltan variables: " + ", ".join(faltan))
        return 2

    # A test send is not recorded, so it never opens the real log.
    log_path = Path(os.devnull) if args.prueba else enviados_path
    nuevo = not args.prueba and (not enviados_path.exists() or enviados_path.stat().st_size == 0)
    ok = 0
    puerto = int(os.environ["SMTP_PORT"])
    smtp_cls = smtplib.SMTP_SSL if puerto == 465 else smtplib.SMTP
    with smtp_cls(os.environ["SMTP_HOST"], puerto, timeout=60) as smtp, \
            log_path.open("a", encoding="utf-8", newline="") as log:
        if puerto != 465:
            smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        escritor = csv.DictWriter(log, fieldnames=["campana", "email", "fecha"])
        if nuevo:
            escritor.writeheader()
        for contacto in tanda:
            try:
                smtp.send_message(armar_mensaje(campana, contacto, remitente, baja))
            except smtplib.SMTPRecipientsRefused:
                print(f"  rechazado: {contacto['email']}")
                continue
            ok += 1
            if not args.prueba:
                escritor.writerow({"campana": campana["nombre"], "email": contacto["email"], "fecha": datetime.now().isoformat(timespec="seconds")})
                log.flush()
            time.sleep(args.pausa)
    print(f"Enviados: {ok}. Pendientes para otro día: {len(destinatarios) - len(tanda)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
