# ENTSCHEIDUNG — Autonome Social-Media-Komponente

**Stand:** 25.10.2026 · **Projekt:** KM-HR-Agent / `https://jobs.hanibal-ai.com` · **Umsetzung:** `scripts/social_agent.py`

## Zielgruppe und Kanalwahl

- **B2B (Arbeitgeber DE/FR/CH):** LinkedIn ist der einzige Kanal mit professioneller Reichweite in allen drei Märkten. September-2026-Adressable-Audiences: DE 27,1 Mio., FR 40,1 Mio. (38,0 Mio. Mitglieder), CH 5,76 Mio. Quellen: <https://napoleoncat.com/stats/linkedin-users-in-germany/> · <https://napoleoncat.com/stats/linkedin-users-in-france/> · <https://napoleoncat.com/stats/linkedin-users-in-switzerland/>
- **Kandidaten Nordafrika:** Facebook ist der Reichweitenführer (StatCounter September 2026: Marokko 49,9 %, Ägypten 62,4 % Social-Traffic). Adressable Audiences: Marokko 29,6 Mio., Algerien 32,9 Mio. Quellen: <https://gs.statcounter.com/social-media-stats/all/morocco> · <https://napoleoncat.com/stats/facebook-users-in-morocco/> · <https://napoleoncat.com/stats/social-media-users-in-algeria/>
- **Arbeitgebermarke/visuelle Reichweite:** Instagram ist im Maghreb relevant (Marokko 17,0 Mio., Tunesien 4,54 Mio., Ägypten 23,9 Mio.; September 2026) und teilt sich bei Meta App, Token und Review mit Facebook. Quellen: <https://napoleoncat.com/stats/instagram-users-in-morocco/> · <https://napoleoncat.com/stats/instagram-users-in-tunisia/> · <https://napoleoncat.com/stats/instagram-users-in-egypt/>

**Entscheidung:** Phase 1 = **LinkedIn + Facebook + Instagram**. X wird wegen Link-Pricing ($0,20 pro Post mit URL) und TikTok wegen des separaten Content-Posting-Audits (unaudited nur `SELF_ONLY`) zurückgestellt. Quellen: <https://docs.x.com/x-api/getting-started/pricing> · <https://developers.tiktok.com/doc/content-posting-api-reference-direct-post>

## Formate und Kadenz

| Plattform | Formate | Kadenz |
|---|---|---|
| LinkedIn | Text + Link, Single Image 1200×627, PDF-Dokument als Carousel-Ersatz (organische Carousels sind sponsored-only) | 3×/Woche |
| Facebook | Text + Link, Single Image, 2–10-Bild-Carousel, natives Video | 3×/Woche |
| Instagram | 4:5 Single Image 1080×1350, Carousel, Reels 9:16; **keine klickbaren Caption-Links** → Link-in-Bio | 2×/Woche |

LinkedIn-Organikformate: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api> · Instagram-Publishing: <https://developers.facebook.com/docs/instagram-platform/content-publishing> · Facebook Pages API: <https://developers.facebook.com/docs/pages-api>

**Redaktionsplan:** 7 Tage, ein Post/Tag, Rotation `new_jobs` → `candidate_tips` → `hiring_stats`. Jeder Post ist datengetrieben aus der HR-DB (aktive Stellen, aggregierte Bewerbungs-/Einstellungszahlen) und enthält einen KI-Hinweis.

## Architektur

```
Wahrnehmen             Planen                  Handeln                 Beobachten
DB-Aggregate     →   7-Tage-Plan      →   LinkedIn/Facebook/IG   →   Outbox + Log
(PII-frei)           (Plattform/Thema)     (Dry-Run oder live)       ergebnisse/social/<Tag>/
```

- **Default ist Dry-Run.** Der exakte API-Payload wird als JSON in die Outbox geschrieben; es wird kein Socket geöffnet.
- **Live** nur mit `KMHR_SOCIAL_MODE=live` **und** `KMHR_SOCIAL_AUTO_PUBLISH=1` und den jeweiligen Tokens. Fehlt eines, bleibt der Lauf Dry-Run bzw. wird ehrlich als `failed` persistiert.
- **Idempotenz:** Post-ID = SHA-256 aus Tag/Plattform/Thema/Text; existiert die Outbox-Datei, wird der Lauf übersprungen (`--force` überschreibt).
- **Ausführung:** `scripts/social_agent.py --once` (CLI) oder `kmhr-social.timer` (täglich 07:15). Der Timer postet nicht selbst, er startet denselben Agenten.
- **Kein neuer DB-Table:** Die Outbox ist dateibasiert unter `ergebnisse/social/<YYYY-MM-DD>/`; damit bleiben Schema-Gates und Seed unberührt.

## DSGVO und Plattformregeln

- **Keine personenbezogenen Daten** in Posts: keine Namen, E-Mails, Telefonnummern, CVs, Bewerbungstexte, Kandidaten-IDs. Der Guard `assert_no_pii` blockt E-Mail-, Telefon- und `Kandidat #N`-Muster.
- **Erfolgsgeschichten** nur mit dokumentierter Einwilligung (Art. 6 Abs. 1 lit. a DSGVO; §22 KUG für Porträts in DE; Frankreich: droit à l'image). Der MVP postet **keine** Personenstorys, nur Rollen/Städte/Aggregate.
- **Widerruf:** Takedown innerhalb von 7 Tagen; Einwilligungsnachweis (Person, Asset-Hash, Kanäle, Zweck, Datum, Widerruf) separat.
- **Retention:** Post-Assets nach Kampagnenende + 90 Tage löschen; keine Social-Analytics mit Kandidaten-Datensätzen verknüpfen.
- **Plattform-AGB:** keine Scraping-/Automatisierungs-Tricks; nur offizielle APIs. Facebook-Gruppen sind nicht automatisierbar (`publish_to_groups` seit 22.04.2024 entfernt): <https://developers.facebook.com/docs/graph-api/changelog/version19.0/>

## Umsetzungsstand 25.10.2026

- Facebook-App-ID/App-Secret wurden gegen `GET /{app-id}` validiert (HTTP 200,
  App-ID bestätigt; `debug_token`: `type=APP`, `user_id=null`, `scopes=[]`).
  Der App Access Token (`app_id|app_secret`) ist **kein** Page-Token; `/me`
  und `/me/accounts` liefern `OAuthException 2500`. Für Posts ist der
  User-/Page-OAuth-Flow zwingend; der Agent lehnt App-Tokens jetzt mit
  Klartext ab.
- LinkedIn-Client-ID ist gesetzt. Für den Token-Tausch fehlen noch
  **Client Secret + registrierte Redirect-URI**; der OAuth-Helfer
  `scripts/social_oauth.py` erzeugt Auth-URL und schreibt Tokens nur nach
  `.env-social` (chmod 600, gitignored).
- Bis Tokens vorliegen, bleibt `KMHR_SOCIAL_MODE=dry_run`; die Outbox beweist
  Payload und Redaktionsplan ohne Netzwerkaufruf.
- Der OAuth-Helfer öffnet **keinen** Browser mehr automatisch (WSL/Headless:
  DBus/GCM/WebGL-Fehler), bindet den lokalen Server an die exakte
  `*_REDIRECT_URI` und gibt den Port nach Timeout/Ctrl+C frei. Eine
  LinkedIn-Meldung „redirect_uri does not match the registered value" bedeutet
  immer: URI in der LinkedIn-App exakt gleich eintragen (Schema/Host/Port/Pfad).
- **LinkedIn-Autor-URN:** `w_member_social` allein reicht für den Token, aber
  `/v2/userinfo` braucht zusätzlich `openid profile`. Ohne diese Scopes fehlt
  `LINKEDIN_AUTHOR_URN`; ein Live-Post ist dann nicht möglich. Produkt
  „Sign In with LinkedIn using OpenID Connect“ aktivieren.
- **Localhost ist für LinkedIn nicht zulässig:** Die offizielle Doku verlangt
  eine HTTPS-Redirect-URI. Deshalb ist der verbindliche Callback
  `https://jobs.hanibal-ai.com/oauth/callback`; Caddy leitet ihn an den
  lokalen Helper auf dem VPS (`127.0.0.1:8765`) weiter. Meta blockiert
  Localhost ebenfalls im Live-Modus. Quelle:
  <https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow>

## Risiken / offene Punkte

- **LinkedIn Community Management API** (Organisations-Posting) braucht App-Review, Rechtsentity, Business-E-Mail und Datenschutzseite; Member-Posting (`w_member_social`) ist self-serve. Bis zum Review läuft LinkedIn im Dry-Run oder als Member-Post.
- **Meta App Review** (`pages_manage_posts`, `instagram_content_publish`) kann Wochen dauern; Instagram braucht zusätzlich ein öffentlich erreichbares `INSTAGRAM_IMAGE_URL`.
- **Token-Laufzeit** (Meta ~60 Tage) braucht Refresh/Alert; ein abgelaufener Token wird als `failed` persistiert, nicht stillschweigend ignoriert.
- **Keine echten Tokens im Repo.** `.env-social` ist gitignored; Vorlage `.env-social.example`.

## Quellen (Auswahl)

- LinkedIn Posts API: <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api>
- LinkedIn Rate Limits: <https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits>
- Meta Graph API Rate Limits: <https://developers.facebook.com/docs/graph-api/overview/rate-limiting/>
- DSGVO: <https://eur-lex.europa.eu/eli/reg/2016/679/oj> · §22 KUG: <https://www.gesetze-im-internet.de/kukg/__22.html>
- CNIL-Recruiting-Leitfaden: <https://www.cnil.fr/sites/default/files/atoms/files/guide_referentiel_-_recrutement.pdf>
