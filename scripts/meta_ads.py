"""Meta Marketing API (Facebook/Instagram-Anzeigen) – Live-Pfad mit PAUSED-first.

Warum dieses Modul: `scripts/ads_agent.py` konnte bisher nur Dry-Run-Payloads
bauen; `--live` brach ab. Für eine echte Schaltung fehlten vier Dinge, die hier
gekapselt sind:

1. **Vorabprüfung** (`preflight`): Token, `ads_management`, Werbekonto,
   Zahlungsmittel, Währung, Seite, DSA-Pflichtfelder. Jede Lücke wird als
   konkreter Blocker mit Lösungsschritt ausgegeben – kein stiller Fehlschlag.
2. **Anlegen** (`launch`): Kampagne -> Ad Set -> Creative -> Ad, **immer PAUSED**
   und **immer** `special_ad_categories=["EMPLOYMENT"]`. Es gibt keinen Code-Pfad,
   der eine Anzeige aktiv anlegt.
3. **Aktivieren** (`activate`): separat, nur nach ausdrücklicher Bestätigung,
   setzt Kampagne, Ad Set und Ad gemeinsam auf ACTIVE (sonst liefert Meta nicht
   aus). Vorher wird das Tagesbudget gegen Cap und Konto-Spend-Cap geprüft.
4. **Geheimhaltung**: Das Token steht nur im Request, nie in Fehlermeldungen,
   Logs oder Ergebnisdateien (`_redact`).

Grenzen, die Code nicht löst (bewusst): Zahlungsmittel im Werbekonto,
Identitäts-/Unternehmensprüfung, Meta-Richtlinienprüfung der Anzeige. Diese
Punkte erscheinen als Blocker im Preflight.

Konfiguration (`.env-social` oder Prozessumgebung):
    META_AD_ACCOUNT_ID=act_123...        # Pflicht für live
    META_ADS_ACCESS_TOKEN=...            # Pflicht; Fallback FACEBOOK_PAGE_ACCESS_TOKEN
    FACEBOOK_PAGE_ID=...                 # Pflicht (Anzeigengeber)
    META_GRAPH_VERSION=v26.0             # Default
    META_ADS_CURRENCY=EUR                # Default; Cap rechnet in EUR
    META_DSA_BENEFICIARY=...             # Pflicht für EU-Zielgruppe (DSA)
    META_DSA_PAYOR=...
    META_VIDEO_ID=...                    # optional: bereits hochgeladenes Ad-Video
    META_VIDEO_URL=...                   # optional: öffentliche MP4-URL für Upload
    META_VIDEO_PATH=...                  # optional: lokale MP4-Datei für Upload
    META_VIDEO_THUMBNAIL_PATH=...         # Pflicht bei Video: lokales Vorschaubild
    META_VIDEO_THUMBNAIL_URL=...          # Alternative: öffentliches Vorschaubild

Video-Ads: Ist eine Video-Quelle konfiguriert, lädt `launch` sie über
`POST /act_<id>/advideos` hoch und baut ein `video_data`-Creative. Ohne
Video-Quelle bleibt der bisherige Link-Ad-Pfad (`link_data`) aktiv.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import requests

GRAPH_HOST = "https://graph.facebook.com"
GRAPH_VIDEO_HOST = "https://graph-video.facebook.com"

ACCOUNT_STATUS = {
    1: "ACTIVE",
    2: "DISABLED",
    3: "UNSETTLED",
    7: "PENDING_RISK_REVIEW",
    8: "PENDING_SETTLEMENT",
    9: "IN_GRACE_PERIOD",
    100: "PENDING_CLOSURE",
    101: "CLOSED",
}

# Konto-Status, bei denen eine Auslieferung nicht möglich ist.
BLOCKING_STATUS = {2, 3, 7, 100, 101}

OBJECTIVE = "OUTCOME_TRAFFIC"
OPTIMIZATION_GOAL = "LANDING_PAGE_VIEWS"
BILLING_EVENT = "IMPRESSIONS"
BID_STRATEGY = "LOWEST_COST_WITHOUT_CAP"


class MetaAdsError(RuntimeError):
    pass


class Transport(Protocol):
    """HTTP-Abstraktion, damit Tests ohne Netz laufen."""

    def request(self, method: str, url: str, params: dict[str, str],
                data: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        ...

    def upload(self, url: str, params: dict[str, str],
               file_path: str) -> tuple[int, dict[str, Any]]:
        ...


class RequestsTransport:
    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def request(self, method: str, url: str, params: dict[str, str],
                data: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        resp = requests.request(method, url, params=params, data=data,
                                timeout=self.timeout)
        return resp.status_code, self._json(resp)

    def upload(self, url: str, params: dict[str, str],
               file_path: str) -> tuple[int, dict[str, Any]]:
        with open(file_path, "rb") as fh:
            resp = requests.post(url, params=params,
                                 files={"source": fh}, timeout=self.timeout)
        return resp.status_code, self._json(resp)

    @staticmethod
    def _json(resp: requests.Response) -> dict[str, Any]:
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text[:300]}


def _redact(value: Any, token: str) -> Any:
    """Entfernt das Token rekursiv aus Fehlertexten/Ergebnissen."""
    if not token:
        return value
    if isinstance(value, str):
        return value.replace(token, "<TOKEN>")
    if isinstance(value, dict):
        return {k: _redact(v, token) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, token) for v in value]
    return value


def cents(eur: float) -> int:
    return int(round(eur * 100))


@dataclass
class MetaConfig:
    ad_account_id: str = ""
    token: str = ""
    page_id: str = ""
    version: str = "v26.0"
    currency: str = "EUR"
    dsa_beneficiary: str = ""
    dsa_payor: str = ""
    video_id: str = ""
    video_url: str = ""
    video_path: str = ""
    video_thumbnail_url: str = ""
    video_thumbnail_path: str = ""

    @property
    def act(self) -> str:
        acct = self.ad_account_id.strip()
        if not acct:
            return ""
        return acct if acct.startswith("act_") else f"act_{acct}"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "MetaConfig":
        e = env if env is not None else os.environ
        token = (e.get("META_ADS_ACCESS_TOKEN")
                 or e.get("FACEBOOK_ADS_ACCESS_TOKEN")
                 or e.get("FACEBOOK_PAGE_ACCESS_TOKEN")
                 or "").strip()
        return cls(
            ad_account_id=(e.get("META_AD_ACCOUNT_ID") or "").strip(),
            token=token,
            page_id=(e.get("FACEBOOK_PAGE_ID") or "").strip(),
            version=(e.get("META_GRAPH_VERSION") or "v26.0").strip().lstrip("v"),
            currency=(e.get("META_ADS_CURRENCY") or "EUR").strip().upper(),
            dsa_beneficiary=(e.get("META_DSA_BENEFICIARY") or "").strip(),
            dsa_payor=(e.get("META_DSA_PAYOR") or "").strip(),
            video_id=(e.get("META_VIDEO_ID") or "").strip(),
            video_url=(e.get("META_VIDEO_URL") or "").strip(),
            video_path=(e.get("META_VIDEO_PATH") or "").strip(),
            video_thumbnail_url=(e.get("META_VIDEO_THUMBNAIL_URL") or "").strip(),
            video_thumbnail_path=(e.get("META_VIDEO_THUMBNAIL_PATH") or "").strip(),
        )

    @property
    def has_video(self) -> bool:
        return bool(self.video_id or self.video_url or self.video_path)

    @property
    def version_tag(self) -> str:
        return f"v{self.version.strip().lstrip('v')}"

    def missing(self) -> list[str]:
        missing = []
        if not self.ad_account_id:
            missing.append("META_AD_ACCOUNT_ID")
        if not self.token:
            missing.append("META_ADS_ACCESS_TOKEN")
        if not self.page_id:
            missing.append("FACEBOOK_PAGE_ID")
        return missing


@dataclass
class MetaAdsClient:
    cfg: MetaConfig
    transport: Transport = field(default_factory=RequestsTransport)
    _uploaded_video_id: str = field(default="", init=False, repr=False)
    _uploaded_image_hash: str = field(default="", init=False, repr=False)

    # ── HTTP ────────────────────────────────────────────────────────────────
    def _call(self, method: str, path: str, params: dict[str, Any] | None = None,
              data: dict[str, Any] | None = None,
              host: str = GRAPH_HOST) -> dict[str, Any]:
        if not self.cfg.token:
            raise MetaAdsError("META_ADS_ACCESS_TOKEN fehlt")
        p = {k: str(v) for k, v in (params or {}).items()}
        p["access_token"] = self.cfg.token
        body = None
        if data is not None:
            body = {}
            for key, value in data.items():
                body[key] = value if isinstance(value, str) else json.dumps(
                    value, ensure_ascii=False)
        url = f"{host}/{self.cfg.version_tag}/{path.lstrip('/')}"
        status, payload = self.transport.request(method, url, p, body)
        payload = _redact(payload, self.cfg.token) if isinstance(payload, dict) else payload
        if status >= 400 or (isinstance(payload, dict) and "error" in payload):
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            msg = err.get("message") or f"HTTP {status}"
            detail = " — ".join(x for x in (err.get("error_user_title"),
                                            err.get("error_user_msg")) if x)
            raise MetaAdsError(
                f"{method} {path}: {msg} "
                f"(code={err.get('code')}, subcode={err.get('error_subcode')})"
                + (f" — {detail}" if detail else ""))
        if not isinstance(payload, dict):
            raise MetaAdsError(f"{method} {path}: unerwartete Antwort")
        return payload

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        return self._call("GET", path, params)

    def post(self, path: str, **data: Any) -> dict[str, Any]:
        return self._call("POST", path, data=data)

    # ── Video-Upload ────────────────────────────────────────────────────────
    def upload_video(self, video_url: str = "", video_path: str = "") -> str:
        """Lädt ein Video in die Ad-Video-Bibliothek des Werbekontos.

        Reihenfolge: bereits konfigurierte META_VIDEO_ID -> lokale Datei
        (multipart `source`) -> öffentliche URL (`file_url`). Gibt die
        `video_id` zurück, die das Creative referenziert.
        """
        if self._uploaded_video_id:
            return self._uploaded_video_id
        if self.cfg.video_id:
            self._uploaded_video_id = self.cfg.video_id
            return self.cfg.video_id
        if not self.cfg.act:
            raise MetaAdsError("META_AD_ACCOUNT_ID fehlt: Video kann nicht hochgeladen werden")

        local_path = os.path.expanduser(video_path or self.cfg.video_path)
        remote_url = (video_url or self.cfg.video_url).strip()
        if not local_path and not remote_url:
            raise MetaAdsError(
                "Keine Video-Quelle: META_VIDEO_ID, META_VIDEO_URL oder "
                "META_VIDEO_PATH setzen")

        endpoint = f"{GRAPH_VIDEO_HOST}/{self.cfg.version_tag}/{self.cfg.act}/advideos"
        params = {"access_token": self.cfg.token}
        if local_path:
            if not os.path.isfile(local_path):
                raise MetaAdsError(f"META_VIDEO_PATH nicht gefunden: {local_path}")
            status, payload = self.transport.upload(endpoint, params, local_path)
            source = local_path
        else:
            status, payload = self.transport.request(
                "POST", endpoint, params, {"file_url": remote_url})
            source = remote_url

        payload = _redact(payload, self.cfg.token) if isinstance(payload, dict) else payload
        if status >= 400 or (isinstance(payload, dict) and "error" in payload):
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            msg = err.get("message") or f"HTTP {status}"
            detail = " — ".join(x for x in (err.get("error_user_title"),
                                            err.get("error_user_msg")) if x)
            raise MetaAdsError(
                f"POST {self.cfg.act}/advideos ({source}): {msg} "
                f"(code={err.get('code')}, subcode={err.get('error_subcode')})"
                + (f" — {detail}" if detail else ""))
        video_id = payload.get("id") if isinstance(payload, dict) else ""
        if not video_id:
            raise MetaAdsError(f"POST {self.cfg.act}/advideos: keine video_id zurückgegeben")
        self._uploaded_video_id = str(video_id)
        return self._uploaded_video_id

    def ensure_video(self) -> str:
        """Video-ID aus Config/Upload; leer bedeutet bewusst Link-Ad."""
        if not self.cfg.has_video:
            return ""
        return self.upload_video()

    def upload_image(self, image_path: str = "") -> str:
        """Lädt ein Vorschaubild ins Werbekonto und liefert den `image_hash`."""
        if self._uploaded_image_hash:
            return self._uploaded_image_hash
        if not self.cfg.act:
            raise MetaAdsError("META_AD_ACCOUNT_ID fehlt: Bild kann nicht hochgeladen werden")
        local_path = os.path.expanduser(image_path or self.cfg.video_thumbnail_path)
        if not local_path or not os.path.isfile(local_path):
            raise MetaAdsError(f"META_VIDEO_THUMBNAIL_PATH nicht gefunden: {local_path}")

        endpoint = f"{GRAPH_HOST}/{self.cfg.version_tag}/{self.cfg.act}/adimages"
        status, payload = self.transport.upload(
            endpoint, {"access_token": self.cfg.token}, local_path)
        payload = _redact(payload, self.cfg.token) if isinstance(payload, dict) else payload
        if status >= 400 or (isinstance(payload, dict) and "error" in payload):
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            msg = err.get("message") or f"HTTP {status}"
            detail = " — ".join(x for x in (err.get("error_user_title"),
                                            err.get("error_user_msg")) if x)
            raise MetaAdsError(
                f"POST {self.cfg.act}/adimages ({local_path}): {msg} "
                f"(code={err.get('code')}, subcode={err.get('error_subcode')})"
                + (f" — {detail}" if detail else ""))
        images = payload.get("images") if isinstance(payload, dict) else {}
        image_hash = ""
        if isinstance(images, dict):
            for value in images.values():
                if isinstance(value, dict) and value.get("hash"):
                    image_hash = str(value["hash"])
                    break
        if not image_hash:
            raise MetaAdsError(f"POST {self.cfg.act}/adimages: kein image_hash zurückgegeben")
        self._uploaded_image_hash = image_hash
        return image_hash

    def ensure_thumbnail(self) -> str:
        """`image_hash` aus lokalem Thumbnail; URL-Pfad braucht keinen Upload."""
        if not self.cfg.video_thumbnail_path:
            return ""
        return self.upload_image()

    # ── Vorabprüfung ────────────────────────────────────────────────────────
    def preflight(self) -> dict[str, Any]:
        blockers: list[str] = []
        warnings: list[str] = []
        result: dict[str, Any] = {
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "graph_version": self.cfg.version_tag,
            "account": {}, "page": {}, "permissions": {},
            "blockers": blockers, "warnings": warnings, "ok": False,
        }

        missing = self.cfg.missing()
        for key in missing:
            blockers.append(f"{key} fehlt in .env-social")
        if missing:
            result["next_steps"] = [
                "Meta-App (Business) öffnen, Nutzer-Token mit ads_management erzeugen "
                "und in .env-social als META_ADS_ACCESS_TOKEN eintragen.",
                "Werbekonto-ID aus adsmanager.facebook.com (act_...) als "
                "META_AD_ACCOUNT_ID eintragen.",
                "Facebook-Seite als FACEBOOK_PAGE_ID eintragen (Anzeigengeber).",
            ]
            return result

        me = self.get("me", fields="id,name")
        perms = self.get("me/permissions").get("data", [])
        granted = {p.get("permission"): p.get("status") for p in perms}
        result["permissions"] = {"ads_management": granted.get("ads_management", "missing"),
                                 "ads_read": granted.get("ads_read", "missing"),
                                 "pages_read_engagement": granted.get(
                                     "pages_read_engagement", "missing")}
        if granted.get("ads_management") != "granted":
            blockers.append(
                "Permission ads_management nicht erteilt (Token ohne Werbezugriff)")

        fields = ("id,account_id,name,account_status,disable_reason,currency,"
                  "timezone_name,funding_source_details,amount_spent,spend_cap,"
                  "business,is_prepay_account")
        account = self.get(self.cfg.act, fields=fields)
        status_code = int(account.get("account_status") or 0)
        status_name = ACCOUNT_STATUS.get(status_code, str(status_code))
        result["account"] = {
            "id": account.get("id"), "name": account.get("name"),
            "status": status_name, "currency": account.get("currency"),
            "amount_spent_cents": account.get("amount_spent"),
            "spend_cap_cents": account.get("spend_cap"),
            "funding_source": bool(account.get("funding_source_details")),
            "disable_reason": account.get("disable_reason"),
        }
        if status_code in BLOCKING_STATUS:
            blockers.append(
                f"Werbekonto nicht auslieferungsfähig: {status_name} "
                f"(disable_reason={account.get('disable_reason')})")
        if not account.get("funding_source_details"):
            blockers.append(
                "Kein Zahlungsmittel im Werbekonto (Meta Ads Manager → "
                "Abrechnung → Zahlungsmethode hinzufügen)")
        if (account.get("currency") or "").upper() != self.cfg.currency:
            blockers.append(
                f"Kontowährung {account.get('currency')} != {self.cfg.currency}; "
                "Budget-Cap rechnet in EUR, Kampagne wird nicht angelegt")

        try:
            page = self.get(self.cfg.page_id, fields="id,name")
            result["page"] = {"id": page.get("id"), "name": page.get("name")}
            if not page.get("id"):
                blockers.append("Seite nicht lesbar (Page-Rolle prüfen)")
        except MetaAdsError as exc:
            result["page"] = {"error": str(exc)}
            blockers.append(f"Seite {self.cfg.page_id} nicht lesbar: {exc}")

        if not (self.cfg.dsa_beneficiary and self.cfg.dsa_payor):
            blockers.append(
                "META_DSA_BENEFICIARY/META_DSA_PAYOR fehlen (EU-Pflicht nach DSA "
                "für Anzeigen mit Zielgruppe DE/FR)")
        if result["permissions"].get("pages_read_engagement") != "granted":
            warnings.append(
                "pages_read_engagement nicht erteilt; Creative kann scheitern")

        result["video"] = {
            "configured": self.cfg.has_video,
            "video_id": self.cfg.video_id or None,
            "video_url": self.cfg.video_url or None,
            "video_path": self.cfg.video_path or None,
            "thumbnail_url": self.cfg.video_thumbnail_url or None,
            "thumbnail_path": self.cfg.video_thumbnail_path or None,
            "creative_type": "video" if self.cfg.has_video else "link",
        }
        if self.cfg.video_path:
            expanded = os.path.expanduser(self.cfg.video_path)
            if not os.path.isfile(expanded):
                blockers.append(f"META_VIDEO_PATH nicht gefunden: {expanded}")
        elif not self.cfg.has_video:
            warnings.append(
                "Kein Video konfiguriert (META_VIDEO_ID/URL/PATH): "
                "der Lauf legt eine Link-Anzeige statt einer Video-Anzeige an")
        if self.cfg.video_thumbnail_path:
            expanded_thumb = os.path.expanduser(self.cfg.video_thumbnail_path)
            if not os.path.isfile(expanded_thumb):
                blockers.append(
                    f"META_VIDEO_THUMBNAIL_PATH nicht gefunden: {expanded_thumb}")
        elif self.cfg.has_video and not self.cfg.video_thumbnail_url:
            blockers.append(
                "Video-Ad braucht ein Miniaturbild: META_VIDEO_THUMBNAIL_PATH "
                "oder META_VIDEO_THUMBNAIL_URL setzen")

        result["me"] = {"id": me.get("id"), "name": me.get("name")}
        result["ok"] = not blockers
        result["next_steps"] = [
            "Blocker beheben und `ads_agent.py --check-meta` erneut ausführen."
        ] if blockers else ["Preflight grün: `--live` legt Kampagnen PAUSED an."]
        return result

    # ── Anlegen (immer PAUSED) ──────────────────────────────────────────────
    def launch(self, campaign: dict[str, Any], day: str,
               language: str = "de") -> dict[str, Any]:
        """Legt Kampagne/AdSet/Creative/Ad PAUSED an. Kein ACTIVE-Pfad."""
        t = campaign["targeting"]
        name = f"KMHR-{campaign['campaign_key']}-{day}"
        budget_cents = cents(campaign["daily_budget_eur"])
        if budget_cents <= 0:
            raise MetaAdsError("Budget 0: keine Anlage")
        self._check_account_cap(budget_cents)
        # Vor der Kampagne hochladen: schlägt der Upload fehl, entsteht kein
        # verwaistes Kampagnen-/AdSet-Objekt.
        video_id = str(campaign.get("video_id") or self.ensure_video() or "")
        image_hash = ""
        if video_id:
            if not (self.cfg.video_thumbnail_url or self.cfg.video_thumbnail_path):
                raise MetaAdsError(
                    "Video-Ad braucht ein Miniaturbild: "
                    "META_VIDEO_THUMBNAIL_PATH oder META_VIDEO_THUMBNAIL_URL setzen")
            image_hash = self.ensure_thumbnail()

        created = self.post(
            f"{self.cfg.act}/campaigns",
            name=name,
            objective=OBJECTIVE,
            status="PAUSED",
            buying_type="AUCTION",
            special_ad_categories=["EMPLOYMENT"],
            # Länder, für die die Sonderkategorie gilt; muss die AdSet-Länder
            # enthalten, sonst blockiert Meta das AdSet (subcode 2909035).
            special_ad_category_country=list(t["countries"]),
            # Meta verlangt 2026 diesen Wert, wenn das Budget auf AdSet-Ebene
            # liegt (kein Kampagnenbudget). False = keine Budget-Sharing-Optik.
            is_adset_budget_sharing_enabled=False,
        )
        campaign_id = created.get("id")
        if not campaign_id:
            raise MetaAdsError("Kampagne ohne ID zurückgegeben")

        adset = self.post(
            f"{self.cfg.act}/adsets",
            name=f"{name}-adset",
            campaign_id=campaign_id,
            daily_budget=budget_cents,
            billing_event=BILLING_EVENT,
            optimization_goal=OPTIMIZATION_GOAL,
            bid_strategy=BID_STRATEGY,
            destination_type="WEBSITE",
            status="PAUSED",
            targeting={
                "geo_locations": {"countries": t["countries"]},
                "age_min": int(t["age_min"]),
                "age_max": int(t["age_max"]),
                # Kein genders-Feld = alle Geschlechter (Beschäftigungsregel).
                "targeting_automation": {"advantage_audience": 0},
            },
        )
        adset_id = adset.get("id")
        if not adset_id:
            raise MetaAdsError("Ad Set ohne ID zurückgegeben")

        creative_body = campaign["creative"]
        link = campaign["link"]
        cta = {"type": "LEARN_MORE", "value": {"link": link}}
        if video_id:
            video_data: dict[str, Any] = {
                "video_id": video_id,
                "message": creative_body,
                "link_description": campaign.get("link_description")
                or link.replace("https://", "").replace("http://", "").rstrip("/"),
                "call_to_action": cta,
            }
            if image_hash:
                video_data["image_hash"] = image_hash
            elif self.cfg.video_thumbnail_url:
                video_data["image_url"] = self.cfg.video_thumbnail_url
            story_spec: dict[str, Any] = {
                "page_id": self.cfg.page_id,
                "video_data": video_data,
            }
            creative_type = "video"
        else:
            story_spec = {
                "page_id": self.cfg.page_id,
                "link_data": {
                    "message": creative_body,
                    "link": link,
                    "name": campaign["headline"],
                    "call_to_action": cta,
                },
            }
            creative_type = "link"
        creative = self.post(
            f"{self.cfg.act}/adcreatives",
            name=f"{name}-creative-{language}-{creative_type}",
            object_story_spec=story_spec,
        )
        creative_id = creative.get("id")
        if not creative_id:
            raise MetaAdsError("Creative ohne ID zurückgegeben")

        ad = self.post(
            f"{self.cfg.act}/ads",
            name=f"{name}-ad-{language}",
            adset_id=adset_id,
            creative={"creative_id": creative_id},
            status="PAUSED",
            dsa_beneficiary=self.cfg.dsa_beneficiary,
            dsa_payor=self.cfg.dsa_payor,
        )
        ad_id = ad.get("id")
        if not ad_id:
            raise MetaAdsError("Ad ohne ID zurückgegeben")

        return {"status": "paused_created", "campaign_id": campaign_id,
                "adset_id": adset_id, "creative_id": creative_id, "ad_id": ad_id,
                "daily_budget_eur": campaign["daily_budget_eur"],
                "special_ad_categories": ["EMPLOYMENT"], "language": language,
                "creative_type": creative_type, "video_id": video_id or None}

    def _check_account_cap(self, planned_cents: int) -> None:
        account = self.get(self.cfg.act, fields="amount_spent,spend_cap,currency")
        currency = (account.get("currency") or "").upper()
        if currency and currency != self.cfg.currency:
            raise MetaAdsError(
                f"Kontowährung {currency} != {self.cfg.currency}: Anlage verweigert")
        spend_cap = int(account.get("spend_cap") or 0)
        spent = int(account.get("amount_spent") or 0)
        if spend_cap > 0 and spend_cap - spent < planned_cents:
            raise MetaAdsError(
                "Konto-Spend-Cap reicht nicht: "
                f"verbleibend {max(0, spend_cap - spent)} Cent < "
                f"geplant {planned_cents} Cent")

    # ── Aktivieren (separater, bestätigter Schritt) ─────────────────────────
    def activate(self, ids: dict[str, str], confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise MetaAdsError(
                "Aktivierung nur mit ausdrücklicher Bestätigung (--yes). "
                "Der Agent schaltet keine Anzeige selbst scharf.")
        out: dict[str, Any] = {}
        for key in ("campaign_id", "adset_id", "ad_id"):
            obj_id = ids.get(key)
            if not obj_id:
                raise MetaAdsError(f"{key} fehlt in den gespeicherten IDs")
            self._call("POST", obj_id, data={"status": "ACTIVE"})
            out[key] = "ACTIVE"
        out["status"] = "active"
        return out

    def pause(self, ids: dict[str, str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("campaign_id", "adset_id", "ad_id"):
            obj_id = ids.get(key)
            if obj_id:
                self._call("POST", obj_id, data={"status": "PAUSED"})
                out[key] = "PAUSED"
        return out

    def insights(self, campaign_id: str, since: str, until: str) -> dict[str, Any]:
        """Nur Aggregate: Ausgaben, Impressionen, Klicks. Keine Personen."""
        return self.get(
            f"{campaign_id}/insights",
            fields="spend,impressions,clicks,ctr,cpc,cpm",
            time_range=json.dumps({"since": since, "until": until}),
        )
