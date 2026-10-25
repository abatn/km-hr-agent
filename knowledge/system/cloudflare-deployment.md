# Cloudflare-Deployment: `jobs.hanibal-ai.com`

**Stand:** 25.10.2026 · **Status:** implementiert · **Ziel:** `https://jobs.hanibal-ai.com` → Cloudflare → Caddy → `127.0.0.1:8080`

## Architektur

```
Browser
  │ HTTPS (Cloudflare Edge, Proxy AN)
  ▼
Cloudflare (DNS A jobs → 176.57.189.201, orange cloud)
  │ HTTPS (Full strict, Origin-Zertifikat von Caddy/Let's Encrypt)
  ▼
Caddy auf 176.57.189.201 :443  (Site: jobs.hanibal-ai.com)
  │ HTTP/WebSocket (Upgrade) → 127.0.0.1:8080
  ▼
NiceGUI-App (uvicorn, KMHR_HOST=127.0.0.1)
```

- **Port 8080 ist nicht öffentlich**; die App bindet per Default an `127.0.0.1`.
  `KMHR_HOST=0.0.0.0` nur bewusst für LAN/Diagnose.
- **Caddy** terminiert TLS am Origin und proxyt HTTP + Socket.IO/WebSocket.
  Site-Datei: `deploy/caddy/jobs.hanibal-ai.com.caddy` → `/etc/caddy/conf.d/`.
- **systemd**: `deploy/systemd/km-hr-agent.service` setzt `KMHR_HOST=127.0.0.1` und
  `KMHR_COOKIE_SECURE=1` (Session-Cookie nur über HTTPS).

## DNS (Cloudflare Dashboard)

| Typ | Name | Inhalt | Proxy |
|---|---|---|---|
| A | `jobs` | `176.57.189.201` | **Proxied (orange)** |

- Der A-Record zeigt auf den Contabo-VPS. Cloudflare liefert dafür eigene Edge-IPs
  (`getent ahosts jobs.hanibal-ai.com` → 104.x/172.x).
- Kein CNAME, kein Port 8080 in der DNS.

## TLS / Cloudflare-Einstellungen

| Einstellung | Soll | Warum |
|---|---|---|
| SSL/TLS → Overview | **Full (strict)** | Cloudflare prüft das Origin-Zertifikat; Caddy holt ein gültiges Let's-Encrypt-Zertifikat. |
| Edge Certificates → Always Use HTTPS | **ON** | HTTP wird auf HTTPS umgeleitet. |
| Minimum TLS | **1.2** | Aktuelle Browser/Firefox; keine Legacy-Clients nötig. |
| WebSockets | **ON** (Default) | NiceGUI/Socket.IO braucht Upgrade. |
| Rocket Loader | **OFF** | Kann ES-Module/Inline-Skripte der Landingpage verzögern/brechen. |
| Brotli | **ON** | Caddy/Cloudflare komprimieren; kein Nachteil. |
| Cache Rules | HTML/`/` **nicht cachen** | NiceGUI rendert pro Session; statische `/_nicegui/*` sind versioniert und cachebar. |
| Bot Fight Mode | optional **OFF** | Kann Login/Health-Checks stören; WAF-Regeln bewusst separat planen. |

Caddy nutzt für beide Sites (travel + jobs) HTTP-01, weil Cloudflare proxied ist und
TLS-ALPN an der Edge terminiert:

```caddyfile
tls {
    issuer acme {
        disable_tlsalpn_challenge
    }
}
```

## Origin-Konfiguration (VPS)

1. **Caddy-Site installieren**
   ```bash
   install -d -m 755 /etc/caddy/conf.d
   install -m 644 deploy/caddy/jobs.hanibal-ai.com.caddy \
     /etc/caddy/conf.d/jobs.hanibal-ai.com.caddy
   grep -Fq 'import /etc/caddy/conf.d/*.caddy' /etc/caddy/Caddyfile \
     || echo 'import /etc/caddy/conf.d/*.caddy' >> /etc/caddy/Caddyfile
   caddy validate --config /etc/caddy/Caddyfile
   systemctl reload caddy
   ```
2. **systemd-Unit installieren** (Loopback-Bindung)
   ```bash
   install -m 644 deploy/systemd/km-hr-agent.service \
     /etc/systemd/system/km-hr-agent.service
   systemctl daemon-reload
   systemctl restart km-hr-agent
   ```
3. **Prüfen**
   ```bash
   ss -ltnp | grep 8080          # muss 127.0.0.1:8080 sein
   curl -fsS http://127.0.0.1:8080/ >/dev/null
   curl -kfsS -H 'Host: jobs.hanibal-ai.com' https://127.0.0.1/ >/dev/null
   curl -fsSI https://jobs.hanibal-ai.com/
   ```

Der Deploy-Workflow `.github/workflows/deploy-contabo.yml` installiert beide Dateien
bei jedem Deploy (idempotent), validiert die Caddyfile vor dem Reload und prüft
anschließend `https://jobs.hanibal-ai.com/` von GitHub aus.

## Cloudflare-Proxy und WebSocket

- Caddy setzt `X-Forwarded-Proto`, `X-Forwarded-For`, `X-Real-IP`; `flush_interval -1`
  verhindert Pufferung für Socket.IO.
- Cloudflare unterstützt WebSocket-Upgrades im Proxy-Modus ohne Extraregel.
- Ein 502 bedeutet Origin-App down; **525** bedeutet Origin-TLS-Handshake fehlgeschlagen
  (kein/ungültiges Zertifikat für den Host) — dann Caddy-Log prüfen:
  `journalctl -u caddy -n 50 --no-pager`.

## Health-Checks

| Ebene | Befehl | Soll |
|---|---|---|
| App lokal | `curl -fsS http://127.0.0.1:8080/` | HTTP 200 |
| Caddy lokal | `curl -kfsS -H 'Host: jobs.hanibal-ai.com' https://127.0.0.1/` | HTTP 200 |
| Cloudflare extern | `curl -fsSI https://jobs.hanibal-ai.com/` | HTTP 200, `server: cloudflare`, `cf-ray` |
| WebSocket | Login-Seite im Browser öffnen; keine Socket.IO-Fehler in der Konsole | verbunden |
| Deploy | GitHub-Action „Deploy Contabo" | success inkl. externem Health-Check |

## Rollback

- **Caddy:** `cp /root/Caddyfile.bak-<ts> /etc/caddy/Caddyfile`, `rm /etc/caddy/conf.d/jobs.hanibal-ai.com.caddy`,
  `systemctl reload caddy`.
- **systemd/Code:** `git reset --hard <SHA>` in `/opt/km-hr-agent`, `systemctl restart km-hr-agent`.
- **Cloudflare:** DNS-Record pausieren (graue Wolke) oder auf alten Origin zeigen; SSL-Modus
  erst nach Prüfung ändern.

## Sicherheit

- Der öffentliche Weg ist ausschließlich `443` über Cloudflare; `8080` bleibt loopback.
- Das Live-Admin-Konto trägt weiterhin das alte Seed-Passwort. Die Cloudflare-Freischaltung
  ersetzt **nicht** die Passwort-Rotation; siehe `knowledge/system/configuration-secrets.md`.
  Bis zur Rotation ist der öffentliche Betrieb nur mit Cloudflare Access/WAF-Regeln oder
  nach Rotation freizugeben.
- Keine Cloudflare-API-Tokens im Repo. DNS/SSL-Regeln werden im Dashboard gepflegt oder
  über einen separat gespeicherten Token (nicht hier) automatisiert.

## Quellen

- Cloudflare DNS Proxy: <https://developers.cloudflare.com/dns/proxy-status/>
- Cloudflare SSL/TLS-Modi: <https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/>
- Cloudflare WebSockets: <https://developers.cloudflare.com/network/websockets/>
- Caddy Automatic HTTPS: <https://caddyserver.com/docs/automatic-https>
- Caddy `reverse_proxy`: <https://caddyserver.com/docs/caddyfile/directives/reverse_proxy>
