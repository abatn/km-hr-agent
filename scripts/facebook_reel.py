"""Veröffentlicht ein Reel auf alle Facebook-Seiten aus `.env-social` (Graph API v26).

Ablauf je Seite (Reels-Upload in drei Phasen):
  1. POST /{page-id}/video_reels  upload_phase=start   -> video_id, upload_url
  2. POST upload_url (rupload)    Binärdatei hochladen
  3. POST /{page-id}/video_reels  upload_phase=finish  -> Veröffentlichung

Nutzung (auf dem VPS, dort liegen die Seitentokens):
  python3 scripts/facebook_reel.py --video /pfad/reel.mp4 --live
Ohne `--live` wird nichts gesendet (nur Prüfung der Datei und Konfiguration).
Protokoll: ergebnisse/social/<YYYY-MM-DD>/facebook-reel.json (ohne Tokens).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.environ.get("KMHR_SOCIAL_ENV", ROOT / ".env-social"))
GRAPH = "https://graph.facebook.com/v26.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v26.0"
PAGE_SLOTS = (("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"),
              ("FACEBOOK_PAGE2_ID", "FACEBOOK_PAGE2_ACCESS_TOKEN"))

CAPTION = (
    "Fachkräfte aus Nordafrika für Arbeitgeber in der EU. Der Mensch entscheidet. "
    "Mehr: https://jobs.hanibal-ai.com\n"
    "Main-d'œuvre d'Afrique du Nord pour les employeurs de l'UE. L'humain décide. "
    "Plus d'infos : https://jobs.hanibal-ai.com\n"
    "Skilled workers from North Africa for employers in the EU. Humans make the decisions. "
    "More: https://jobs.hanibal-ai.com\n"
    "عمالة مؤهلة من شمال أفريقيا لأصحاب العمل في الاتحاد الأوروبي. القرار للإنسان. "
    "المزيد: https://jobs.hanibal-ai.com\n"
    "KI-Hinweis: Dieser Beitrag wurde mit KI-Unterstützung erstellt. / "
    "AI note: created with AI support. / Note IA : créé avec l'aide de l'IA. / "
    "ملاحظة: أُنشئ بدعم من الذكاء الاصطناعي."
)


class ReelError(RuntimeError):
    pass


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _check(resp: requests.Response, phase: str) -> dict:
    if resp.status_code not in (200, 201):
        raise ReelError(f"{phase} HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def publish_reel(page_id: str, token: str, video: Path) -> dict:
    start = _check(requests.post(
        f"{GRAPH}/{page_id}/video_reels",
        data={"upload_phase": "start", "access_token": token}, timeout=60), "start")
    video_id, upload_url = start["video_id"], start["upload_url"]

    size = video.stat().st_size
    with video.open("rb") as fh:
        up = requests.post(
            upload_url if upload_url.startswith("http") else f"{RUPLOAD}/{video_id}",
            headers={"Authorization": f"OAuth {token}", "offset": "0",
                     "file_size": str(size), "Content-Type": "application/octet-stream"},
            data=fh, timeout=600)
    _check(up, "upload")

    fin = _check(requests.post(
        f"{GRAPH}/{page_id}/video_reels",
        data={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
              "description": CAPTION, "access_token": token}, timeout=120), "finish")
    return {"page_id": page_id, "video_id": video_id, "finish": fin}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Facebook-Reel auf alle Seiten veröffentlichen")
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--live", action="store_true", help="tatsächlich veröffentlichen")
    args = ap.parse_args(argv)

    if not args.video.is_file():
        raise SystemExit(f"Video fehlt: {args.video}")
    env = load_env(ENV_FILE)
    pages = [(env.get(i, ""), env.get(t, "")) for i, t in PAGE_SLOTS]
    pages = [(i, t) for i, t in pages if i and t]
    if not pages:
        raise SystemExit("Keine Seite mit ID und Token in .env-social")
    if not args.live:
        print(f"Dry-Check OK: {len(pages)} Seite(n), Video {args.video.stat().st_size} Bytes. "
              "Mit --live veröffentlichen.")
        return 0

    results = []
    for page_id, token in pages:
        try:
            results.append({"status": "published", **publish_reel(page_id, token, args.video)})
        except (ReelError, requests.RequestException) as exc:
            results.append({"status": "failed", "page_id": page_id, "error": str(exc)})
    log_dir = ROOT / "ergebnisse" / "social" / date.today().isoformat()
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "facebook-reel.json").write_text(
        json.dumps({"video": args.video.name, "caption": CAPTION, "results": results},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print(f"{r['page_id']}: {r['status']}")
    return 0 if all(r["status"] == "published" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
