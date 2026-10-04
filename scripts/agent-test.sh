#!/bin/bash
# Agent-Test: KM-HR-Agent – Matching-Test

echo "=== Agent-Test: KM-HR-Agent ==="
echo ""
echo "Projekt: ~/mimo-agents/km-hr-agent"
echo ""
echo "Testdaten:"
echo "  Lebensläufe:"
echo "    - testdaten/lebenslauf-anna-schuster.txt"
echo "    - testdaten/lebenslauf-marc-weber.txt"
echo "    - testdaten/lebenslauf-lena-fischer.txt"
echo "  Stellenprofile:"
echo "    - testdaten/stellenprofil-cloud-devops-engineer.txt"
echo "    - testdaten/stellenprofil-it-projektmanager.txt"
echo ""
echo "Verwendete Connectors:"
echo "  1. Filesystem MCP (lokal, kein Auth)"
echo "  2. PDF-Connector (lokal, kein Auth) – für PDF-Lebensläufe"
echo "  3. Visuals-MCP (lokal) – für Visualisierung"
echo ""

# Prüfen ob opencode JSON gültig ist
echo "Prüfe opencode.json auf Gültigkeit..."
cat ~/.config/opencode/opencode.json | python3 -c "import sys,json; json.load(sys.stdin)" && echo "✅ opencode.json ist gültig" || echo "❌ opencode.json ist ungültig"

echo ""
echo "=== Starte Matching-Test ==="
echo "Bitte opencode starten und die folgenden Befehle ausführen:"
echo ""
cat << 'EOF'
1. Profil extrahieren:

"Extrahiere ein strukturiertes Profil aus ~/mimo-agents/km-hr-agent/testdaten/lebenslauf-anna-schuster.txt
und vergleiche es mit ~/mimo-agents/km-hr-agent/testdaten/stellenprofil-cloud-devops-engineer.txt.
Wende die Skills extract-profile, match-candidate und explain-match an.
Speichere das Ergebnis in ~/mimo-agents/km-hr-agent/ergebnisse/match-test-anna-devops.md"

2. Weitere Matches:

"Führe die gleiche Analyse durch für Marc Weber und Lena Fischer
gegenüber beiden Stellenprofilen.
Speichere die Ergebnisse in ~/mimo-agents/km-hr-agent/ergebnisse/"

3. Zusammenfassung:

"Erstelle eine Vergleichstabelle aller 6 Matches (3 Kandidaten x 2 Stellen)
und speichere sie in ~/mimo-agents/km-hr-agent/ergebnisse/vergleichsmatrix.md"
EOF
