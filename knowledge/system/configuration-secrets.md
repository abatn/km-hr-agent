# Konfiguration: Geheimnisse aus der Umgebung

**Stand: 30.09.2026 (P1-10 „Defaults + Warnung“ + R3-4 Fail-closed-Gate + R6-2.2 `.env` statt KMHR_DEV-Default, sicherheitsrelevant, Nutzer-GO)**

Diese Datei ist die MD-Wahrheit für die Laufzeit-Konfiguration des NiceGUI-Frontends
(`webui/`). Code: `webui/main.py` (STORAGE_SECRET + R3-4-Gate), `webui/pages/login.py`
(Admin-Seed), `start-webui.sh` (liest `.env`, R6-2.2).

---

## (a) Variable je Geheimnis

| Variable | Zweck | Default wenn nicht gesetzt | Fundstelle |
|---|---|---|---|
| `KMHR_STORAGE_SECRET` | Signiert die NiceGUI-Session-/Browser-Storage-Cookies (`storage_secret=`) | `km-hr-agent-phase0-secret` (**Entwicklung**, unsicher) | `webui/main.py` (gemessen 10.10.2026) |
| `KMHR_ADMIN_SEED_EMAIL` | E-Mail des Admin-Seed-Kontos | `admin@km-hr-agent.local` | `webui/pages/login.py` (gemessen 10.10.2026) |
| `KMHR_ADMIN_SEED_PASSWORD` | Passwort des Admin-Seed-Kontos — seit R3-4 **Pflicht** (ohne `KMHR_DEV`) | `admin-agent-2026` (**Entwicklung**, unsicher, nur noch unter `KMHR_DEV`) | `webui/pages/login.py` (gemessen 10.10.2026) |
| `KMHR_DEV` | Schalter: hebt das Fail-closed-Gate für beide Pflicht-Variablen auf | nicht gesetzt → **Gate aktiv** | `webui/main.py` (Codemarke `KMHR_DEV`, gemessen 10.10.2026) |

**R3-4 (30.09.2026): fail closed.** Ohne `KMHR_DEV` startet die App nur, wenn
`KMHR_STORAGE_SECRET` **und** `KMHR_ADMIN_SEED_PASSWORD` gesetzt und nicht-leer sind.
Fehlt eine Variable, schreibt der Start eine **ABBRUCH-Meldung nach stderr** (mit den
fehlenden Namen) und beendet sich mit `SystemExit(1)` — und zwar **vor**
`logic.app_bootstrap()` (`webui/main.py` (gemessen 10.10.2026), erster DB-Zugriff) und **vor** `ui.run()`
(`webui/main.py` (gemessen 10.10.2026)). Details: Abschnitt (e).

Die **P1-10-Default-Warnung bleibt unverändert** (`webui/main.py` (gemessen 10.10.2026)). Sie steht
textlich VOR dem Gate und wird deshalb auch in einem Abbruchlauf noch ausgegeben;
inhaltlich gilt sie nur noch für `KMHR_DEV`-Läufe, denn ohne `KMHR_DEV` wird nie mit
dem Default gestartet.

> **Design-Entscheidung (keine externe Quelle):** Variablennamen, Default-Werte, der
> Schaltername `KMHR_DEV` samt Werten `1/true/yes`, „fail closed“ als Grundverhalten
> und die Starter-Voreinstellung sind frei gewählt. **Quelle des Verhaltens: Nutzer-GO
> R3-4 (30.09.2026).** Bewusste Abwägung: ein stiller Default wäre ein
> Sicherheitsrisiko; deshalb sind die Defaults nur noch über den expliziten
> Entwicklungs-Override erreichbar und werden dann weiterhin laut gewarnt.

---

## (b) Betrieb (Produktion)

```bash
export KMHR_STORAGE_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
export KMHR_ADMIN_SEED_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
export KMHR_ADMIN_SEED_EMAIL="admin@firma.example"
```

Regeln:
1. `KMHR_STORAGE_SECRET` **darf nie** zwischen Instanzen geteilt und nie rotiert werden,
   solange Sessions gültig bleiben sollen (ein Wechsel invalidiert alle Browser-Sessions).
2. Das Admin-Seed-Konto wird nur angelegt, wenn `admins` leer ist. Ist bereits ein Admin
   vorhanden, greift die Variable **nicht** mehr – dann zählt das bestehende Passwort.
3. Das Seed-Passwort wird **nur** gehasht gespeichert (`hash_password_argon2id`), nie im
   Klartext. Die Variable selbst ist trotzdem geheim zu halten.

---

## (c) Warum das geändert wurde (Altstand, 30.09.2026)

Beide Geheimnisse standen als Klartext-Literal im Quellcode:

- `webui/main.py`: `STORAGE_SECRET = "km-hr-agent-phase0-secret"`
- `webui/pages/login.py`: `hash_password_argon2id("admin-agent-2026")`

Damit war das Admin-Passwort vorhersagbar und das Session-Geheimnis bekannt. Nachweis und
Test: `ergebnisse/entscheidungen.md` (Runde 2, Eintrag „P1-10“) sowie
`tests/test_secrets_from_env.py` (prüft beide Richtungen: mit und ohne gesetzte Variable,
inkl. echtem Sub-Prozess-Start).

---

## (d) Test

```bash
.venv-streamlit/bin/python3 -m pytest -q tests/test_secrets_from_env.py   # -> R3-4: 11 passed
```

Ohne pytest kann man das Verhalten direkt beobachten (Venv-Python, weil `nicegui`
nur dort installiert ist):

```bash
# (a) ohne Env, ohne KMHR_DEV -> ABBRUCH, rc=1, kein Server
.venv-streamlit/bin/python3 -m webui.main ; echo rc=$?
# (b) Dev-Override -> startet, Default-Warnung sichtbar
KMHR_PORT=8097 KMHR_DB_PATH=/tmp/... KMHR_RUNNER_AUTOSTART=0 timeout 8 .venv-streamlit/bin/python3 -m webui.main
# (c) mit beiden Secrets -> startet, KEINE Default-Warnung
KMHR_PORT=8098 KMHR_DB_PATH=/tmp/... KMHR_RUNNER_AUTOSTART=0 \
  KMHR_STORAGE_SECRET=x KMHR_ADMIN_SEED_PASSWORD=y timeout 8 .venv-streamlit/bin/python3 -m webui.main
```

---

## (e) `KMHR_DEV` – Fail-closed-Gate (R3-4, 30.09.2026)

**Quelle: Nutzer-GO R3-4 (30.09.2026) „A: Fail-closed, KMHR_DEV=1-Override“.**

Gate in `webui/main.py` (gemessen 10.10.2026) (Kurzform):

```python
KMHR_DEV = os.environ.get("KMHR_DEV", "").strip().lower() in ("1", "true", "yes")
_missing = [k for k in ("KMHR_STORAGE_SECRET", "KMHR_ADMIN_SEED_PASSWORD")
            if not os.environ.get(k, "").strip()]
if _missing and not KMHR_DEV:
    print("[webui] ABBRUCH: fehlende Umgebungsvariable(n): ...", file=sys.stderr)
    raise SystemExit(1)
```

| Fall | Env | Ergebnis |
|---|---|---|
| (a) | eine/beide Pflicht-Variablen fehlen, kein `KMHR_DEV` | stderr `ABBRUCH` mit den fehlenden Namen, `SystemExit(1)`, **keine DB, kein Server** |
| (b) | `KMHR_DEV=1`, keine Secrets | Start erlaubt, Default-Warnung (P1-10) auf stderr |
| (c) | beide Secrets gesetzt (kein `KMHR_DEV` nötig) | Start erlaubt, **keine** Default-Warnung |

Verhaltensregeln:
1. **Reihenfolge:** Gate nach dem STORAGE_SECRET-Block (`webui/main.py` (Codemarke `STORAGE_SECRET`, gemessen 10.10.2026)), vor
   `logic.app_bootstrap()`  und vor `ui.run()`  — es feuert damit bei
   jedem Ausführen/Import der Datei. Reihenfolge-Nachweis im Test:
   `test_gate_liegt_vor_app_bootstrap_und_ui_run`.
2. **Leer-String zählt als fehlend** (`.strip()`); `KMHR_DEV` akzeptiert
   `1/true/yes` (case-insensitiv).
3. **Starter (geändert R6-2.2, 30.09.2026):** `start-webui.sh` setzt `KMHR_DEV` NICHT mehr
   automatisch (früher `KMHR_DEV="${KMHR_DEV:-1}"` → die Live-App lief mit dem bekannten
   Default-Secret). Siehe Abschnitt (f). Jeder direkte Aufruf `python3 -m webui.main`
   bekommt weiterhin das Gate.
4. **Betrieb (Abschnitt (b)):** beide Secrets exportieren und `KMHR_DEV` NICHT setzen.
5. **Tests/E2E:** `tests/test_secrets_from_env.py` prüft (a)-(c) als echte
   Sub-Prozess-Starts gegen isolierte Port-/DB-Pfade; `tests/e2e_isolation.py` trägt
   `KMHR_DEV=1` in die Env seiner isolierten Instanz (Server + Skripte).

> **Design-Entscheidung (keine externe Quelle):** Umgebungsvariablen-Name `KMHR_DEV`,
> die akzeptierten Werte `1/true/yes`, die Tatsache, dass der Override BEIDE
> Pflicht-Variablen betrifft (nicht nur `KMHR_STORAGE_SECRET`), und die Voreinstellung
> `KMHR_DEV=1` im Dev-Starter sind frei gewählt. **Quelle des Verhaltens: Nutzer-GO
> R3-4 (30.09.2026)** — keine Norm, kein Gesetz.


---

## (f) `.env`-Datei und Starter (R6-2.2, 30.09.2026)

**Quelle: Nutzer-GO R6-2.2 „Ja: .env statt KMHR_DEV-Default“ (30.09.2026).** Die Punkte
R6-2.1 (Admin-Passwort rotieren) und R6-2.3 (erzwungener Passwortwechsel) hat der Nutzer
**abgelehnt** — sie sind NICHT umgesetzt (siehe „Bekanntes Restrisiko“).

- `start-webui.sh` lädt `./.env` (Pfad per `KMHR_ENV_FILE` übersteuerbar, z. B. für Tests)
  mit `set -a`, danach gilt: fehlen `KMHR_STORAGE_SECRET` oder `KMHR_ADMIN_SEED_PASSWORD`
  und ist `KMHR_DEV` nicht ausdrücklich `1/true/yes`, bricht der **Starter selbst** mit
  rc=1 ab (Meldung nennt die fehlenden Namen). `webui/main.py` bricht zusätzlich ab (R3-4).
- Entwicklung ohne Secrets: bewusst `KMHR_DEV=1 ./start-webui.sh` (Warnung bleibt sichtbar).
- `.env` ist in `.gitignore` (`.env*`, Ausnahme `!.env.example`), Modus `600`.
  Vorlage ohne Werte: `.env.example`. Werte erzeugen:
  `python3 -c 'import secrets;print(secrets.token_urlsafe(48))'`.
- Die am 30.09.2026 angelegte `.env` enthält zufällig erzeugte Werte (nicht im Protokoll).
  **Folge:** Das neue `KMHR_STORAGE_SECRET` invalidiert beim nächsten Start alle
  bestehenden Browser-Sessions (einmaliges erneutes Einloggen).
- `KMHR_ADMIN_SEED_PASSWORD` wirkt nur, wenn `admins` leer ist (Regel (b)2). Ein bereits
  vorhandener Admin behält sein Passwort.
- Tests: `tests/test_secrets_from_env.py` (Starter: Abbruch ohne `.env`, Dev-Override,
  `.env` wird gelesen und es erscheint keine Default-Warnung, `.gitignore`/Vorlage).

### Bekanntes Restrisiko (dokumentiert, nicht behoben — Nutzerentscheidung)
Das Live-Admin-Konto (`admin@km-hr-agent.local`) trägt weiterhin das **früher im Quelltext
stehende Seed-Passwort** (am 30.09.2026 per argon2-Verify gegen den Live-Hash bestätigt).
Der Klartext wird hier bewusst nicht wiederholt. Wer die Git-/Dateihistorie oder ältere
Doku kennt, kann sich als Admin anmelden. Maßnahme (Rotation oder erzwungener Wechsel) ist
auf Nutzerwunsch **offen**; bis dahin darf die App nicht aus dem lokalen Netz erreichbar
sein.

> **Design-Entscheidung (keine externe Quelle):** Dateiname `.env`, Variable
> `KMHR_ENV_FILE`, Verhalten des Starters und die Modus-Empfehlung `600` sind frei gewählt.
