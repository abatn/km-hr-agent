#!/usr/bin/env python3
"""
E-Mail-MCP-Server für KM-HR-Agent
Sendet E-Mails via Yahoo SMTP (kein OAuth nötig, nur App-Passwort).
Quelle: https://github.com/bedro96/email-send-mcp (Inspiration)
"""

from fastmcp import FastMCP
import smtplib
import os
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# i18n (Variante B, P2b 07.10.2026): framework-freie Kernschicht (gettext,
# kein NiceGUI). Spec: knowledge/system/i18n-runner-chain.md §7.1.
# Defensiv: das Skript liegt im Projekt-Root, sys.path[0] ist das bei
# `python3 mcp-email-server.py` – der Insert schützt den Import trotzdem.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from webui.i18n_core import tr

# .env laden
env_file = Path(__file__).parent / ".env-email"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

mcp = FastMCP("email-sender")

# Konfiguration aus Umgebungsvariablen
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.mail.yahoo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # App-Passwort
DEFAULT_FROM_NAME = os.getenv("DEFAULT_FROM_NAME", "KM-HR-Agent")


@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    is_html: bool = False
) -> str:
    """
    Sendet eine E-Mail via Yahoo SMTP.

    Args:
        to: Empfänger (kommasepariert für mehrere)
        subject: Betreff
        body: Nachrichtentext
        cc: CC-Empfänger (optional)
        bcc: BCC-Empfänger (optional)
        is_html: True wenn HTML-Body

    Returns:
        Erfolgsmeldung oder Fehler
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return "FEHLER: SMTP_credentials nicht konfiguriert. Setze SMTP_USERNAME und SMTP_PASSWORD in .env"

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{DEFAULT_FROM_NAME} <{SMTP_USERNAME}>"
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        # Alle Empfänger sammeln
        recipients = [to.strip() for to in to.split(",")]
        if cc:
            recipients.extend([cc.strip() for cc in cc.split(",")])
        if bcc:
            recipients.extend([bcc.strip() for bcc in bcc.split(",")])

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            # Fix 12.09.2026 (Live-Test): Tippfehler SMCP_ -> SMTP_
            server.sendmail(SMTP_USERNAME, recipients, msg.as_string())

        return f"OK|Gesendet an {to}|{subject}|{datetime.now().strftime('%Y-%m-%d %H:%M')}"

    except smtplib.SMTPAuthenticationError:
        return "FEHLER: SMTP-Auth fehlgeschlagen. Prüfe App-Passwort."
    except smtplib.SMTPException as e:
        return f"FEHLER: SMTP-Fehler: {str(e)}"
    except Exception as e:
        return f"FEHLER: {str(e)}"


@mcp.tool()
def send_interview_invitation(
    to: str,
    candidate_name: str,
    position: str,
    company: str,
    date: str,
    time: str,
    duration_minutes: int = 45,
    format: str = "Online (Jitsi Meet – kostenlos)",
    match_score: int = 0,
    language: str = "de"
) -> str:
    """
    Sendet eine personalisierte Interview-Einladung.

    Args:
        to: E-Mail des Kandidaten
        candidate_name: Name des Kandidaten
        position: Stellenbezeichnung
        company: Unternehmen
        date: Datum (z.B. "Freitag, 15. Oktober 2026")
        time: Uhrzeit (z.B. "10:00 Uhr")
        duration_minutes: Dauer in Minuten
        format: Interview-Format
        match_score: Match-Score (0-100)
        language: Zielsprache der Mail (de/en/fr/ar; Default de – Altverhalten)

    Returns:
        Erfolgsmeldung
    """
    subject = tr("Einladung zum Vorstellungsgespräch – {position}",
                 language, position=position)

    body = "\n\n".join([
        tr("Sehr geehrte(r) {0},", language).format(candidate_name),
        tr("wir freuen uns, Ihnen unser Interesse an Ihrer Bewerbung "
           "mitteilen zu können.", language),
        tr("Nach der Prüfung Ihres Lebenslaufs haben wir festgestellt, dass "
           "Ihre Qualifikationen hervorragend zu unserer Position als "
           "**{position}** bei **{company}** passen.", language,
           position=position, company=company),
        tr("**Wir laden Sie herzlich ein zum:**", language),
        "\n".join([
            tr("- **Datum:** {date}", language, date=date),
            tr("- **Uhrzeit:** {time}", language, time=time),
            tr("- **Format:** {format}", language, format=format),
            tr("- **Dauer:** ca. {duration_minutes} Minuten", language,
               duration_minutes=duration_minutes),
        ]),
        tr("**Agenda:**", language) + "\n" + tr(
            "1. Vorstellung des Unternehmens (5 Min.)\n"
            "2. Technische Fragen (20 Min.)\n"
            "3. Kulturelles Fit (10 Min.)\n"
            "4. Fragen des Kandidaten (10 Min.)", language),
        tr("**Vorbereitung:**", language) + "\n" + tr(
            "Bitte bringen Sie folgende Unterlagen mit:\n"
            "- Aktuellen Lebenslauf\n"
            "- Zeugnisse\n"
            "- Referenzen (falls vorhanden)", language),
        "---\n" + tr("**Rechtliche Hinweise:**", language) + "\n" + "\n".join([
            tr("- 🔒 DSGVO Art. 13: Ihre Daten werden gemäß "
               "Art. 6(1)(b) DSGVO verarbeitet.", language),
            tr("- ⚖️ EU AI Act Art. 50: Diese Einladung wurde mit "
               "KI-Unterstützung erstellt.", language),
        ]),
        tr("Mit freundlichen Grüßen,\nHR Team", language) + f"\n{company}\n",
    ])

    return send_email(to, subject, body)


@mcp.tool()
def send_pre_screen_invitation(
    to: str,
    candidate_name: str,
    position: str,
    meet_url: str,
    date: str,
    time: str,
    questions_summary: str,
    language: str = "de"
) -> str:
    """
    Sendet eine Pre-Screening-Einladung mit Meeting-Link.

    Args:
        to: E-Mail des Kandidaten
        candidate_name: Name
        position: Stelle
        meet_url: Jitsi-Link
        date: Datum
        time: Uhrzeit
        questions_summary: Zusammenfassung der Fragen
        language: Zielsprache der Mail (de/en/fr/ar; Default de – Altverhalten)

    Returns:
        Erfolgsmeldung
    """
    subject = tr("Pre-Screening: {position}", language, position=position)

    body = "\n\n".join([
        tr("Sehr geehrte(r) {0},", language).format(candidate_name),
        tr("wir möchten Sie herzlich zu einem kurzen Pre-Screening für die "
           "Position als **{position}** einladen.", language, position=position),
        "\n".join([
            tr("**Meeting-Details:**", language),
            tr("- **Link:** {meet_url}", language, meet_url=meet_url),
            tr("- **Datum:** {0}", language).format(date),
            tr("- **Uhrzeit:** {uhrzeit}", language, uhrzeit=time),
            tr("- **Dauer:** ca. 30 Minuten", language),
        ]),
        "\n".join([
            tr("**Themen:**", language),
            questions_summary,
        ]),
        tr("Bitte bestätigen Sie Ihre Teilnahme kurz per Rück-Mail.", language),
        tr("Mit freundlichen Grüßen,\nHR Team", language),
    ])

    return send_email(to, subject, body)


if __name__ == "__main__":
    mcp.run()
