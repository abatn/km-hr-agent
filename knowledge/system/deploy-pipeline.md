# Deploy-Pipeline: GitHub → Contabo VPS (SSH-Variante)

> **Stand:** 06.10.2026 · **Status:** implementiert (Workflow `.github/workflows/deploy-contabo.yml`)
> **OFFENE STÖRUNG (20.10.2026):** Der alte Contabo-VPS `169.58.83.32` ist **nicht
> erreichbar** (Host komplett down) ⇒ Deploy unmöglich. Messwerte + Handlungsoptionen:
> Abschnitt **„Störung 20.10.2026 — Contabo-VPS nicht erreichbar"** (unten).
> **UMZUG (20.10.2026):** Neuer Host = **`176.57.189.201`** (`vmi3680465`, Ubuntu
> 24.04.5) — Ist-Befund, Installationsschritte und Sicherheitsregel: Abschnitt
> **„Serverumzug 20.10.2026 → neuer Host `176.57.189.201`"** (unten). Letzter
> **bekannter** Code-Stand auf dem alten Host: `f984168` (18.10.2026); `195fc69`
> (20.10.2026) war **nicht** deployed.
> **Ablauf:** lokal `git push` → GitHub CI grün → Deploy-Workflow (SSH) → Contabo `git reset --hard` → App-Neustart
> **Quellen (GitHub-Doku, Abruf 06.10.2026):**
> - Continuous deployment: Workflow läuft bei Push auf den Default-Branch
>   (`docs.github.com/en/actions/get-started/continuous-deployment`)
> - Event `workflow_run` (Deploy erst nach erfolgreichem CI) + `conclusion == 'success'`
>   (`docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows`)
> - Secrets in Workflows (`secrets.<NAME>`) (`docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions`)
> - REST Deploy-Keys: `POST /repos/{owner}/{repo}/keys` mit `read_only`
>   (`docs.github.com/en/rest/repos/keys`)
> **Design-Entscheidungen (ohne externe Quelle, als solche gekennzeichnet):**
> - Key-Typ ed25519, 2 Zwecke ein Paar (inbound SSH + outbound git pull)
> - Health-Wartezeit 60 s (12 × 5 s), Concurrency-Gruppe `deploy-contabo`, `git clean -fd` vor Restart
> - Server-Pfad `/opt/km-hr-agent`, Service `kmhr-deploy` (Name: `kmhr-agent.service`), Port 8080

## Auth (2 Schlüssel-Pfade, ein Key-Paar)

| Zweck | Artefakt | Ort |
|---|---|---|
| Server **liest** Code | Public-Key `kmhr-deploy.pub` als **read-only Deploy-Key** | GitHub-Repo (`gh api repos/abatn/km-hr-agent/keys`, `read_only=true`) |
| GitHub **betritt** Server | Private-Key `kmhr-deploy` als Secret **`CONTABO_SSH_KEY`** | GitHub Secrets (Repo-Ebene) |
| Server-Push-Zugang | gleicher Private-Key + `authorized_keys` | Contabo `~/.ssh/` |

- Server-Remote: `git@github.com:abatn/km-hr-agent.git` mit
  `core.sshCommand = "ssh -i /root/.ssh/kmhr-deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"`.
- **Nicht** angefasst: existierender Root-Key `ssh-key-2026-03-29.key` (Beweis: `git status` unverändert, `authorized_keys` nur +1 Zeile).

## Workflow `deploy-contabo.yml`

1. Trigger: `workflow_run` → `workflows: [CI]`, `branches: [main]`, `types: [completed]`.
2. Gate: `if: github.event.workflow_run.conclusion == 'success'` — **Deploy nur nach grünem CI**.
3. Secret nach `~/.ssh/id_contabo` (600) + `ssh-keyscan $DEPLOY_HOST` (Workflow-Env `DEPLOY_HOST`, 20.10.2026 auf den neuen Host umgestellt).
4. SSH nach Contabo: `git fetch origin main` → `git reset --hard $TARGET_SHA` (`workflow_run.head_sha`)
   → `git clean -fd` → `pip install -r requirements.txt` **nur bei Änderung** →
   `systemctl restart km-hr-agent` → Health-Loop `curl 127.0.0.1:8080` (max 60 s).
5. Abschluss: `git rev-parse HEAD` (Server) **muss** `== TARGET_SHA` sein, sonst Fehler.

## Sync-Garantie (Was = synchron?)

- **Synchron** = Tracked-Dateien (`git reset --hard` + `git clean -fd`).
- **Nie** von Deploy berührt (gitignored): `.env*`, `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`,
  `__pycache__/` — Beweis `.gitignore` (`.env*`, `.venv-*/`, `data/`, `testdaten/`, `ergebnisse/`).
- Lokal einmalig: `git config remote.origin.push master:main` → plain `git push` landet auf `main`.

## Rollback

- Workflow-Input/Dispatch auf gewünschte SHA: `git fetch && git reset --hard <SHA>` per SSH
  (gleiche Befehle wie Deploy) — **kein** separater Mechanismus nötig.
- DB-Backups liegen **nicht** im Deploy-Pfad (nur Code-Sync); Datenänderungen bleiben separat.

## Sicherheit

- Privatschlüssel verlässt Contabo nur per Pipe in `gh secret set` (nie in Chat/Repo/Datei).
- Repo ist **privat** (Voraussetzung für saubere Deploy-Key-Nutzung; siehe GitHub-Doku zu
  Deploy-Keys/Forks — Public-Repos: Fork-PRs könnten Keys auslesen).
- Rotation: bei Leak → Key auf Contabo neu erzeugen → Deploy-Key löschen/neu setzen → Secret neu setzen.

## Störung 20.10.2026 — Contabo-VPS nicht erreichbar

**Status: offen (Stand 20.10.2026, 12:15:51Z gemessen).** Der Server `169.58.83.32` ist
**komplett unerreichbar** — nicht nur SSH, sondern auch der App-Port und ICMP:

| Prüfung | Ergebnis (20.10.2026 12:15:51Z) |
|---|---|
| `curl http://169.58.83.32:8080/` | **keine Antwort** (Timeout nach 15 s) |
| TCP **22** (SSH) | Timeout / verweigert |
| TCP **8080** (App) | Timeout / verweigert |
| `ping` | 2 Pakete, 0 empfangen, **100 % Paketverlust** |
| `ssh-keyscan -H 169.58.83.32` | rc=1, **0 Zeilen** |

**Gegenprobe (19.10.2026):** Zugriff auf `169.58.83.32:8080` (HTTP 200) und
`ssh root@169.58.83.32` waren **an diesem Tag erfolgreich** ⇒ **Ausfall zwischen 19.10.
und 20.10.2026**, nicht Dauerzustand.

**Auswirkung auf die Pipeline (gemessen, keine Vermutung):**
- GitHub-CI des Commits `195fc69` ist **grün** (5 Workflows: CI, Docs & Schema,
  Docs-Drift, Security, i18n — alle `success`; der Billing-Block vom 16.–20.10.2026 war
  die Ursache der früheren 4-Sekunden-Fehlschläge und ist **behoben**).
- Der Deploy-Workflow **`Deploy Contabo` #39420241461** startete (Gate `conclusion ==
  'success'` erfüllt) und scheiterte in **Schritt 3 „SSH-Key + known_hosts"** an
  `ssh-keyscan` (exit 1) ⇒ **nicht** am Code, **nicht** an Keys: der Host ist nicht
  erreichbar. Schritte 4/5 (Reset auf SHA + Restart, SHA-Abgleich) wurden **skipped**.
- **Serverseitiger Code-Stand bleibt `f984168` (18.10.2026, 14:07)** — alle Änderungen
  ab `6a25ff2` (FR-Filter, MVP-Board, Visum-nach-Einstellen, Onboarding-DB-Quelle,
  Sidebar 5→7) sind **nicht** live. Lokal läuft der Stand `195fc69` (App + Runner aktiv).

**Handlungsoptionen (keine automatisch ausgeführt — Provider-/Server-Zugriff nötig):**
1. **Contabo-Panel prüfen** (Powercycle/Neustart des VPS, Netzwerk/Status, ggf. Zahlung/
   Suspendierung des Accounts) — **Root Cause liegt außerhalb des Repos**.
2. Danach **Deploy nachholen**: `gh run rerun 39420241461` (Deploy-Workflow) — Ziel-SHA
   kommt aus `workflow_run.head_sha`; oder manuell per SSH (gleiche Befehle wie der
   Workflow, siehe „Rollback"): `git fetch origin main && git reset --hard 195fc69 &&
   git clean -fd && systemctl restart km-hr-agent` + Health-Check `curl 127.0.0.1:8080`.
3. **Diagnose am Host** (sobald erreichbar): `journalctl -u km-hr-agent`, `ss -ltnp | grep 8080`,
   `dmesg | tail`, `uptime` — Ziel: warum SSH **und** App-Port und ICMP ausfallen
   (Reboot/Hänger, Firewall, Provider-Netz).

**Kein Code-/Doku-Fix erforderlich:** Die Pipeline selbst ist unverändert und war bis
zum Ausfall 2× grün durchgelaufen (`f984168`, 18.10.2026).

## Serverumzug 20.10.2026 → neuer Host `176.57.189.201`

**Anlass:** Der alte Host `169.58.83.32` ist seit 20.10.2026 **nicht erreichbar**
(Messwerte siehe Störungsabschnitt oben) und damit als Deploy-Ziel verloren. Der
**neue Contabo-VPS** `176.57.189.201` (`vmi3680465`) ersetzt ihn.

**Ist-Befund neuer Host (gemessen 20.10.2026, 14:23–14:34Z, read-only):**

| Merkmal | Wert |
|---|---|
| OS / Kernel | Ubuntu 24.04.5 LTS, 6.8.0-139-generic |
| CPU / RAM / Disk | 8 GB RAM (468 MB belegt), 96 GB (`/dev/sda1`, 2,3 GB belegt, 94 GB frei) |
| Offene Ports (vor Setup) | nur **22** (sshd) — kein 80/443/8080, **keine App** |
| `/opt/km-hr-agent` | **nicht vorhanden** (vor Setup) |
| `km-hr-agent.service` | **nicht vorhanden** / `inactive` (vor Setup) |
| `/root/.ssh/authorized_keys` | **0 Zeilen** (vor Setup) |
| `ufw` | **inactive** ⇒ App auf `0.0.0.0:8080` wäre **öffentlich** |
| Werkzeuge | Python **3.12.3**, git **2.43.0** (passen zum Projekt) |
| Reboot | nach Erst-Installation ausgeführt (`/var/run/reboot-required` ⇒ erledigt) |

**Installationsschritte (Reihenfolge = Abhängigkeit):**
1. **Reboot** (Pflicht des Providers) — erledigt 20.10.2026.
2. **Keys:** neues Deploy-Paar **auf dem Server** erzeugen
   (`/root/.ssh/kmhr-deploy`, privat 600) ⇒ der private Schlüssel **verlässt den Host
   nicht**; nur der **öffentliche** geht (a) in die **Repo-Deploy-Keys**
   (`gh api repos/abatn/km-hr-agent/keys`, `read_only=true`) und (b) in das
   **GitHub-Secret `CONTABO_SSH_KEY`** (einmalig, für „GitHub → Server").
   Der Management-Key (`batnini-contabo`) kommt in `authorized_keys` (key-basierter
   Admin-Zugang statt Passwort).
3. **Clone:** `git config --global core.sshCommand "ssh -i /root/.ssh/kmhr-deploy -o
   IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"` + `git clone` nach
   `/opt/km-hr-agent` (Deploy-Key ist read-only ⇒ nur lesen, Deploy erfolgt per
   `git reset --hard`).
4. **Laufzeit:** venv + `pip install -r requirements.txt`; die drei Secret-Dateien
   `.env` / `.env-runner` / `.env-email` **manuell** aus dem lokalen Stand
   (gitignored, **nie** über git) sowie `data/` (Live-DB) und `testdaten/`
   (Profil-Dateien für den Skill-7-Generator) übertragen.
5. **Dienst:** Unit `km-hr-agent.service` (`WorkingDirectory=/opt/km-hr-agent`,
   `ExecStart` = venv-Python `-m webui.main`); der **Agent-Runner startet mit der
   App** (`webui/logic.py::ensure_agent_runner`, Codemark) — kein zweiter Unit nötig.
6. **Health-Check:** `curl 127.0.0.1:8080` (max. 60 s), danach `git rev-parse HEAD`
   == Ziel-SHA.

**Sicherheitsregel vor der Freischaltung (AGENTS.md „Netz-Restrisiko"):** Das
Live-Admin-Konto trägt weiterhin das frühere Seed-Passwort ⇒ die App darf **nicht**
ungeschützt öffentlich lauschen. Vor `0.0.0.0:8080` also entweder das
**Admin-Passwort rotieren** (empfohlen, da neuer Host) **oder** `ufw`/Reverse-Proxy
so setzen, dass 8080 nicht öffentlich erreichbar ist (nur 22 für SSH).

**Workflow-Anpassung:** `.github/workflows/deploy-contabo.yml` hardcodiert die alte
IP an **3 Stellen** (`ssh-keyscan`, SSH-Ziel, SHA-Abgleich) ⇒ auf den neuen Host
umstellen (eigener Commit, Teil dieser Migration).
