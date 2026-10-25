"""Autonomer Social-Media-Agent für den KM-HR-Agent.

Prinzip: Wahrnehmen → Planen → Handeln → Beobachten.

- Wahrnehmen: liest ausschließlich aggregierte, PII-freie Daten aus der HR-DB
  (aktive Stellen, Bewerbungs-/Einstellungszahlen). Keine Kandidatennamen,
  E-Mails, Telefonnummern, CV-Texte oder Bewerbungsinhalte.
- Planen: erzeugt einen 7-Tage-Redaktionsplan (Plattform × Thema × Sprache).
- Handeln: rendert einen Post und publiziert ihn über LinkedIn/Facebook/
  Instagram — **nur** im Modus ``live`` und mit ``KMHR_SOCIAL_AUTO_PUBLISH=1``.
  Default ist Dry-Run: der exakte API-Payload landet in der Outbox, ohne Netz.
- Beobachten: schreibt Plan, Post, Payload, Status und Lauf-Log nach
  ``ergebnisse/social/<YYYY-MM-DD>/`` (heute-datiert, gitignored).

Spec: ``knowledge/system/social-automation.md``
Agent: ``marketing/social-agent.md``
Entscheidung/Quellen: ``marketing/ENTSCHEIDUNG.md``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("KMHR_DB_PATH") or (PROJECT_ROOT / "data" / "feedback.db"))
OUT_ROOT = PROJECT_ROOT / "ergebnisse" / "social"
LOG_FILE = PROJECT_ROOT / "logs" / "social-agent.log"
def site_url() -> str:
    return os.environ.get("KMHR_SOCIAL_SITE_URL", "https://jobs.hanibal-ai.com").rstrip("/")

PLATFORMS = ("linkedin", "facebook", "instagram")
TOPICS = ("new_jobs", "candidate_tips", "hiring_stats")
LANGUAGE_BY_PLATFORM = {"linkedin": "de", "facebook": "fr", "instagram": "fr"}

# Wochentag (0=Montag) → (Plattform, Thema). Ein Post pro Tag, 7 Tage/Woche.
WEEK_PLAN = {
    0: ("linkedin", "new_jobs"),
    1: ("facebook", "new_jobs"),
    2: ("linkedin", "candidate_tips"),
    3: ("facebook", "hiring_stats"),
    4: ("instagram", "hiring_stats"),
    5: ("facebook", "candidate_tips"),
    6: ("linkedin", "hiring_stats"),
}

TEXT = {
    "de": {
        "new_jobs_title": "Neue Stellen für Fachkräfte aus Nordafrika",
        "new_jobs_intro": "Aktuell offen bei Arbeitgebern in DE, FR und CH:",
        "tips_title": "Bewerbungstipp der Woche",
        "tips": [
            "Lebenslauf auf Deutsch oder Französisch: Rolle, Jahre, Skills und Sprachlevel klar nennen.",
            "Sprachzertifikat (CEFR) beilegen – A2/B1 reicht für viele Einstiegsstellen, B2 öffnet mehr Türen.",
            "Visum- und Anerkennungsfragen früh klären: Der Agent liefert die Schritte, bevor du dich bewirbst.",
        ],
        "stats_title": "Recruiting-Zahlen dieser Woche",
        "stats": "Aktive Stellen: {jobs} · Bewerbungen: {applications} · Eingeladen: {invited} · Eingestellt: {hired}",
        "cta": "Jetzt Stellen ansehen",
        "ai": "KI-unterstützt erstellt.",
    },
    "en": {
        "new_jobs_title": "New roles for skilled professionals from North Africa",
        "new_jobs_intro": "Currently open with employers in DE, FR and CH:",
        "tips_title": "Application tip of the week",
        "tips": [
            "Keep your CV in German or French: role, years, skills and language level up front.",
            "Add a CEFR language certificate – A2/B1 opens entry roles, B2 opens more doors.",
            "Clarify visa and recognition questions early: the agent prepares the steps before you apply.",
        ],
        "stats_title": "Recruiting numbers this week",
        "stats": "Active roles: {jobs} · Applications: {applications} · Invited: {invited} · Hired: {hired}",
        "cta": "View open roles",
        "ai": "AI-assisted.",
    },
    "fr": {
        "new_jobs_title": "Nouveaux postes pour les talents d'Afrique du Nord",
        "new_jobs_intro": "Actuellement ouverts chez des employeurs en DE, FR et CH :",
        "tips_title": "Conseil de candidature de la semaine",
        "tips": [
            "CV en allemand ou en français : poste, années, compétences et niveau de langue en évidence.",
            "Joignez un certificat de langue CEFR – A2/B1 suffit pour débuter, B2 ouvre plus de portes.",
            "Clarifiez tôt le visa et la reconnaissance : l'agent prépare les étapes avant votre candidature.",
        ],
        "stats_title": "Chiffres du recrutement cette semaine",
        "stats": "Postes actifs : {jobs} · Candidatures : {applications} · Invités : {invited} · Recrutés : {hired}",
        "cta": "Voir les postes",
        "ai": "Créé avec l'aide de l'IA.",
    },
    "ar": {
        "new_jobs_title": "وظائف جديدة للكفاءات من شمال أفريقيا",
        "new_jobs_intro": "مفتوحة حالياً لدى أصحاب العمل في ألمانيا وفرنسا وسويسرا:",
        "tips_title": "نصيحة التقديم لهذا الأسبوع",
        "tips": [
            "اكتب السيرة الذاتية بالألمانية أو الفرنسية: الوظيفة وسنوات الخبرة والمهارات ومستوى اللغة.",
            "أرفق شهادة لغة CEFR – مستوى A2/B1 يكفي للبداية وB2 يفتح فرصاً أكثر.",
            "وضّح مبكراً مسائل التأشيرة والاعتراف: الوكيل يجهز الخطوات قبل التقديم.",
        ],
        "stats_title": "أرقام التوظيف هذا الأسبوع",
        "stats": "وظائف نشطة: {jobs} · طلبات: {applications} · مدعوون: {invited} · تم التعيين: {hired}",
        "cta": "عرض الوظائف",
        "ai": "أُنشئ بمساعدة الذكاء الاصطناعي.",
    },
}


class SocialError(RuntimeError):
    """Fehler im Social-Agenten (Konfiguration, PII, API)."""


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)


def load_env_social(path: Path | None = None) -> None:
    """Lädt .env-social, ohne bestehende Umgebungsvariablen zu überschreiben."""
    env_file = path or Path(os.environ.get("KMHR_SOCIAL_ENV_FILE") or (PROJECT_ROOT / ".env-social"))
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def read_aggregates(db_path: Path) -> dict[str, Any]:
    """Nur PII-freie Aggregate/öffentliche Stellendaten."""
    conn = _connect_ro(db_path)
    try:
        jobs = [
            dict(zip(("id", "titel", "standort", "land", "stellentyp",
                      "gehaltsrahmen_min", "gehaltsrahmen_max", "erstellt_am"), row))
            for row in conn.execute(
                "SELECT id, titel, standort, land, stellentyp, gehaltsrahmen_min, "
                "gehaltsrahmen_max, erstellt_am FROM jobs WHERE status='aktiv' "
                "AND titel NOT LIKE 'E2E-Beweis%' AND titel NOT LIKE '%Teststelle%' "
                "ORDER BY erstellt_am DESC, id DESC LIMIT 12"
            )
        ]
        counts = dict(conn.execute(
            "SELECT status, COUNT(*) FROM applications GROUP BY status"
        ).fetchall())
        active_jobs = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='aktiv'").fetchone()[0]
    finally:
        conn.close()
    return {
        "jobs": jobs,
        "active_jobs": active_jobs,
        "applications": sum(counts.values()),
        "invited": counts.get("eingeladen", 0),
        "hired": counts.get("eingestellt", 0),
    }


def build_weekly_plan(day: date, language: str | None = None) -> list[dict[str, Any]]:
    monday = day - timedelta(days=day.weekday())
    plan: list[dict[str, Any]] = []
    for offset in range(7):
        d = monday + timedelta(days=offset)
        platform, topic = WEEK_PLAN[offset]
        lang = language or LANGUAGE_BY_PLATFORM[platform]
        plan.append({
            "day": d.isoformat(),
            "weekday": d.strftime("%A"),
            "platform": platform,
            "topic": topic,
            "language": lang,
            "format": "image" if platform == "instagram" else "text_link",
        })
    return plan


def assert_no_pii(text: str) -> None:
    """Harte Sperre gegen personenbezogene Daten in öffentlichen Posts."""
    checks = (
        (r"[\w.+-]+@[\w-]+\.[\w.-]+", "E-Mail-Adresse"),
        (r"(?<!\d)\+?\d[\d\s/()-]{7,}\d(?!\d)", "Telefonnummer"),
        (r"\b(?:Kandidat|Bewerber|Candidate)\s*#\s*\d+", "Kandidaten-ID"),
        (r"\bcandidate_id\b|\bapplication_id\b", "interne Personen-ID"),
    )
    for pattern, label in checks:
        if re.search(pattern, text, re.I):
            raise SocialError(f"DSGVO-Guard: {label} im Post-Text gefunden")


def _job_lines(agg: dict[str, Any], lang: str) -> list[str]:
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for job in agg["jobs"]:
        key = (str(job.get("titel", "")), str(job.get("standort", "")))
        if key in seen:
            continue
        seen.add(key)
        place = " · ".join(x for x in (job.get("standort"), job.get("land")) if x)
        lines.append(f"• {job['titel']}" + (f" ({place})" if place else ""))
        if len(lines) == 3:
            break
    if not lines:
        lines.append("• " + TEXT[lang]["new_jobs_intro"])
    return lines


def render_post(entry: dict[str, Any], agg: dict[str, Any]) -> dict[str, Any]:
    lang = entry["language"] if entry["language"] in TEXT else "de"
    t = TEXT[lang]
    topic = entry["topic"]
    if topic == "new_jobs":
        title = t["new_jobs_title"]
        body = t["new_jobs_intro"] + "\n" + "\n".join(_job_lines(agg, lang))
        link = f"{site_url()}/candidate/stellen"
    elif topic == "candidate_tips":
        title = t["tips_title"]
        tip = t["tips"][date.fromisoformat(entry["day"]).toordinal() % len(t["tips"])]
        body = tip
        link = f"{site_url()}/candidate/stellen"
    elif topic == "hiring_stats":
        title = t["stats_title"]
        body = t["stats"].format(
            jobs=agg["active_jobs"], applications=agg["applications"],
            invited=agg["invited"], hired=agg["hired"])
        link = site_url()
    else:
        raise SocialError(f"unbekanntes Thema: {topic}")

    text = f"{body}\n\n{link}\n\n{t['ai']}"
    assert_no_pii(text)
    post_id = hashlib.sha256(
        f"{entry['day']}|{entry['platform']}|{topic}|{text}".encode()).hexdigest()[:16]
    image_url = os.environ.get("INSTAGRAM_IMAGE_URL", "").strip()
    return {
        "post_id": post_id,
        "day": entry["day"],
        "platform": entry["platform"],
        "topic": topic,
        "language": lang,
        "title": title,
        "text": text,
        "link": link,
        "image_url": image_url if entry["platform"] == "instagram" else None,
    }


class DryRunAdapter:
    def publish(self, post: dict[str, Any]) -> dict[str, Any]:
        return {"status": "dry_run", "platform": post["platform"],
                "payload": self.payload(post)}

    def payload(self, post: dict[str, Any]) -> dict[str, Any]:
        if post["platform"] == "linkedin":
            return {
                "url": "https://api.linkedin.com/rest/posts",
                "headers": {"Authorization": "Bearer <LINKEDIN_ACCESS_TOKEN>",
                            "LinkedIn-Version": os.environ.get("LINKEDIN_VERSION", "202506"),
                            "X-Restli-Protocol-Version": "2.0.0"},
                "json": linkedin_body(post),
            }
        if post["platform"] == "facebook":
            return {
                "url": "https://graph.facebook.com/v21.0/<FACEBOOK_PAGE_ID>/feed",
                "data": {"message": post["text"], "link": post["link"],
                         "access_token": "<FACEBOOK_PAGE_ACCESS_TOKEN>"},
            }
        return {
            "url": "https://graph.facebook.com/v21.0/<INSTAGRAM_USER_ID>/media",
            "data": {"image_url": post.get("image_url") or "<INSTAGRAM_IMAGE_URL>",
                     "caption": post["text"], "access_token": "<INSTAGRAM_ACCESS_TOKEN>"},
        }


def linkedin_body(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "author": "<LINKEDIN_AUTHOR_URN>",
        "commentary": post["text"],
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED",
                         "targetEntities": [], "thirdPartyDistributionChannels": []},
        "content": {"article": {"source": post["link"], "title": post["title"]}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


class LinkedInAdapter:
    def __init__(self) -> None:
        self.token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
        self.author = os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()
        self.version = os.environ.get("LINKEDIN_VERSION", "202506")

    def publish(self, post: dict[str, Any]) -> dict[str, Any]:
        if not self.token or not self.author:
            raise SocialError("LINKEDIN_ACCESS_TOKEN/LINKEDIN_AUTHOR_URN fehlen")
        body = linkedin_body(post)
        body["author"] = self.author
        resp = requests.post(
            "https://api.linkedin.com/rest/posts",
            headers={"Authorization": f"Bearer {self.token}",
                     "LinkedIn-Version": self.version,
                     "X-Restli-Protocol-Version": "2.0.0",
                     "Content-Type": "application/json"},
            json=body, timeout=30)
        if resp.status_code not in (200, 201):
            raise SocialError(f"LinkedIn HTTP {resp.status_code}: {resp.text[:300]}")
        return {"status": "published", "platform": "linkedin",
                "external_id": resp.headers.get("x-restli-id") or resp.headers.get("location", "")}


class FacebookAdapter:
    def __init__(self) -> None:
        self.page_id = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
        self.token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()

    def publish(self, post: dict[str, Any]) -> dict[str, Any]:
        if not self.page_id or not self.token:
            raise SocialError("FACEBOOK_PAGE_ID/FACEBOOK_PAGE_ACCESS_TOKEN fehlen")
        if "|" in self.token:
            raise SocialError(
                "Facebook App Access Token (app_id|app_secret) kann keine Page-Posts "
                "erstellen. Nutze den OAuth-Flow (scripts/social_oauth.py facebook) "
                "und den daraus erzeugten Page Access Token.")
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{self.page_id}/feed",
            data={"message": post["text"], "link": post["link"],
                  "access_token": self.token}, timeout=30)
        if resp.status_code not in (200, 201):
            raise SocialError(f"Facebook HTTP {resp.status_code}: {resp.text[:300]}")
        return {"status": "published", "platform": "facebook",
                "external_id": str(resp.json().get("id", ""))}


class InstagramAdapter:
    def __init__(self) -> None:
        self.user_id = os.environ.get("INSTAGRAM_USER_ID", "").strip()
        self.token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()

    def publish(self, post: dict[str, Any]) -> dict[str, Any]:
        if not self.user_id or not self.token:
            raise SocialError("INSTAGRAM_USER_ID/INSTAGRAM_ACCESS_TOKEN fehlen")
        if not post.get("image_url"):
            raise SocialError("INSTAGRAM_IMAGE_URL fehlt (Instagram braucht ein Bild)")
        create = requests.post(
            f"https://graph.facebook.com/v21.0/{self.user_id}/media",
            data={"image_url": post["image_url"], "caption": post["text"],
                  "access_token": self.token}, timeout=30)
        if create.status_code not in (200, 201):
            raise SocialError(f"Instagram create HTTP {create.status_code}: {create.text[:300]}")
        creation_id = create.json().get("id")
        publish = requests.post(
            f"https://graph.facebook.com/v21.0/{self.user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": self.token}, timeout=30)
        if publish.status_code not in (200, 201):
            raise SocialError(f"Instagram publish HTTP {publish.status_code}: {publish.text[:300]}")
        return {"status": "published", "platform": "instagram",
                "external_id": str(publish.json().get("id", ""))}


def adapter_for(platform: str):
    return {"linkedin": LinkedInAdapter, "facebook": FacebookAdapter,
            "instagram": InstagramAdapter}[platform]()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def publish_post(post: dict[str, Any], mode: str, auto_publish: bool) -> dict[str, Any]:
    """Dry-Run ist Default; live nur mit explizitem Auto-Publish + Token."""
    if mode != "live":
        return DryRunAdapter().publish(post)
    if not auto_publish:
        result = DryRunAdapter().publish(post)
        result["reason"] = "approval_required (KMHR_SOCIAL_AUTO_PUBLISH != 1)"
        return result
    return adapter_for(post["platform"]).publish(post)


def run_once(day: date, db_path: Path, mode: str = "dry_run",
             force: bool = False, platform: str | None = None,
             language: str | None = None) -> dict[str, Any]:
    if os.environ.get("KMHR_SOCIAL_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        log("Social-Agent deaktiviert (KMHR_SOCIAL_ENABLED=0) — skip")
        return {"status": "disabled"}

    agg = read_aggregates(db_path)
    plan = build_weekly_plan(day, language)
    if platform:
        plan = [p for p in plan if p["platform"] == platform]
    entry = next((p for p in plan if p["day"] == day.isoformat()), None)
    if entry is None:
        if platform:
            raise SocialError(f"kein Plan-Eintrag für {day} auf {platform}")
        entry = plan[0]
    post = render_post(entry, agg)

    out_dir = OUT_ROOT / day.isoformat()
    plan_path = out_dir / "plan.json"
    post_path = out_dir / f"{post['platform']}-{post['topic']}.md"
    outbox_path = out_dir / f"{post['platform']}-{post['topic']}.json"
    if outbox_path.exists() and not force:
        log(f"skip: {outbox_path} existiert bereits (idempotent)")
        return {"status": "skipped", "path": str(outbox_path)}

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(plan_path, {"generated_at": datetime.now().isoformat(timespec="seconds"),
                            "db": str(db_path), "plan": build_weekly_plan(day, language)})
    post_path.write_text(
        f"# {post['title']}\n\n{post['text']}\n\n---\n"
        f"Plattform: {post['platform']} · Sprache: {post['language']} · "
        f"Post-ID: {post['post_id']}\n", encoding="utf-8")

    auto_publish = os.environ.get("KMHR_SOCIAL_AUTO_PUBLISH", "0").strip().lower() in ("1", "true", "yes")
    try:
        result = publish_post(post, mode, auto_publish)
    except Exception as exc:  # noqa: BLE001 - Status muss persistiert werden
        result = {"status": "failed", "error": str(exc)[:500]}
    record = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "auto_publish": auto_publish,
        "post": post,
        "result": result,
        "source": {k: v for k, v in agg.items() if k != "jobs"},
    }
    _write_json(outbox_path, record)
    log(f"{post['platform']}/{post['topic']} → {result.get('status')} ({outbox_path})")
    return {"status": result.get("status"), "path": str(outbox_path), "post": post}


def main(argv: list[str] | None = None) -> int:
    load_env_social()
    ap = argparse.ArgumentParser(description="Autonomer Social-Media-Agent (KM-HR-Agent)")
    ap.add_argument("--once", action="store_true", help="heutigen Plan-Eintrag ausführen")
    ap.add_argument("--plan", action="store_true", help="nur Wochenplan schreiben")
    ap.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="SQLite-Pfad (read-only)")
    ap.add_argument("--platform", choices=PLATFORMS, help="nur diese Plattform")
    ap.add_argument("--language", choices=tuple(TEXT), help="erzwingt Sprache")
    ap.add_argument("--dry-run", action="store_true", default=True, help="kein Netz (Default)")
    ap.add_argument("--live", action="store_true", help="live posten (nur mit Auto-Publish)")
    ap.add_argument("--force", action="store_true", help="vorhandene Outbox überschreiben")
    args = ap.parse_args(argv)
    day = date.fromisoformat(args.date)
    mode = "live" if args.live else "dry_run"

    if args.plan:
        plan = build_weekly_plan(day, args.language)
        path = OUT_ROOT / day.isoformat() / "plan.json"
        _write_json(path, {"generated_at": datetime.now().isoformat(timespec="seconds"),
                           "db": args.db, "plan": plan})
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    result = run_once(day, Path(args.db), mode=mode, force=args.force,
                      platform=args.platform, language=args.language)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in ("failed",) else 1


if __name__ == "__main__":
    sys.exit(main())
