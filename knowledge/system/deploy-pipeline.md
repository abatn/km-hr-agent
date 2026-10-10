# Deploy-Pipeline: GitHub → Contabo VPS (SSH-Variante)

> **Stand:** 06.10.2026 · **Status:** implementiert (Workflow `.github/workflows/deploy-contabo.yml`)
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
3. Secret nach `~/.ssh/id_contabo` (600) + `ssh-keyscan 169.58.83.32`.
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
