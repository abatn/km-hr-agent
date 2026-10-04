#!/usr/bin/env python3
"""HR-Benchmark-Connector mit ZYTHR-Formel."""

from fastmcp import FastMCP

mcp = FastMCP("hr-benchmark")

@mcp.tool()
def calculate_weighted_score(scores: dict, weights: dict, max_score: int = 5) -> dict:
    """Berechnet den gewichteten Score nach ZYTHR-Formel.
    
    Formel (original): Weighted contribution = (score / max) × weight
    Quelle: zythr.com (verifiziert 15.09.2026)
    """
    details = {}
    total = 0
    
    for key in scores:
        if key in weights:
            contribution = (scores[key] / max_score) * weights[key] * 100
            details[key] = {
                "score": scores[key],
                "weight": weights[key],
                "contribution": round(contribution, 2)
            }
            total += contribution
    
    return {
        "total_score": round(total, 2),
        "details": details,
        "quelle": "ZYTHR Formel (verifiziert 15.09.2026)",
        "url": "https://zythr.com/resources/candidate-scoring-model-in-recruiting-what-it-is-and-how-to-build-one"
    }

@mcp.tool()
def get_score_category(score: int) -> dict:
    """Kategorisiert Score nach ZYTHR-Schwellen.
    
    Schwellen (original):
    - 80-100 = "Strong"
    - 60-79 = "Consider"
    - <60 = "Weak"
    """
    if score >= 80:
        category = "Strong"
    elif score >= 60:
        category = "Consider"
    else:
        category = "Weak"
    
    return {
        "score": score,
        "category": category,
        "quelle": "ZYTHR Schwellen (verifiziert 15.09.2026)"
    }

@mcp.tool()
def get_weight_ranges() -> dict:
    """Gibt die ZYTHR-Gewichtungsbereiche zurück."""
    return {
        "ranges": {
            "experience": {"min": 0.20, "max": 0.35},
            "core_skills": {"min": 0.30, "max": 0.50},
            "role_specific": {"min": 0.10, "max": 0.25},
            "behavioral": {"min": 0.10, "max": 0.20},
            "education": {"min": 0.00, "max": 0.10}
        },
        "quelle": "ZYTHR (verifiziert 15.09.2026)"
    }

if __name__ == "__main__":
    mcp.run()
