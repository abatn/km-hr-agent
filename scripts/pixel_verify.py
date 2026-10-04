"""Pixel-Verifikation der 4 Login-Kontrast-Fails aus dem Audit.
Der Auditor komponiert nur background-COLORs; der Login-Hintergrund ist ein
background-image (Gradient-Mesh) — Ground Truth sind echte Pixels aus den
Screenshots (dort ist der Gradient real gerendert).
"""
from pathlib import Path

from PIL import Image

SHOTS = Path("/home/batnini/mimo-agents/km-hr-agent/ergebnisse/screenshots")

# Element-Positionen aus dem Audit (Login-Seite, Viewport 1440×900):
# - Titel "Willkommen zurueck" / Logo / Markenname sitzen im Karten-/Header-Bereich
# Probe-Punkte: Header-Logo (links oben), Karten-Titel (Mitte oben)
POINTS = {
    "logo+markenname (Header)": (90, 60),
    "karten-titel 'Willkommen'": (720, 300),
}


def luminance(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(fg, bg):
    l1, l2 = sorted([luminance(fg), luminance(bg)], reverse=True)
    return (l1 + 0.05) / (h2 := (l2 + 0.05)) if False else (l1 + 0.05) / (l2 + 0.05)


def pixel_bg(img, x, y, r=6):
    """Median-Hintergrund um (x,y) ohne helle Textpixel (hellste Pixel raus)."""
    px = img.load()
    region = [px[i, j][:3] for i in range(x - r, x + r) for j in range(y - r, y + r)]
    region.sort(key=lambda c: sum(c))
    return region[len(region) // 2]  # Median ≈ Hintergrund (Text ist Minderheit)


for shot in ["login-light.png", "login-dark.png"]:
    img = Image.open(SHOTS / shot).convert("RGB")
    print(f"── {shot} ({img.size[0]}×{img.size[1]}) ──")
    for label, (x, y) in POINTS.items():
        bg = pixel_bg(img, x, y)
        lum = luminance(bg)
        # fg: weißer Text (255) und weißer Gradient-Text → Kontrast gegen weiße Schrift
        rw = ratio((255, 255, 255), bg)
        # für Dark-Mode zusätzlich: Textfarbe dort ist die helle Gradient-Spitze (~#93C5FD hellblau)
        rb = ratio((147, 197, 253), bg)
        verdict_w = "OK" if rw >= 3.0 else "FAIL"
        verdict_b = "OK" if rb >= 3.0 else "FAIL"
        print(f"  {label:<28} bg-Pixel={bg} L={lum:.3f}  weiß={rw:.2f} [{verdict_w}]  hellblau={rb:.2f} [{verdict_b}]")
    print()
