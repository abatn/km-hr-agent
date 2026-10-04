#!/usr/bin/env python3
"""Salary-Connector mit BambooHR-Formel."""

from fastmcp import FastMCP

mcp = FastMCP("salary-data")

@mcp.tool()
def calculate_salary_band(market_data: list, role: str) -> dict:
    """Berechnet Gehaltsband nach BambooHR-Formel.
    
    Formel (original):
    - Min = 25th Percentile
    - Mid = 50th Percentile (Median)
    - Max = 75th Percentile
    """
    sorted_data = sorted(market_data)
    n = len(sorted_data)
    
    min_idx = int(n * 0.25)
    mid_idx = int(n * 0.50)
    max_idx = int(n * 0.75)
    
    return {
        "role": role,
        "band": {
            "min": sorted_data[min_idx],
            "mid": sorted_data[mid_idx],
            "max": sorted_data[max_idx]
        },
        "percentiles": {
            "min": "25th",
            "mid": "50th (Median)",
            "max": "75th"
        },
        "quelle": "BambooHR Formel (verifiziert 15.09.2026)",
        "url": "https://www.bamboohr.com/blog/salary-bands-explained"
    }

@mcp.tool()
def calculate_salary_position(salary: int, band: dict) -> dict:
    """Berechnet Position im Gehaltsband.
    
    Platzierungs-Regeln (original):
    - Entry-level: 25-40%
    - Mid-level: 40-60%
    - Senior: 60-80%
    - Specialist: 80-100%
    """
    min_sal = band["min"]
    max_sal = band["max"]
    
    if max_sal == min_sal:
        position_percent = 50
    else:
        position_percent = ((salary - min_sal) / (max_sal - min_sal)) * 100
    
    if position_percent <= 40:
        level = "Entry-level"
    elif position_percent <= 60:
        level = "Mid-level"
    elif position_percent <= 80:
        level = "Senior"
    else:
        level = "Specialist"
    
    return {
        "salary": salary,
        "position_percent": round(position_percent, 2),
        "level": level,
        "band": band,
        "quelle": "BambooHR Platzierungs-Regeln (verifiziert 15.09.2026)"
    }

@mcp.tool()
def calculate_salary_tolerance(midpoint: int, tolerance_percent: float = 0.15) -> dict:
    """Berechnet Gehalts-Toleranz um den Midpoint."""
    return {
        "midpoint": midpoint,
        "tolerance_min": midpoint * (1 - tolerance_percent),
        "tolerance_max": midpoint * (1 + tolerance_percent),
        "tolerance_percent": tolerance_percent,
        "quelle": "BambooHR (verifiziert 15.09.2026)"
    }

if __name__ == "__main__":
    mcp.run()
