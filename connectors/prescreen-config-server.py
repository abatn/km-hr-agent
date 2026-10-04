#!/usr/bin/env python3
"""Pre-Screen-Connector mit CareerPlug-Logik."""

from fastmcp import FastMCP

mcp = FastMCP("prescreen-config")

@mcp.tool()
def get_optimal_duration() -> dict:
    """Gibt optimale Pre-Screen-Dauer nach CareerPlug-Logik zurück.
    
    Quelle (original): "Keep the phone screen short – aim for 15 minutes 
    and no more than 30."
    """
    return {
        "min_minutes": 15,
        "optimal_minutes": 20,
        "max_minutes": 30,
        "quelle": "CareerPlug (verifiziert 15.09.2026)",
        "url": "https://www.careerplug.com/how-to-conduct-phone-screen-interview/"
    }

@mcp.tool()
def get_screening_questions() -> list:
    """Gibt die CareerPlug Screening-Fragen zurück."""
    return [
        {"id": 1, "frage": "This role pays $X annually. Does that fit your salary expectations?", "kategorie": "salary"},
        {"id": 2, "frage": "Do you have experience with X software?", "kategorie": "experience"},
        {"id": 3, "frage": "Do you have any years of experience in a similar role?", "kategorie": "experience"},
        {"id": 4, "frage": "Can you work weekends?", "kategorie": "availability"},
        {"id": 5, "frage": "Are you willing to relocate?", "kategorie": "availability"},
        {"id": 6, "frage": "What stood out to you about this position?", "kategorie": "motivation"},
        {"id": 7, "frage": "Tell me a little bit about your resume.", "kategorie": "resume"},
        {"id": 8, "frage": "Why did you leave (or why are you leaving) your last position?", "kategorie": "reason"},
        {"id": 9, "frage": "What date can you start?", "kategorie": "availability"},
        {"id": 10, "frage": "Do you have any questions about the role or our company?", "kategorie": "questions"}
    ]

@mcp.tool()
def get_screening_structure() -> dict:
    """Gibt die CareerPlug Screeningsstruktur zurück."""
    return {
        "structure": [
            {"step": 1, "name": "Salary check", "dauer_min": 2},
            {"step": 2, "name": "Software/Erfahrung", "dauer_min": 4},
            {"step": 3, "name": "Verfügbarkeit", "dauer_min": 3},
            {"step": 4, "name": "Motivation", "dauer_min": 3},
            {"step": 5, "name": "Resume-Check", "dauer_min": 4},
            {"step": 6, "name": "Kündigungsgrund", "dauer_min": 2},
            {"step": 7, "name": "Startdatum", "dauer_min": 1},
            {"step": 8, "name": "Kandidaten-Fragen", "dauer_min": 5}
        ],
        "total_minutes": 24,
        "quelle": "CareerPlug (verifiziert 15.09.2026)"
    }

if __name__ == "__main__":
    mcp.run()
