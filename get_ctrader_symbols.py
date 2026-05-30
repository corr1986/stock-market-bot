#!/usr/bin/env python3
"""
Scarica tutti i simboli disponibili su cTrader FP Markets (account Demo).
Salva ctrader_symbols.json e ctrader_symbols.csv nella stessa cartella.

Prerequisiti:
    pip install ctrader-open-api requests python-dotenv

Setup:
    1. Vai su https://openapi.ctrader.com/ e registra un'app
    2. Copia Client ID e Client Secret nel file .env:
           CTRADER_CLIENT_ID=...
           CTRADER_CLIENT_SECRET=...
    3. python get_ctrader_symbols.py
       (si aprirà il browser per autorizzare l'app)
"""
import os
import json
import csv
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import Counter

import requests
from dotenv import load_dotenv
from twisted.internet import reactor
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetAccountListByAccessTokenRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
    ProtoOASymbolCategoryListReq,
    ProtoOASymbolCategoryListRes,
)

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"

_state = {
    "token": None,
    "account_id": None,
    "categories": {},
    "symbols": [],
}


# ── OAuth ─────────────────────────────────────────────────────────────────────

def get_access_token() -> str:
    code_holder = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                code_holder["code"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Autorizzazione completata. Puoi chiudere questa finestra.")

        def log_message(self, *args):
            pass

    server = HTTPServer(("", 8080), _Handler)
    Thread(target=server.handle_request, daemon=True).start()

    auth_url = "https://connect.ctrader.com/oauth/authorize?" + urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "accounts",
    })
    print("Apertura browser per autorizzazione OAuth...")
    print(f"(Se non si apre, copia questo URL nel browser):\n{auth_url}\n")
    webbrowser.open(auth_url)
    print("In attesa di risposta (max 2 minuti)...")

    server.handle_request()

    if "code" not in code_holder:
        raise RuntimeError("Nessun codice OAuth ricevuto. Riprova.")

    r = requests.post("https://connect.ctrader.com/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code_holder["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


# ── Callbacks cTrader API ─────────────────────────────────────────────────────

def _on_connected(client):
    print("Connesso al server cTrader Demo.")
    req = ProtoOAApplicationAuthReq()
    req.clientId = CLIENT_ID
    req.clientSecret = CLIENT_SECRET
    client.send(req)


def _on_disconnected(client, reason):
    print(f"Disconnesso: {reason}")
    if reactor.running:
        reactor.stop()


def _on_message(client, message):
    ptype = message.payloadType

    if ptype == ProtoOAApplicationAuthRes().payloadType:
        print("App autenticata.")
        req = ProtoOAGetAccountListByAccessTokenReq()
        req.accessToken = _state["token"]
        client.send(req)

    elif ptype == ProtoOAGetAccountListByAccessTokenRes().payloadType:
        res = Protobuf.extract(message)
        demo_accounts = [a for a in res.ctidTraderAccount if not a.isLive]
        if not demo_accounts:
            print("ERRORE: Nessun account demo trovato per questo token.")
            reactor.stop()
            return
        _state["account_id"] = demo_accounts[0].ctidTraderAccountId
        print(f"Account demo selezionato: {_state['account_id']}")
        req = ProtoOASymbolCategoryListReq()
        req.ctidTraderAccountId = _state["account_id"]
        client.send(req)

    elif ptype == ProtoOASymbolCategoryListRes().payloadType:
        res = Protobuf.extract(message)
        _state["categories"] = {c.id: c.name for c in res.symbolCategory}
        print(f"Categorie ricevute: {len(_state['categories'])}")
        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = _state["account_id"]
        req.includeArchivedSymbols = False
        client.send(req)

    elif ptype == ProtoOASymbolsListRes().payloadType:
        res = Protobuf.extract(message)
        _state["symbols"] = [s for s in res.symbol if s.enabled]
        print(f"Simboli abilitati ricevuti: {len(_state['symbols'])}")
        _save_and_stop()


def _save_and_stop():
    categories = _state["categories"]
    symbols = _state["symbols"]

    rows = []
    for s in symbols:
        rows.append({
            "symbolId": s.symbolId,
            "symbolName": s.symbolName,
            "category": categories.get(s.symbolCategoryId, "Unknown"),
            "categoryId": s.symbolCategoryId,
        })

    rows.sort(key=lambda r: (r["category"], r["symbolName"]))

    out_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(out_dir, "ctrader_symbols.json")
    csv_path = os.path.join(out_dir, "ctrader_symbols.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbolId", "symbolName", "category", "categoryId"])
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(r["category"] for r in rows)
    print("\n── Riepilogo per categoria ─────────────────────────────")
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:<30} {n:>4} simboli")
    print(f"\nTotale: {len(rows)} simboli")
    print(f"\nFile salvati:")
    print(f"  {json_path}")
    print(f"  {csv_path}")

    reactor.stop()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "ERRORE: CTRADER_CLIENT_ID o CTRADER_CLIENT_SECRET non trovati nel .env\n"
            "Registra un'app su https://openapi.ctrader.com/ e aggiungili al .env"
        )
        return

    _state["token"] = get_access_token()
    print("Access token ottenuto.\n")

    client = Client(EndPoints.PROTOBUF_DEMO_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)
    client.setConnectedCallback(_on_connected)
    client.setDisconnectedCallback(_on_disconnected)
    client.setMessageReceivedCallback(_on_message)
    client.startService()
    reactor.run()


if __name__ == "__main__":
    main()
