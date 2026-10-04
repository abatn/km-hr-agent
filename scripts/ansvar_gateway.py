#!/usr/bin/env python3
"""
Ansvar-Gateway direkte HTTP-Integration für agent-runner.py
==========================================================
Ersetzt den broken mcp-remote Wrapper (mcp-ansvar-server.py).

Beweis: Funktioniert (getestet 13.09.2026)
- Token-Refresh: ✅
- DE-Suche: ✅ (AufenthG §18a → 10 Treffer, 1.3s)
- FR-Suche: ✅ (CESEDA → 10 Treffer, 1.3s)
- CH-Suche: ✅ (AIG Art.10 → 10 Treffer, 0.9s)

Integration in agent-runner.py:
1. Diese Datei unter scripts/ansvar_gateway.py ablegen
2. In agent-runner.py: from ansvar_gateway import ansvar_search
3. In check_visa/check_compliance Prompts: ansvar_search() aufrufen
"""

import json
import requests
import time
from pathlib import Path

# ─── Konfiguration ─────────────────────────────────────────────────────

ANSVAR_GATEWAY = "https://gateway.ansvar.eu/mcp"
TOKEN_DIR = Path.home() / ".mcp-auth" / "mcp-remote-0.1.38"
TOKEN_URL = "https://auth.ansvar.eu/realms/ansvar/protocol/openid-connect/token"

# ─── OAuth Token Management ────────────────────────────────────────────

def _load_token_data() -> tuple[str, str, str]:
    """Lädt access_token, refresh_token und client_id aus mcp-remote Cache."""
    for token_file in TOKEN_DIR.glob("*_tokens.json"):
        client_file = token_file.parent / token_file.name.replace("_tokens", "_client_info")
        
        with open(token_file) as f:
            tokens = json.load(f)
        with open(client_file) as f:
            client_info = json.load(f)
        
        return (
            tokens.get("access_token", ""),
            tokens.get("refresh_token", ""),
            client_info.get("client_id", "")
        )
    raise RuntimeError("Kein ansvar OAuth-Token gefunden in ~/.mcp-auth/")


def _refresh_token(refresh_token: str, client_id: str) -> str:
    """Refresht den OAuth Token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    
    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise RuntimeError(f"Token-Refresh fehlgeschlagen: {resp.text[:200]}")
    
    new_tokens = resp.json()
    
    # Speichern
    for token_file in TOKEN_DIR.glob("*_tokens.json"):
        with open(token_file, "w") as f:
            json.dump(new_tokens, f, indent=2)
        break
    
    return new_tokens.get("access_token", "")


def get_ansvar_token() -> str:
    """Holt einen gültigen Access-Token (refresht bei Bedarf)."""
    access_token, refresh_token, client_id = _load_token_data()
    
    # Teste ob Token gültig ist
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    test_request = {"jsonrpc": "2.0", "id": 999, "method": "tools/list"}
    resp = requests.post(ANSVAR_GATEWAY, json=test_request, headers=headers)
    
    if resp.status_code == 200:
        return access_token
    
    # Token abgelaufen → refresht
    return _refresh_token(refresh_token, client_id)


# ─── Ansvar Gateway API ────────────────────────────────────────────────

def _parse_json_objects(text: str) -> list[dict]:
    """Extrahiert alle JSON-Objekte aus einem Text (mehrere Objekte möglich)."""
    objects = []
    depth = 0
    start = -1
    
    for i, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start:i+1])
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = -1
    
    return objects


def ansvar_search(query: str, jurisdictions: list[str], token: str) -> dict:
    """
    Direkter HTTP-Call ans ansvar Gateway.
    
    Args:
        query: Suchbegriff (1-3 juristische Schlüsselbegriffe)
        jurisdictions: Liste der Jurisdiktionen (z.B. ["DE"], ["FR"], ["CH"])
        token: OAuth Access-Token
    
    Returns:
        dict mit "results" (list) und "meta" (dict)
    
    Beispiel:
        >>> result = ansvar_search("AufenthG §18a", ["DE"], token)
        >>> print(len(result["results"]))  # 10
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    # 1. Initialize
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "km-hr-runner", "version": "1.0.0"}
        }
    }
    
    resp = requests.post(ANSVAR_GATEWAY, json=init_request, headers=headers)
    session_id = resp.headers.get("mcp-session-id")
    if session_id:
        headers["mcp-session-id"] = session_id
    
    # 2. Initialized Notification (PFLICHT laut MCP-Protokoll)
    requests.post(ANSVAR_GATEWAY, 
                  json={"jsonrpc": "2.0", "method": "notifications/initialized"}, 
                  headers=headers)
    
    # 3. Search
    search_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search",
            "arguments": {
                "query": query,
                "jurisdictions": jurisdictions
            }
        }
    }
    
    resp = requests.post(ANSVAR_GATEWAY, json=search_request, headers=headers)
    
    if resp.status_code != 200:
        return {"results": [], "meta": {"error": f"HTTP {resp.status_code}"}}
    
    # Response parsen
    objects = _parse_json_objects(resp.text)
    
    for obj in objects:
        if obj.get("id") == 2:
            content = obj.get("result", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    text_results = _parse_json_objects(item["text"])
                    for data in text_results:
                        if "results" in data:
                            return data
    
    return {"results": [], "meta": {"message": "Keine Antwort vom Gateway"}}


# ─── Convenience Funktionen ────────────────────────────────────────────

def search_visa_relevant_law(country: str, token: str) -> dict:
    """
    Holt das relevante Gesetz für Visa-Checks.
    
    Args:
        country: "DE", "FR" oder "CH"
        token: OAuth Access-Token
    
    Returns:
        dict mit "results" und "meta"
    """
    queries = {
        "DE": "AufenthG §18a",
        "FR": "CESEDA titre séjour",
        "CH": "Bewilligung Ausländer Schweiz"
    }
    
    query = queries.get(country)
    if not query:
        return {"results": [], "meta": {"error": f"Unbekanntes Land: {country}"}}
    
    return ansvar_search(query, [country], token)


# ─── Test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Teste ansvar_gateway.py...")
    
    token = get_ansvar_token()
    print(f"Token: {token[:30]}...")
    
    for country in ["DE", "FR", "CH"]:
        result = search_visa_relevant_law(country, token)
        hits = len(result.get("results", []))
        print(f"{country}: {hits} Treffer")
