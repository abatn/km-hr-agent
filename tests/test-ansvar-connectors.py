#!/usr/bin/env python3
"""Test-Ansvar-Law-Connectors: 3 Suchanfragen für DE/FR/CH."""

import subprocess
import json
import sys
import time

GATEWAY = "https://gateway.ansvar.eu/mcp"
MCP_CMD = ["npx", "-y", "mcp-remote@0.1.38", GATEWAY]

TESTS = [
    {
        "name": "TEST 1 - DEUTSCHLAND",
        "connector": "ansvar-german-law",
        "query": "ausländische Mitarbeiter Anforderung arbeitsvisum",
        "jurisdictions": ["DE"],
        "expectation": "Treffer zum Aufenthaltsgesetz §18a (Fachkräfte)",
    },
    {
        "name": "TEST 2 - FRANKREICH",
        "connector": "ansvar-french-law",
        "query": "CESEDA titre séjour",
        "jurisdictions": ["FR"],
        "expectation": "Treffer zum französischen Aufenthaltsrecht",
    },
    {
        "name": "TEST 3 - SCHWEIZ",
        "connector": "ansvar-swiss-law",
        "query": "AuG Art 10",
        "jurisdictions": ["CH"],
        "expectation": "Treffer zum schweizerischen Ausländergesetz",
    },
]


def send_rpc(proc, method, params=None):
    """Send a JSON-RPC request and return the response."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        request["params"] = params
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    start = time.time()
    while time.time() - start < 30:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            resp = json.loads(line.strip())
            if resp.get("id") == 1:
                return resp
        except json.JSONDecodeError:
            continue
    return None


def test_connector(test):
    """Run a single connector test."""
    print(f"\n{'='*60}")
    print(f"{test['name']}")
    print(f"{'='*60}")
    print(f"Connector: {test['connector']}")
    print(f"Query:     {test['query']}")
    print(f"Expected:  {test['expectation']}")

    try:
        proc = subprocess.Popen(
            MCP_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Initialize
        init_resp = send_rpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-agent", "version": "1.0.0"}
        })
        if not init_resp or "error" in init_resp:
            print(f"  ERROR: Init failed: {init_resp}")
            proc.terminate()
            return False

        # Send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        # Call search tool
        search_resp = send_rpc(proc, "tools/call", {
            "name": "search",
            "arguments": {
                "query": test["query"],
                "jurisdictions": test["jurisdictions"],
            }
        })

        proc.terminate()

        if not search_resp:
            print(f"  ERROR: No response from search")
            return False

        if "error" in search_resp:
            print(f"  ERROR: {search_resp['error']}")
            return False

        # Parse results - the content is a list with one text item containing JSON
        result = search_resp.get("result", {})
        content = result.get("content", [])
        
        hits = []
        meta = {}
        raw_json = None
        
        print(f"\n  DEBUG: content type={type(content)}, len={len(content)}")
        
        for i, item in enumerate(content):
            print(f"  DEBUG: item[{i}] type={item.get('type') if isinstance(item, dict) else type(item)}")
            if isinstance(item, dict) and item.get("type") == "text":
                text_val = item.get("text", "")
                print(f"  DEBUG: text length={len(text_val)}")
                print(f"  DEBUG: text preview={text_val[:200]}")
                try:
                    data = json.loads(text_val)
                    raw_json = data
                    print(f"  DEBUG: parsed type={type(data)}")
                    if isinstance(data, dict):
                        hits = data.get("results", [])
                        meta = data.get("meta", {})
                        print(f"  DEBUG: results count={len(hits)}")
                    elif isinstance(data, list):
                        hits = data
                        print(f"  DEBUG: list count={len(hits)}")
                except json.JSONDecodeError as e:
                    print(f"  DEBUG: JSON parse error: {e}")

        print(f"\n  Treffer: {len(hits)}")
        
        # Show search metadata
        if meta:
            tier = meta.get("tier", "unknown")
            scope = meta.get("search_scope", {})
            searched = scope.get("searched", [])
            msg = meta.get("message", "")
            print(f"  Tier: {tier}")
            if searched:
                print(f"  Durchsucht: {', '.join(searched[:5])}{'...' if len(searched) > 5 else ''}")
            if msg:
                print(f"  Nachricht: {msg[:200]}")

        if hits:
            print(f"\n  Erste Quellen:")
            for i, hit in enumerate(hits[:3]):
                citation = hit.get("citation", {})
                source = citation.get("source_full_name", hit.get("text_source", "N/A"))
                article = citation.get("article", "N/A")
                url = citation.get("source_url", "N/A")
                jurisdiction = citation.get("jurisdiction", "N/A")
                text_preview = hit.get("text", "")[:100]
                print(f"    {i+1}. Gesetz: {source}")
                print(f"       Artikel: {article}")
                print(f"       URL: {url}")
                print(f"       Text: {text_preview}...")

            # Check if results match expectation
            all_text = json.dumps(hits).lower()
            key_terms = {
                "TEST 1 - DEUTSCHLAND": ["aufenthaltsgesetz", "aufenthg", "§18a", "fachkräfte", "arbeitsvisum", "§ 18a"],
                "TEST 2 - FRANKREICH": ["ceseda", "titre de séjour", "séjour", "étranger", "code de l'entrée"],
                "TEST 3 - SCHWEIZ": ["aug", "ausländergesetz", "art. 10", "bewilligung", "ausländer"],
            }
            terms = key_terms.get(test["name"], [])
            found = [t for t in terms if t in all_text]
            match_pct = len(found) / len(terms) * 100 if terms else 0
            print(f"\n  Erwartung: {test['expectation']}")
            print(f"  Gefundene Schlüsselbegriffe: {', '.join(found) if found else 'keine'}")
            print(f"  Übereinstimmung: {match_pct:.0f}%")
        else:
            print(f"\n  Keine Treffer gefunden")
            if raw_json:
                msg = raw_json.get("meta", {}).get("message", "")
                if msg:
                    print(f"  Grund: {msg[:400]}")

        return len(hits) > 0

    except Exception as e:
        print(f"  EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("TEST-PROMPT FÜR ANSAVAR-LAW-CONNECTOR")
    print("=" * 60)
    print("Test-Agent für KM-HR-Agent: ansvar-law MCP-Connector Tests")

    results = []
    for test in TESTS:
        ok = test_connector(test)
        results.append((test["name"], ok))

    # Summary table
    print(f"\n\n{'='*60}")
    print("ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    print(f"{'Test':<30} {'Status':<10}")
    print(f"{'-'*40}")
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{name:<30} {status:<10}")
    print(f"{'-'*40}")
    passed = sum(1 for _, ok in results if ok)
    print(f"Gesamt: {passed}/{len(results)} bestanden")


if __name__ == "__main__":
    main()
