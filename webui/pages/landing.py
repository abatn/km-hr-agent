"""
Landing page (Startseite „/") für den KM-HR-Agent – NiceGUI.
=============================================================
Zeigt VOR dem Login, was der KM-HR-Agent tut: eine in sich geschlossene,
EXAKT 30-sekündige Three.js-Animation (5 Kapitel, `TOTAL = 30.0`) in Endlosschleife
mit sichtbarem Countdown 30 → 0, Fortschrittsbalken und Button „Nochmal ansehen“.
Die 5-Schritte-Liste + Quellen liegen in einem aufklappbaren Bereich
(`ui.expansion` „Details & Quellen“) – die Hauptseite bleibt aufgeräumt.

Nutzerentscheidungen 02.10.2026:
* Three.js LOKAL gebündelt (webui/static/three/, MIT, npm-Paket three@0.186.1)
  – KEIN externes CDN, voll offline lauffähig. ESM/Import-Map in add_head_html.
* Route „/" zeigt Gästen die Landingpage; eingeloggte Nutzer werden wie bisher
  auf /admin | /employer | /candidate umgeleitet (Verhalten aus webui/main.py
  „Index (redirect)", Codemarke, Stand 02.10.2026).
* Farben: Blau #1E40AF (PRIMARY) + Gold #F59E0B (ACCENT), Weiß – Quelle:
  webui/theme.py (Codemarke PRIMARY/ACCENT, Stand 02.10.2026), Vorgabe Nutzer.
* Typografie: lokaler System-Stack Inter/Roboto – Design-Entscheidung (keine
  externe Quelle), bewusst KEIN Google-Fonts-CDN (Offline-Pflicht).

Lab-Konformität der Zahlen (Codemarke + Messdatum 02.10.2026, Drift-Regel
AGENTS.md – KEINE Datei:Zeile):
* Regionen DE/FR/CH + Nordafrika .......... knowledge/portal/candidate-portal-fields.md (existiert)
* CV-Upload → PDF-Extraktion .............. `_upload_section` (webui/pages/candidate.py)
                                            + `logic.extract_pdf_text` (webui/logic.py)
* Agent-Kette 10 Tasks .................... webui/db.py, Docstring der Bewerbungs-Kette
                                            (`apply_to_job`) – 10 = gezählt
* Matching 7 Kategorien ................... `KATEGORIE_MAX` (webui/logic.py) – 7 = gezählt
* Score 0–100 ............................. `berechne_match_score` (webui/logic.py)
* Compliance DE/FR/CH ..................... knowledge/legal/compliance-rules.md (existiert)
* HR-Entscheidung (einladen/ablehnen/einstellen) ... `ALLOWED_TRANSITIONS` (webui/pages/employer.py)
* Video-Meeting VDO.Ninja (NICHT Jitsi) ... knowledge/system/vdo-ninja-migration.md (27.09.2026)
* Ende „Quantenfeld“ + Ablaufdauer 30 s + Loop/Countdown + Schrift-Stack ... Design-Entscheidung (keine Quelle)
* Balkenhöhen der 7 Kategorien = `KATEGORIE_MAX` (Maximalwerte, KEINE Gewichte; Gewichte: `BASELINE_GEWINCHTE`)

Muster für Head-HTML-Einbettung: webui/pages/login.py (`ui.add_head_html`).
"""
from __future__ import annotations

import json
from pathlib import Path

from nicegui import app, ui

from webui import logic
from webui.theme import C, inject_css
from webui.i18n import language_switcher, apply_direction, _

_WEBUI_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = _WEBUI_DIR / "static"

# Statische Dateien (Three.js r186.1, MIT) unter /static ausliefern.
# NiceGUI-eigene Assets liegen unter /_nicegui/<version>/static – keine Kollision
# (geprüft 02.10.2026, nicegui/nicegui.py `app.mount(f'/_nicegui/...')`).
app.add_static_files("/static", str(STATIC_DIR))


# ─── Landing-HTML/CSS + Three.js-Szene (inline, moduliert) ───────────
# Bewusst ein einziges add_head_html (Muster: webui/pages/login.py):
# Import-Map MUSS vor dem Modul-Skript stehen, das „three" importiert.

_HEAD_HTML = r"""
<style>
:root {
    --kmhr-primary: #1E40AF;
    --kmhr-primary-dark: #1E3A8A;
    --kmhr-primary-light: #3B82F6;
    --kmhr-accent: #F59E0B;
    --kmhr-ink: #0F172A;
    --kmhr-muted: #64748B;
    --kmhr-line: #E2E8F0;
    --kmhr-bg: #F8FAFC;
}
html { scroll-behavior: smooth; }
body {
    background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 42%, #F8FAFC 100%);
    font-family: Inter, Roboto, "Segoe UI", system-ui, -apple-system, sans-serif;
    color: var(--kmhr-ink);
}
.kmhr-wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
.kmhr-top { display: flex; align-items: center; justify-content: space-between;
            padding: 22px 0 10px; }
.kmhr-brand { display: flex; align-items: center; gap: 10px; font-weight: 700;
              font-size: 1.15rem; color: var(--kmhr-primary-dark); }
.kmhr-hero { padding: 42px 0 26px; }
.kmhr-kicker { display: inline-block; font-size: 0.82rem; letter-spacing: 0.14em;
               text-transform: uppercase; color: var(--kmhr-primary);
               background: rgba(30, 64, 175, 0.08); border: 1px solid rgba(30, 64, 175, 0.18);
               border-radius: 999px; padding: 6px 14px; font-weight: 600; }
.kmhr-h1 { font-size: clamp(1.15rem, 2.2vw, 1.5rem); line-height: 1.2; font-weight: 700;
           letter-spacing: -0.02em; margin: 18px 0 14px; color: var(--kmhr-primary-dark);
           max-width: 980px; text-wrap: balance; }
.kmhr-h1 .kmhr-gold { color: var(--kmhr-accent); }
.kmhr-sub { font-size: 1.06rem; line-height: 1.65; color: var(--kmhr-muted);
            max-width: 720px; margin: 0 0 26px; }
.kmhr-section { padding: 36px 0 8px; }
.kmhr-h2 { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.01em;
           color: var(--kmhr-primary-dark); margin: 0 0 8px; }
.kmhr-lead { color: var(--kmhr-muted); font-size: 1.05rem; line-height: 1.7;
             max-width: 760px; margin: 0 0 28px; }
/* align-items: stretch ist NÖTIG: NiceGUI setzt für .nicegui-row
   `align-items: flex-start` (nicegui.css), wodurch die Grid-Kacheln NICHT
   auf gleiche Höhe gestreckt werden (Bug-Fund 02.10.2026: Aufgabe 223 px vs.
   Für wen/Nutzen 175 px). */
.kmhr-grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px;
              align-items: stretch; }
.kmhr-grid2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px;
              align-items: stretch; }
@media (max-width: 760px) { .kmhr-grid3, .kmhr-grid2 { grid-template-columns: 1fr; } }
.kmhr-card { background: #FFFFFF; border: 1px solid var(--kmhr-line); border-radius: 18px;
             padding: 22px 22px 20px; box-shadow: 0 10px 30px -18px rgba(30, 64, 175, 0.25);
             transition: transform 0.25s ease, box-shadow 0.25s ease; }
.kmhr-card:hover { transform: translateY(-3px); box-shadow: 0 18px 40px -18px rgba(30, 64, 175, 0.35); }
.kmhr-card h3 { margin: 0 0 8px; font-size: 1.02rem; font-weight: 700; color: var(--kmhr-primary-dark); }
.kmhr-card p { margin: 0; color: var(--kmhr-muted); line-height: 1.6; font-size: 0.95rem; }
.kmhr-card .kmhr-ico { margin-bottom: 10px; display: block; }

/* ── Animations-Host ─────────────────────────────────────────────── */
.kmhr-anim-host { position: relative; width: 100%; min-height: 520px; height: clamp(520px, 68vh, 720px);
                  border-radius: 22px; overflow: hidden; border: 1px solid var(--kmhr-line);
                  background: #F8FAFC; box-shadow: 0 30px 70px -40px rgba(30, 64, 175, 0.45); }
.kmhr-canvas { position: absolute; inset: 0; }
.kmhr-canvas canvas { display: block; width: 100%; height: 100%; }
.kmhr-overlay { position: absolute; inset: 0; pointer-events: none;
                display: flex; flex-direction: column; justify-content: space-between;
                padding: 26px 28px 22px; }
.kmhr-cap { max-width: 440px; background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(226, 232, 240, 0.9); border-radius: 16px;
            padding: 18px 22px 16px; backdrop-filter: blur(10px);
            opacity: 0; transform: translateY(10px); transition: opacity 0.45s ease, transform 0.45s ease; }
.kmhr-cap-show { opacity: 1; transform: translateY(0); }
.kmhr-cap-kicker { font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase;
                   font-weight: 700; color: var(--kmhr-accent); }
.kmhr-cap-title { margin: 6px 0 6px; font-size: 1.32rem; font-weight: 700; color: var(--kmhr-primary-dark); }
.kmhr-cap-text { margin: 0; color: var(--kmhr-ink); line-height: 1.5; font-size: 0.97rem; }
.kmhr-toprow { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.kmhr-count { flex: 0 0 auto; display: flex; align-items: baseline; gap: 4px;
              background: rgba(255, 255, 255, 0.85); border: 1px solid var(--kmhr-line);
              border-radius: 999px; padding: 6px 16px; backdrop-filter: blur(8px);
              font-variant-numeric: tabular-nums; color: var(--kmhr-primary-dark); }
.kmhr-count-n { font-size: 1.5rem; font-weight: 800; min-width: 2ch; text-align: right; }
.kmhr-count-u { font-size: 0.8rem; font-weight: 600; color: var(--kmhr-muted); }
.kmhr-fade { position: absolute; inset: 0; background: #F8FAFC; opacity: 1; pointer-events: none; }
.kmhr-bottom { display: flex; align-items: center; gap: 16px; pointer-events: auto; }
.kmhr-dots { display: flex; gap: 8px; }
.kmhr-dot { width: 10px; height: 10px; border-radius: 999px; border: 0; cursor: pointer;
            background: rgba(30, 64, 175, 0.25); transition: all 0.25s ease; padding: 0; }
.kmhr-dot-on { background: var(--kmhr-accent); transform: scale(1.35); }
.kmhr-progress { flex: 1; height: 5px; border-radius: 999px; background: rgba(30, 64, 175, 0.14); overflow: hidden; }
.kmhr-progress-fill { height: 100%; width: 0%; border-radius: 999px;
                      background: linear-gradient(90deg, var(--kmhr-primary-light), var(--kmhr-accent)); }
.kmhr-replay { border: 1px solid var(--kmhr-line); background: rgba(255, 255, 255, 0.85);
               color: var(--kmhr-primary-dark); font-weight: 600; font-size: 0.85rem;
               border-radius: 999px; padding: 9px 18px; cursor: pointer; min-height: 40px; }
.kmhr-replay:hover { border-color: var(--kmhr-primary-light); }
.kmhr-end { position: absolute; right: 28px; bottom: 76px; opacity: 0; pointer-events: none;
            transition: opacity 0.6s ease; }
.kmhr-end-show { opacity: 1; pointer-events: auto; }
.kmhr-cta { display: inline-block; background: var(--kmhr-primary); color: #FFFFFF;
            text-decoration: none; font-weight: 700; border-radius: 14px;
            padding: 14px 30px; font-size: 1.02rem;
            box-shadow: 0 14px 30px -12px rgba(30, 64, 175, 0.55); }
.kmhr-cta:hover { background: var(--kmhr-primary-dark); }
.kmhr-fallback .kmhr-canvas { display: none; }

/* ── Aufklappbarer Bereich „Details & Quellen“ ──────────────────── */
.kmhr-details { width: 100%; border: 1px solid var(--kmhr-line); border-radius: 16px;
                background: #FFFFFF; margin-top: 18px; }
.kmhr-steps { margin: 0; padding: 0; list-style: none; counter-reset: kmhr; }
.kmhr-steps li { counter-increment: kmhr; display: flex; gap: 14px; align-items: baseline;
                 padding: 8px 0; color: var(--kmhr-ink); font-size: 0.98rem; line-height: 1.5; }
.kmhr-steps li::before { content: counter(kmhr); flex: 0 0 26px; height: 26px; border-radius: 8px;
                         display: inline-flex; align-items: center; justify-content: center;
                         font-weight: 700; font-size: 0.82rem; color: var(--kmhr-primary-dark);
                         background: rgba(245, 158, 11, 0.16); }
.kmhr-src { color: var(--kmhr-muted); font-size: 0.8rem; line-height: 1.7; }
.kmhr-src code { background: #F1F5F9; border: 1px solid var(--kmhr-line); border-radius: 6px;
                 padding: 1px 6px; font-size: 0.76rem; }
.kmhr-footer { margin: 48px 0 32px; padding: 30px 0 0; border-top: 1px solid var(--kmhr-line);
               color: var(--kmhr-muted); font-size: 0.88rem; line-height: 1.7; }
.kmhr-foot-link { color: var(--kmhr-primary); text-decoration: none; font-size: 0.9rem; }
.kmhr-foot-link:hover { text-decoration: underline; }
/* ── Mobil (≤768 px): Animation auf ≤45 vh, eine Primär-CTA vor dem Inhalt ── */
@media (max-width: 768px) {
  .kmhr-anim-host { min-height: 0 !important; height: 45vh !important; }
  .kmhr-m-hide { display: none !important; }
}
</style>

<script type="module">
/* Relative Import Reference (kein bare specifier): Three.js direkt per URL laden.
   Grund: NiceGUI setzt bereits eine Import-Map (vue/sass/...); laut HTML-Spec ist nur
   EINE Import-Map erlaubt — eine zweite (three) wird ignoriert -> "bare specifier not
   remapped". Der URL-Import braucht keine Import-Map; three.module.js laedt intern
   ./three.core.js relativ nach. Quelle: sbcode.net "Module Specifiers Versus Relative
   Import References" + spidermonkey.dev "Import maps, Part 2" (only one map allowed). */
import * as THREE from '/static/three/three.module.js';

(function () {
  'use strict';

  /* ── Kapitel-Timeline (Zahlen mit Quelle, siehe Modul-Docstring) ── */
  const TASKS = ['send_confirmation', 'extract_profile', 'match_candidate',
                 'check_compliance', 'assess_culture_fit', 'verify_documents',
                 'check_visa', 'explain_match', 'check_gdpr', 'notify_user'];
  /* Name + Maximalwert je Kategorie = KATEGORIE_MAX (webui/logic.py). Der Wert steuert
     NUR die Balkenhöhe und wird nicht angezeigt (Maximalwert ≠ Gewicht). */
  const KATEGORIEN = [['kern', 30], ['erfahrung', 30], ['bildung', 15], ['standort', 10],
                      ['branche', 10], ['soft', 10], ['sprache', 10]];

  /* 5 Kapitel in exakt 30,0 s. Das Agenten-Prinzip: Gehirn → Loop →
     Sub-Agenten → Werkzeuge → Ergebnis. Je Kapitel nur EINE kurze Textzeile;
     Quellen/Entscheidungen stehen in ui/ANIMATION_ENTSCHEIDUNG.md. */
  const CH = [
    { id: 'brain', zi: 0, t0: 0.0, t1: 5.2,
      kicker: 'Kapitel 1', title: 'Das Gehirn',
      text: 'Der Orchestrator plant jede Aufgabe und behält den Überblick.' },
    { id: 'loop', zi: 1, t0: 6.0, t1: 11.2,
      kicker: 'Kapitel 2', title: 'Die Loop',
      text: 'Der Runner fragt alle 60 Sekunden die Queue ab – bis zu drei Versuche pro Task.' },
    { id: 'agents', zi: 2, t0: 12.0, t1: 17.2,
      kicker: 'Kapitel 3', title: 'Die Sub-Agenten',
      text: 'Zehn spezialisierte Agenten arbeiten die Bewerbung Schritt für Schritt ab.' },
    { id: 'tools', zi: 3, t0: 18.0, t1: 23.2,
      kicker: 'Kapitel 4', title: 'Die Werkzeuge',
      text: 'MCP-Connectoren verbinden PDF, Recht, Mail, Meeting und Sprachtests.' },
    { id: 'result', zi: 4, t0: 24.0, t1: 30.0,
      kicker: 'Kapitel 5', title: 'Das Ergebnis',
      text: 'Score, Einladung per VDO.Ninja und Onboarding – der Mensch entscheidet.' },
  ];
  /* i18n (Phase 2b 02.10.2026): Kapiteltexte aus window.__KMHR_CH__ überschreiben,
     das die Seite pro Session (Sprache) vor dem Modul-Skript setzt. */
  if (window.__KMHR_CH__) {
    CH.forEach((c, i) => {
      const t = window.__KMHR_CH__[i];
      if (t) { c.kicker = t.kicker; c.title = t.title; c.text = t.text; }
    });
  }
  const TOTAL = 30.0;
  const SPACING = 30;
  const COLORS = { primary: 0x1E40AF, primaryLight: 0x3B82F6, accent: 0xF59E0B,
                   sky: 0x93C5FD, bg: 0xF8FAFC, ink: 0x1E3A8A };

  /* Deterministischer Zufall (Reproduzierbarkeit, Lab-Konvention) */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rng = mulberry32(20261002);

  const clamp01 = (v) => Math.max(0, Math.min(1, v));
  const smooth = (v) => { const x = clamp01(v); return x * x * (3 - 2 * x); };
  const lerp = (a, b, f) => a + (b - a) * f;
  const S = { captionIdx: -1, dots: [], startTime: 0, pausedAt: null, autoPaused: false, offscreen: false,
              staticIdx: 0, reduce: false, endEl: null, fillEl: null, fadeEl: null,
              countEl: null, frames: 0, loops: 0 };

  function whenHostReady(fn) {
    const el = document.getElementById('kmhr-anim-host');
    if (el) { fn(el); return; }
    let tries = 0;
    const timer = setInterval(() => {
      const host = document.getElementById('kmhr-anim-host');
      if (host) { clearInterval(timer); fn(host); }
      else if (++tries > 200) clearInterval(timer);
    }, 50);
  }

  function setCaption(i) {
    if (S.captionIdx === i) return;
    S.captionIdx = i;
    const ch = CH[i];
    const cap = document.getElementById('kmhr-cap');
    if (!cap) return;
    cap.classList.remove('kmhr-cap-show');
    setTimeout(() => {
      document.getElementById('kmhr-cap-kicker').textContent = ch.kicker;
      document.getElementById('kmhr-cap-title').textContent = ch.title;
      document.getElementById('kmhr-cap-text').textContent = ch.text;
      cap.classList.add('kmhr-cap-show');
    }, 160);
    S.dots.forEach((d, k) => d.classList.toggle('kmhr-dot-on', k === i));
  }

  function buildUi(host) {
    host.innerHTML = `
      <div class="kmhr-canvas" aria-hidden="true"></div>
      <div class="kmhr-fade" id="kmhr-fade"></div>
      <div class="kmhr-overlay">
        <div class="kmhr-toprow">
          <div class="kmhr-cap kmhr-cap-show" id="kmhr-cap">
            <div class="kmhr-cap-kicker" id="kmhr-cap-kicker"></div>
            <h3 class="kmhr-cap-title" id="kmhr-cap-title"></h3>
            <p class="kmhr-cap-text" id="kmhr-cap-text"></p>
          </div>
          <div class="kmhr-count" aria-label="Verbleibende Sekunden">
            <span class="kmhr-count-n" id="kmhr-count-n">30</span><span class="kmhr-count-u">s</span>
          </div>
        </div>
        <div class="kmhr-end" id="kmhr-end">
          <a class="kmhr-cta" href="/login">Zum Login &rarr;</a>
        </div>
        <div class="kmhr-bottom">
          <div class="kmhr-dots" id="kmhr-dots"></div>
          <div class="kmhr-progress"><div class="kmhr-progress-fill" id="kmhr-progress-fill"></div></div>
          <button class="kmhr-replay" id="kmhr-pause" type="button"
                  title="Pause" aria-label="Pause">&#10074;&#10074;</button>
          <button class="kmhr-replay" id="kmhr-replay" type="button">&#8635; Nochmal ansehen</button>
        </div>
      </div>`;
    const dotsEl = document.getElementById('kmhr-dots');
    CH.forEach((ch, i) => {
      const b = document.createElement('button');
      b.className = 'kmhr-dot';
      b.type = 'button';
      b.title = ch.title;
      b.addEventListener('click', () => {
        if (S.reduce) { S.staticIdx = i; setCaption(i); }
        else {
          S.startTime = performance.now() - ch.t0 * 1000;
        }
      });
      dotsEl.appendChild(b);
      S.dots.push(b);
    });
    document.getElementById('kmhr-replay').addEventListener('click', () => {
      S.staticIdx = 0;
      S.startTime = performance.now();
      setCaption(0);
    });
    const pauseBtn = document.getElementById('kmhr-pause');
    pauseBtn.addEventListener('click', () => {
      if (S.pausedAt === null) {
        S.pausedAt = performance.now();
        pauseBtn.innerHTML = '&#9654;';
        pauseBtn.setAttribute('aria-label', 'Weiter');
        pauseBtn.title = 'Weiter';
      } else {
        S.startTime += performance.now() - S.pausedAt;
        S.pausedAt = null;
        S.autoPaused = false;
        pauseBtn.innerHTML = '&#10074;&#10074;';
        pauseBtn.setAttribute('aria-label', 'Pause');
        pauseBtn.title = 'Pause';
      }
    });
    S.endEl = document.getElementById('kmhr-end');
    S.fillEl = document.getElementById('kmhr-progress-fill');
    S.fadeEl = document.getElementById('kmhr-fade');
    S.countEl = document.getElementById('kmhr-count-n');
  }

  /* ── Helfer: Text-Sprite (Canvas-Texture, offline) ─────────────── */
  function roundRect(g, x, y, w, h, r) {
    g.beginPath();
    if (g.roundRect) { g.roundRect(x, y, w, h, r); return; }
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  function makeLabel(text, opts) {
    const o = opts || {};
    const sx = o.sx || 5.2, sy = o.sy || 1.3;
    const h = 160, w = Math.round(h * sx / sy);   /* Canvas-Format = Sprite-Format */
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const g = c.getContext('2d');
    g.fillStyle = o.bg || 'rgba(255,255,255,0.88)';
    roundRect(g, 4, 4, w - 8, h - 8, 36);
    g.fill();
    g.strokeStyle = o.border || 'rgba(30,64,175,0.18)';
    g.lineWidth = 3;
    g.stroke();
    g.fillStyle = o.color || '#1E3A8A';
    g.font = '700 ' + (o.px || 74) + 'px Inter, Roboto, sans-serif';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(text, w / 2, h / 2, w - 48);
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 4;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    sprite.scale.set(sx, sy, 1);
    return sprite;
  }

  /* ── Agenten-Prinzip: 5 Stationen ─────────────────────────────── */

  /* 1) Das Gehirn: zentraler Orchestrator als Drahtgitter-Kern,
     umkreist von Nervenpartikeln und drei Ringbahnen. */
  function buildBrain() {
    const g = new THREE.Group();
    const L = window.__KMHR_LABELS__ || {};
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(2.45, 2),
      new THREE.MeshStandardMaterial({
        color: COLORS.primary, roughness: 0.28, metalness: 0.55,
        emissive: COLORS.primaryLight, emissiveIntensity: 0.22, wireframe: true }));
    g.add(core);
    const shell = new THREE.Mesh(
      new THREE.IcosahedronGeometry(3.15, 1),
      new THREE.MeshBasicMaterial({ color: COLORS.primaryLight, wireframe: true,
                                    transparent: true, opacity: 0.12 }));
    g.add(shell);
    const N = 240;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const r = 3.3 + rng() * 2.2;
      const th = rng() * Math.PI * 2;
      const ph = Math.acos(2 * rng() - 1);
      pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
      pos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
      pos[i * 3 + 2] = r * Math.cos(ph);
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const cloud = new THREE.Points(pGeo, new THREE.PointsMaterial({
      color: COLORS.accent, size: 0.09, transparent: true, opacity: 0.8,
      sizeAttenuation: true }));
    g.add(cloud);
    const rings = [];
    [0.0, Math.PI / 3, -Math.PI / 3].forEach((rx, i) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(3.5 + i * 0.22, 0.035, 8, 96),
        new THREE.MeshBasicMaterial({ color: i === 1 ? COLORS.accent : COLORS.primaryLight,
                                      transparent: true, opacity: 0.55 }));
      ring.rotation.x = rx;
      ring.rotation.y = i * 0.6;
      g.add(ring); rings.push(ring);
    });
    const label = makeLabel(L.brain || 'Orchestrator', { sx: 4.4, sy: 1.05 });
    label.position.set(0, 4.7, 0);
    g.add(label);
    return { group: g, update: (t) => {
      core.rotation.y = t * 0.38; core.rotation.x = t * 0.11;
      shell.rotation.y = -t * 0.16; shell.rotation.z = t * 0.07;
      core.scale.setScalar(1 + Math.sin(t * 1.7) * 0.035);
      cloud.rotation.y = t * 0.11;
      cloud.rotation.x = Math.sin(t * 0.23) * 0.16;
      rings.forEach((r, i) => { r.rotation.z = t * (0.22 + i * 0.08); });
    } };
  }

  /* 2) Die Loop: fünf Stationen der Runner-Queue auf einer Ringbahn,
     ein goldener Impuls läuft im Kreis. */
  function buildLoop() {
    const g = new THREE.Group();
    const L = window.__KMHR_LABELS__ || {};
    const rings = [];
    [{ r: 3.2, tube: 0.10, color: COLORS.primaryLight, rx: 0.0, ry: 0.0 },
     { r: 3.65, tube: 0.05, color: COLORS.accent, rx: 0.5, ry: 0.3 },
     { r: 2.75, tube: 0.05, color: COLORS.sky, rx: -0.5, ry: -0.3 }].forEach((s) => {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(s.r, s.tube, 10, 96),
        new THREE.MeshBasicMaterial({ color: s.color, transparent: true, opacity: 0.6 }));
      ring.rotation.x = s.rx; ring.rotation.y = s.ry;
      g.add(ring); rings.push(ring);
    });
    const nodeGeo = new THREE.OctahedronGeometry(0.22, 0);
    const nodes = [];
    const nodeLabels = ['Queue', 'Claim', 'Task', 'Retry', 'Done'];
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2 - Math.PI / 2;
      const node = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
        color: i === 4 ? COLORS.accent : COLORS.primaryLight,
        emissive: i === 4 ? COLORS.accent : COLORS.primaryLight,
        emissiveIntensity: 0.25, roughness: 0.35, metalness: 0.25 }));
      node.position.set(Math.cos(a) * 3.2, Math.sin(a) * 3.2, 0);
      g.add(node); nodes.push(node);
      const lab = makeLabel(nodeLabels[i], { px: 56, sx: 2.5, sy: 0.75 });
      lab.position.set(Math.cos(a) * 4.25, Math.sin(a) * 4.25, 0);
      g.add(lab);
    }
    const orb = new THREE.Mesh(new THREE.SphereGeometry(0.3, 16, 16),
      new THREE.MeshBasicMaterial({ color: COLORS.accent }));
    g.add(orb);
    const label = makeLabel(L.loop || '60-s-Loop', { sx: 4.2, sy: 1.0 });
    label.position.set(0, 5.0, 0);
    g.add(label);
    return { group: g, update: (t, local) => {
      rings.forEach((r, i) => { r.rotation.z = t * (0.18 + i * 0.09); });
      nodes.forEach((n, i) => {
        n.rotation.y = t * 0.8 + i;
        n.scale.setScalar(1 + 0.18 * Math.sin(t * 2.4 + i * 1.1));
      });
      const a = ((local || 0) * 0.95) % (Math.PI * 2) - Math.PI / 2;
      orb.position.set(Math.cos(a) * 3.2, Math.sin(a) * 3.2, 0.4);
    } };
  }

  /* 3) Die Sub-Agenten: zehn spezialisierte Aufgaben-Knoten auf einem Bogen. */
  function buildSubAgents() {
    const g = new THREE.Group();
    const L = window.__KMHR_LABELS__ || {};
    const nodes = [];
    const pts = [];
    const geo = new THREE.IcosahedronGeometry(0.5, 1);
    for (let i = 0; i < TASKS.length; i++) {
      const x = -8.2 + i * (16.4 / (TASKS.length - 1));
      const y = Math.sin((i / (TASKS.length - 1)) * Math.PI) * 1.4 + 0.2;
      const z = Math.sin(i * 1.7) * 0.55;
      const mat = new THREE.MeshStandardMaterial({
        color: COLORS.primaryLight, roughness: 0.35, metalness: 0.2,
        emissive: COLORS.primaryLight, emissiveIntensity: 0.12 });
      const m = new THREE.Mesh(geo, mat);
      m.position.set(x, y, z);
      g.add(m); nodes.push(m);
      pts.push(new THREE.Vector3(x, y, z));
      const label = makeLabel(TASKS[i], { px: 52, sx: 2.9, sy: 0.78 });
      // Drei feste Zeilen unterhalb der Knoten: verhindert Überlappung der
      // 10 langen Task-Namen und der Kugeln.
      label.position.set(x, -1.2 - (i % 3) * 0.8, 1.2);
      g.add(label);
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: COLORS.accent, transparent: true, opacity: 0.65 }));
    g.add(line);
    const label = makeLabel(L.subagents || '10 Sub-Agenten', { sx: 4.8, sy: 1.05 });
    label.position.set(0, 4.2, 0);
    g.add(label);
    return { group: g, update: (t, local, active) => {
      const p = active ? (local * 2.1) % TASKS.length : 0;
      nodes.forEach((m, i) => {
        const d = Math.abs(i - p);
        const glow = Math.max(0, 1 - d);
        m.scale.setScalar(1 + 0.3 * glow);
        m.material.emissiveIntensity = 0.12 + 0.55 * glow;
      });
      line.material.opacity = 0.5 + 0.2 * Math.sin(t * 1.1);
    } };
  }

  /* 4) Die Werkzeuge: MCP-Konnektoren als Werkzeug-Pods um einen Hub. */
  function buildTools() {
    const g = new THREE.Group();
    const L = window.__KMHR_LABELS__ || {};
    const tools = ['filesystem', 'pdf-reader', 'Recht', 'E-Mail',
                   'Meeting', 'Sprachtest', 'Benchmark', 'Gehalt'];
    const hub = new THREE.Mesh(new THREE.OctahedronGeometry(0.9, 0),
      new THREE.MeshStandardMaterial({
        color: COLORS.accent, roughness: 0.3, metalness: 0.45,
        emissive: COLORS.accent, emissiveIntensity: 0.18 }));
    hub.position.set(0, 0.4, 0);
    g.add(hub);
    const pods = [];
    const linePts = [];
    tools.forEach((name, i) => {
      const a = (i / tools.length) * Math.PI * 2 - Math.PI / 2;
      const x = Math.cos(a) * 5.0;
      const y = Math.sin(a) * 2.9 + 0.4;
      const geo = i % 3 === 0 ? new THREE.BoxGeometry(0.85, 0.85, 0.85)
                : i % 3 === 1 ? new THREE.CylinderGeometry(0.45, 0.45, 0.8, 16)
                : new THREE.SphereGeometry(0.5, 18, 18);
      const pod = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
        color: i % 2 ? COLORS.primaryLight : COLORS.primary,
        roughness: 0.35, metalness: 0.3,
        emissive: i % 2 ? COLORS.primaryLight : COLORS.primary,
        emissiveIntensity: 0.12 }));
      pod.position.set(x, y, 0);
      g.add(pod);
      pods.push({ m: pod, y0: y, phase: i * 0.7 });
      linePts.push(new THREE.Vector3(0, 0.4, 0), new THREE.Vector3(x, y, 0));
      const lab = makeLabel(name, { px: 56, sx: 3.0, sy: 0.8 });
      lab.position.set(Math.cos(a) * 6.15, Math.sin(a) * 3.5 + 0.4, 0);
      g.add(lab);
    });
    const lines = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(linePts),
      new THREE.LineBasicMaterial({ color: COLORS.sky, transparent: true, opacity: 0.42 }));
    g.add(lines);
    const label = makeLabel(L.tools || 'MCP-Werkzeuge', { sx: 4.6, sy: 1.05 });
    label.position.set(0, 5.0, 0);
    g.add(label);
    return { group: g, update: (t) => {
      hub.rotation.y = t * 0.5; hub.rotation.x = t * 0.2;
      pods.forEach((p, i) => {
        p.m.rotation.y = t * 0.6 + i;
        p.m.position.y = p.y0 + Math.sin(t * 1.4 + p.phase) * 0.12;
        p.m.scale.setScalar(1 + 0.08 * Math.sin(t * 2.2 + p.phase));
      });
    } };
  }

  /* 5) Das Ergebnis: Score-Karte mit sieben Kategorien, Häkchen und
     dem menschlichen Entscheid als Fußzeile. */
  function buildResult() {
    const g = new THREE.Group();
    const L = window.__KMHR_LABELS__ || {};
    const card = new THREE.Mesh(new THREE.BoxGeometry(15.5, 7.2, 0.35),
      new THREE.MeshBasicMaterial({ color: 0xFFFFFF }));
    card.position.set(0, 0.0, -0.45);
    g.add(card);
    const bars = [];
    const maxV = 30;
    KATEGORIEN.forEach((kat, i) => {
      const h = 0.8 + (kat[1] / maxV) * 2.8;
      const bar = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1, 1.1),
        new THREE.MeshStandardMaterial({
          color: i % 2 ? COLORS.primary : COLORS.primaryLight,
          roughness: 0.4, metalness: 0.15 }));
      const x = -6.0 + i * 2.0;
      bar.position.set(x, 0, 0);
      bar.scale.y = 0.001;
      g.add(bar);
      bars.push({ mesh: bar, h: h });
      const cap = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.15, 1.25),
        new THREE.MeshStandardMaterial({ color: COLORS.accent, roughness: 0.3, metalness: 0.35 }));
      cap.position.set(x, 0, 0);
      cap.scale.y = 0.001;
      g.add(cap);
      bars[i].cap = cap;
      const label = makeLabel(kat[0], { px: 54, sx: 2.15, sy: 0.74 });
      label.position.set(x, -1.5, 0.2);
      g.add(label);
    });
    const check = makeLabel('✓', { px: 110, sx: 1.6, sy: 1.6,
      color: '#B45309', bg: 'rgba(245,158,11,0.18)', border: 'rgba(245,158,11,0.55)' });
    check.position.set(0, 4.5, 0.3);
    g.add(check);
    const head = makeLabel(L.result || 'Score 0–100',
      { color: '#B45309', border: 'rgba(245,158,11,0.5)', sx: 4.6, sy: 1.05 });
    head.position.set(0, 5.7, 0.3);
    g.add(head);
    const foot = makeLabel(L.result_foot || 'Mensch entscheidet · VDO.Ninja · Onboarding',
      { px: 46, sx: 7.2, sy: 0.85 });
    foot.position.set(0, -2.9, 0.3);
    g.add(foot);
    return { group: g, update: (t, local, active) => {
      bars.forEach((b, i) => {
        const grow = active ? smooth(local * 1.3 - i * 0.11) : 1;
        const s = Math.max(0.001, grow);
        b.mesh.scale.y = b.h * s;
        b.mesh.position.y = (b.h * s) / 2;
        b.cap.scale.y = s;
        b.cap.position.y = b.h * s + 0.12;
      });
      check.scale.setScalar(1 + Math.sin(t * 2.2) * 0.06);
      g.rotation.y = Math.sin(t * 0.22) * 0.06;
    } };
  }

  /* ── Szene + Timeline ──────────────────────────────────────────── */
  function startScene(host) {
    const canvasHost = host.querySelector('.kmhr-canvas');
    const width = canvasHost.clientWidth || 900;
    const height = canvasHost.clientHeight || 480;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true,
                                              preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    canvasHost.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(COLORS.bg);
    // Straffe Nebelgrenze: aktive Station (13 Einheiten vor der Kamera) bleibt
    // klar, die nächste Station (43 Einheiten) verschwindet im Hintergrund.
    scene.fog = new THREE.Fog(COLORS.bg, 18, 52);

    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 400);
    camera.position.set(0, 2.1, 13);

    scene.add(new THREE.AmbientLight(0xFFFFFF, 0.9));
    const sun = new THREE.DirectionalLight(0xFFFFFF, 1.15);
    sun.position.set(6, 12, 10);
    scene.add(sun);
    const warm = new THREE.DirectionalLight(COLORS.accent, 0.35);
    warm.position.set(-8, 4, -6);
    scene.add(warm);

    const builders = [buildBrain, buildLoop, buildSubAgents, buildTools, buildResult];
    const stations = builders.map((build, i) => {
      const st = build();
      st.group.position.z = -SPACING * i;
      scene.add(st.group);
      return st;
    });

    const onResize = () => {
      const w = canvasHost.clientWidth || 900;
      const h = canvasHost.clientHeight || 480;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    if (window.ResizeObserver) new ResizeObserver(onResize).observe(canvasHost);
    window.addEventListener('resize', onResize);

    const reduceQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    S.reduce = !!(reduceQuery && reduceQuery.matches);
    const pauseEl = document.getElementById('kmhr-pause');
    if (pauseEl && S.reduce) {
      pauseEl.disabled = true;
      pauseEl.title = 'Statisch (Reduced Motion)';
      pauseEl.setAttribute('aria-label', 'Statisch (Reduced Motion)');
    }

    function cameraZ(t) {
      for (let i = 0; i < CH.length; i++) {
        const c = CH[i];
        const next = CH[i + 1];
        if (t <= c.t1) return -SPACING * c.zi;
        if (next && t < next.t0) {
          const f = smooth((t - c.t1) / (next.t0 - c.t1));
          return -SPACING * lerp(c.zi, next.zi, f);
        }
        if (!next) return -SPACING * c.zi;
      }
      return 0;
    }

    function activeIndex(t) {
      let idx = 0;
      for (let i = 0; i < CH.length; i++) if (t >= CH[i].t0) idx = i;
      return idx;
    }

    S.startTime = performance.now();

    /* Verstrichene Zeit im aktuellen Durchlauf; läuft über TOTAL hinaus, beginnt
       die Animation automatisch von vorn (Loop) – kein Stehenbleiben am Ende. */
    function elapsed(now) {
      if (S.reduce) return CH[S.staticIdx].t0 + 0.2;
      let el = (now - S.startTime) / 1000;
      if (el >= TOTAL) {
        const n = Math.floor(el / TOTAL);
        S.startTime += n * TOTAL * 1000;
        S.loops += n;
        el = (now - S.startTime) / 1000;
      }
      return Math.max(0, el);
    }

    // Test-/Debug-Hook (E2E + Diagnose,02.10.2026): erlaubt deterministisches
    // Ansprechen der Timeline und Abfrage des Szenen-Zustands.
    window.__kmhr = {
      seek: (sec) => { S.startTime = performance.now() - sec * 1000; },
      state: () => {
        // Pause einfrieren: sonst meldet der Debug-Hook eine laufende Zeit,
        // obwohl frame() bereits vor der Aktualisierung zurückkehrt.
        const now = S.pausedAt !== null ? S.pausedAt : performance.now();
        const t = S.reduce ? CH[S.staticIdx].t0 + 0.2 : (now - S.startTime) / 1000;
        return { t: t, camZ: camera.position.z, idx: activeIndex(Math.min(t, TOTAL)),
                 reduce: S.reduce, frames: S.frames, loops: S.loops, total: TOTAL,
                 count: S.countEl ? S.countEl.textContent : null,
                 stationZ: stations.map((st) => st.group.position.z) };
      },
    };

    function frame(now) {
      requestAnimationFrame(frame);
      if (S.pausedAt !== null) return;
      S.frames++;
      const t = elapsed(now);
      const idx = activeIndex(t);
      const ch = CH[idx];
      const local = Math.max(0, t - ch.t0);
      setCaption(idx);
      if (S.fillEl) S.fillEl.style.width = Math.min(100, (t / TOTAL) * 100) + '%';
      /* Countdown 30 → 0 (gerundet; im Reduced-Motion-Modus statisch „30“) */
      if (S.countEl) S.countEl.textContent = S.reduce ? String(TOTAL) : String(Math.max(0, Math.round(TOTAL - t)));
      /* Sanfter Weiß-Übergang am Schleifenende/-anfang statt hartem Sprung */
      if (S.fadeEl) {
        S.fadeEl.style.opacity = S.reduce ? 0
          : Math.max(smooth((t - (TOTAL - 0.7)) / 0.7), 1 - smooth(t / 0.7));
      }
      /* Login-Button im letzten Kapitel einblenden (im Statik-Modus immer) */
      if (S.endEl) S.endEl.classList.toggle('kmhr-end-show',
        S.reduce ? idx === CH.length - 1 : (t >= CH[CH.length - 1].t0 + 0.8 && t < TOTAL - 0.7));
      const bob = S.reduce ? 0 : 1;
      // +13: Kamera steht 13 Einheiten VOR der Stationsmitte und blickt auf
      // deren Zentrum (lookAt unten: camera.position.z - 13 = Stations-z).
      camera.position.z = cameraZ(t) + 13;
      camera.position.x = Math.sin(t * 0.32) * 1.05 * bob;
      camera.position.y = 2.1 + Math.sin(t * 0.47) * 0.32 * bob;
      camera.lookAt(Math.sin(t * 0.18) * 0.7 * bob, 1.9, camera.position.z - 13);
      stations.forEach((st, i) => st.update(t, local, i === idx));
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);

    /* Automatische Pause (Tab verdeckt ODER Animation außerhalb des Viewports).
       Manuelle Pause (Button) bleibt unberührt: S.autoPaused markiert nur die eigene Pause. */
    const syncPause = () => {
      if (document.hidden || S.offscreen) {
        if (S.pausedAt === null) { S.pausedAt = performance.now(); S.autoPaused = true; }
      } else if (S.autoPaused) {
        if (S.pausedAt !== null) S.startTime += performance.now() - S.pausedAt;
        S.pausedAt = null;
        S.autoPaused = false;
      }
    };
    document.addEventListener('visibilitychange', syncPause);
    if (window.IntersectionObserver) {
      new IntersectionObserver((entries) => {
        S.offscreen = !entries[0].isIntersecting;
        syncPause();
      }).observe(host);
    }
  }

  whenHostReady((host) => {
    buildUi(host);
    try {
      startScene(host);
    } catch (err) {
      console.error('[kmhr-landing] Three.js-Szene nicht verfügbar:', err);
      host.classList.add('kmhr-fallback');
      setCaption(0);
    }
    setCaption(0);
  });
})();
</script>
"""


# Kapiteltexte der Animation (Phase 2b 02.10.2026). Reihenfolge = JS-`CH`-Array;
# die übersetzten Texte werden als window.__KMHR_CH__ ins JS injiziert.
_CHAPTERS = [
    ("Kapitel 1", "Das Gehirn",
     "Der Orchestrator plant jede Aufgabe und behält den Überblick."),
    ("Kapitel 2", "Die Loop",
     "Der Runner fragt alle 60 Sekunden die Queue ab – bis zu drei Versuche pro Task."),
    ("Kapitel 3", "Die Sub-Agenten",
     "Zehn spezialisierte Agenten arbeiten die Bewerbung Schritt für Schritt ab."),
    ("Kapitel 4", "Die Werkzeuge",
     "MCP-Connectoren verbinden PDF, Recht, Mail, Meeting und Sprachtests."),
    ("Kapitel 5", "Das Ergebnis",
     "Score, Einladung per VDO.Ninja und Onboarding – der Mensch entscheidet."),
]

# 3D-Labels der Animation (Phase 2b). Werden als window.__KMHR_LABELS__ injiziert.
_LABELS = {
    "brain": "Orchestrator",
    "loop": "60-s-Loop",
    "subagents": "10 Sub-Agenten",
    "tools": "MCP-Werkzeuge",
    "result": "Score 0–100",
    "result_foot": "Mensch entscheidet · VDO.Ninja · Onboarding",
}

# Aufklappbarer Bereich: EINE kurze Zeile pro Schritt (Text) + Quellen separat.
_STEP_LINES = [
    "Das Gehirn – der Orchestrator plant und verteilt die Aufgaben.",
    "Die Loop – der Runner holt alle 60 Sekunden neue Tasks aus der Queue.",
    "Die Sub-Agenten – zehn spezialisierte Schritte von Extraktion bis Benachrichtigung.",
    "Die Werkzeuge – MCP-Connectoren für PDF, Recht, Mail, Meeting und Sprachtests.",
    "Das Ergebnis – Score, Einladung per VDO.Ninja und Onboarding; der Mensch entscheidet.",
]

# Häufige Fragen (P1.2, Bipperz-Muster 02.10.2026). Antworten aus dem Projekt
# (keine Erfindungen); eine Preis-Frage ist bewusst NICHT enthalten (kein Pricing
# festgelegt — Lab-Prinzip: keine erfundenen Werte).
_FAQ = [
    ("Was ist der KM-HR-Agent?",
     "Eine KI-gestützte HR-Plattform, die den Bewerbungsprozess zwischen Nordafrika und "
     "Deutschland, Frankreich und der Schweiz automatisiert."),
    ("Welche Sprachniveaus werden geprüft?",
     "Deutsch, Englisch und Französisch – CEFR A1 bis C1, direkt im Portal per Sprachtest."),
    ("Wie läuft die Visum-Begleitung?",
     "Der Agent prüft den Visum-Bedarf und liefert nach Bestätigung die Schritte "
     "(Was / Wie / Wo) inklusive der zuständigen Behörde."),
    ("Wie werden meine Daten geschützt?",
     "DSGVO-konform: Bewerbungsdaten werden 183 Tage nach Abschluss des Verfahrens "
     "gelöscht (Art. 17 DSGVO); Kontaktdaten erst nach der Einladung."),
]

# Vorteil-Karten „Warum KM-HR-Agent?" (Bipperz-Muster „Why choose …?", 02.10.2026).
# Jede Zahl ist im Projekt belegt und wird per Test gegen den Code geprüft
# (tests/test_landing_page.py::test_vorteile_zahlen_gegen_code).
_VORTEILE = [
    ("smart_toy", "10 Agent-Aufgaben",
     "Vom Bestätigungs-Mail bis zur Benachrichtigung – alles läuft automatisch."),
    ("compare_arrows", "7 Matching-Kategorien",
     "Kern, Erfahrung, Bildung, Standort, Branche, Soft Skills, Sprache → Score 0–100."),
    ("translate", "Sprachtest CEFR A1–C1",
     "Deutsch, Englisch, Französisch – direkt im Portal, mit Zertifikatsniveau."),
    ("videocam", "Video-Pre-Screen",
     "Gespräch per VDO.Ninja – mit Einwilligungs-Regel, ohne Aufnahme."),
    ("verified_user", "DSGVO-konform",
     "Bewerbungsdaten werden 183 Tage nach Abschluss gelöscht (Art. 17 DSGVO)."),
    ("groups", "3 Rollen",
     "Kandidat, Arbeitgeber, Admin – getrennte Zugänge und Rechte."),
]

# Die Labor-Quellen (Codemarke + Messdatum) stehen NICHT mehr im Besucher-UI,
# sondern in ergebnisse/entscheidungen.md (Lab-Praxis: Nachweis im Projekt, nicht
# auf der öffentlichen Seite). Die Zahlen selbst werden per Test gegen den Code
# geprüft (tests/test_landing_page.py::test_zahlen_gegen_quellcode_gezaehlt).


def _session() -> dict:
    from nicegui import app as _app
    return _app.storage.user


def create() -> None:
    """Register the landing page at „/" (vor dem Login, Nutzerentscheidung A 02.10.2026)."""

    @ui.page("/")
    def landing_page():
        # Eingeloggte Nutzer werden wie bisher umgeleitet (Verhalten aus
        # webui/main.py „Index (redirect)", Codemarke, Stand 02.10.2026).
        role = logic.current_role(_session())
        target = {"admin": "/admin", "employer": "/employer", "candidate": "/candidate"}.get(role)
        if target:
            ui.navigate.to(target)
            return

        inject_css()
        # Phase 2b: übersetzte Kapiteltexte VOR dem Animations-Modul setzen.
        _ch = [{"kicker": _(k), "title": _(t), "text": _(x)} for k, t, x in _CHAPTERS]
        _lb = {k: _(v) for k, v in _LABELS.items()}
        ui.add_head_html("<script>window.__KMHR_CH__="
                         + json.dumps(_ch, ensure_ascii=False)
                         + ";window.__KMHR_LABELS__="
                         + json.dumps(_lb, ensure_ascii=False) + ";</script>")
        ui.add_head_html(
            _HEAD_HTML
            .replace("Nochmal ansehen", _("Nochmal ansehen"))
            .replace(">Zum Login &rarr;", ">" + _("Zum Login") + " &rarr;")
        )
        apply_direction()  # <html lang> + dir (RTL bei Arabisch)

        with ui.column().classes("kmhr-wrap w-full"):
            # ── Kopfzeile ───────────────────────────────────────────
            with ui.row().classes("kmhr-top w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("smart_toy", size="md").classes("text-blue-800")
                    ui.label("KM-HR-Agent").classes("kmhr-brand")
                with ui.row().classes("items-center gap-3"):
                    language_switcher()
                    ui.button(_("Registrieren"), on_click=lambda: ui.navigate.to("/login")) \
                        .classes(C.BTN_SECONDARY + " kmhr-m-hide")
                    ui.button(_("Zum Login"), on_click=lambda: ui.navigate.to("/login")) \
                        .classes(C.BTN_PRIMARY + " kmhr-m-hide")

            # ── Hero (Schritt 1: Hauptaufgabe) ──────────────────────
            with ui.column().classes("kmhr-hero w-full"):
                ui.label(_("KI-gestützte HR-Plattform")).classes("kmhr-kicker")
                ui.html('<h1 class="kmhr-h1">' + _("Recruiting zwischen") + ' '
                        '<span class="kmhr-gold">' + _("Nordafrika") + '</span> '
                        + _("und") + ' '
                        '<span class="kmhr-gold">DE / FR / CH</span>.</h1>')
                ui.label(
                    _("Von der Bewerbung bis zum Onboarding.")
                ).classes("kmhr-sub")
                with ui.row().classes("items-center gap-3"):
                    ui.button(_("Zum Login"), on_click=lambda: ui.navigate.to("/login")) \
                        .classes(C.BTN_PRIMARY)
                    ui.button(_("▶ 30-Sekunden-Tour"),
                              on_click=lambda: ui.run_javascript(
                                  "document.getElementById('kmhr-ablauf').scrollIntoView({behavior:'smooth'})")
                              ).classes(C.BTN_SECONDARY + " kmhr-m-hide")

            # ── Animation (Three.js, lokal) — unsere Stärke, direkt unter dem Hero ──
            # Schritt B (Nutzerentscheidung 02.10.2026): die 30-s-Animation ist das
            # Alleinstellungsmerkmal → früh sichtbar. Überschrift/Dauer: TOTAL = 30.0.
            ui.html('<div id="kmhr-ablauf"></div>')
            ui.label(_("Das Agenten-Prinzip – in 30 Sekunden")).classes("kmhr-h2")
            # w-full am ui.html-Wrapper ist NOTWENDIG: NiceGUI-Spalten haben
            # align-items:flex-start, das anonyme Wrapper-Element schrumpft sonst
            # auf 0 px (Bug-Fund 02.10.2026, Messung: Host war 2 px breit).
            ui.html('<div id="kmhr-anim-host" class="kmhr-anim-host"></div>').classes("w-full")

            # ── Zielgruppen (P1.1, Bipperz-Muster 02.10.2026) ──────────
            # Zwei Zielgruppen mit eigenem CTA (ersetzt die frühere „Für wen"-Karte).
            with ui.column().classes("kmhr-section w-full"):
                with ui.row().classes("kmhr-grid2 w-full"):
                    ziele = [
                        ("business", "Für Arbeitgeber",
                         "Qualifizierte, visumbereite Fachkräfte – automatisch gematcht, "
                         "geprüft und gerankt.",
                         "Arbeitgeber-Registrieren"),
                        ("person", "Für Kandidaten",
                         "Ihr Weg nach Deutschland: Profil, Matching, Sprachtest, Visum "
                         "und Onboarding – begleitet.",
                         "Kandidat-Registrieren"),
                    ]
                    for icon, titel, text, cta in ziele:
                        with ui.card().classes("kmhr-card"):
                            ui.icon(icon, size="md").classes("kmhr-ico text-blue-700")
                            ui.label(_(titel)).style(
                                "margin:0 0 8px;font-size:1.02rem;font-weight:700;color:#1E3A8A")
                            ui.label(_(text)).style(
                                "margin:0 0 14px;color:#64748B;line-height:1.6;font-size:0.95rem")
                            ui.button(_(cta), on_click=lambda: ui.navigate.to("/login")) \
                                .classes(C.BTN_PRIMARY)

            # ── Warum KM-HR-Agent? (Vorteile, Bipperz-Muster 02.10.2026) ─
            # Alle Zahlen sind im Projekt belegt (Test prüft gegen den Code).
            # (02.10.2026, Nutzerbefehl: die früheren „Aufgabe"/„Nutzen"-Karten entfernt.)
            with ui.column().classes("kmhr-section w-full"):
                ui.label(_("Warum KM-HR-Agent?")).classes("kmhr-h2")
                with ui.row().classes("kmhr-grid3 w-full"):
                    for icon, titel, text in _VORTEILE:
                        with ui.card().classes("kmhr-card"):
                            ui.icon(icon, size="md").classes("kmhr-ico text-blue-700")
                            ui.label(_(titel)).style(
                                "margin:0 0 8px;font-size:1.02rem;font-weight:700;color:#1E3A8A")
                            ui.label(_(text)).style("margin:0;color:#64748B;line-height:1.6;font-size:0.95rem")

            # ── So funktioniert's (aufklappbar, Standard: zu) ────────
            with ui.expansion(_("So funktioniert's"), icon="menu_book").classes("kmhr-details"):
                with ui.column().classes("w-full gap-1").style("padding:4px 18px 16px"):
                    ui.html("<ol class='kmhr-steps'>"
                            + "".join(f"<li>{_(t)}</li>" for t in _STEP_LINES) + "</ol>")

            # ── Häufige Fragen (P1.2, Bipperz-Muster 02.10.2026) ─────
            with ui.column().classes("kmhr-section w-full"):
                ui.label(_("Häufige Fragen")).classes("kmhr-h2")
                for _frage, _antwort in _FAQ:
                    with ui.expansion(_(_frage), icon="help_outline").classes("kmhr-details"):
                        ui.label(_(_antwort)).style(
                            "padding:4px 18px 16px;color:#64748B;line-height:1.7;font-size:0.95rem")

            # ── Abschluss-CTA (P1.4, Bipperz-Muster 02.10.2026) ──────
            with ui.column().classes("kmhr-section w-full items-start"):
                ui.label(_("Bereit, den Bewerbungsprozess zu automatisieren?")).classes("kmhr-h2")
                ui.label(_("Kostenlos registrieren – als Kandidat oder Arbeitgeber.")) \
                    .classes("kmhr-sub")
                with ui.row().classes("items-center gap-3"):
                    ui.button(_("Jetzt registrieren"), on_click=lambda: ui.navigate.to("/login")) \
                        .classes(C.BTN_PRIMARY)
                    ui.button(_("Zum Login"), on_click=lambda: ui.navigate.to("/login")) \
                        .classes(C.BTN_SECONDARY)

            # ── Footer (P1.3, Bipperz-Muster 02.10.2026) ─────────────
            with ui.column().classes("kmhr-footer w-full"):
                with ui.row().classes("items-center gap-5 flex-wrap"):
                    ui.link(_("Impressum"), "/impressum").classes("kmhr-foot-link")
                    ui.link(_("Datenschutz"), "/datenschutz").classes("kmhr-foot-link")
                    ui.link(_("AGB"), "/agb").classes("kmhr-foot-link")
                    ui.link(_("Kontakt"), "/kontakt").classes("kmhr-foot-link")
