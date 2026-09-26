"""
Live state for the Spiderrh site.

The token is read off Solana. The spider's wallet balance is still read off
Robinhood Chain, the same way it was. Nothing is written, no key is loaded,
and there is no code path here that can sign anything. The site is a window,
not a control panel.
"""
import os
import time

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

RPC = os.environ.get("FLY_RH_RPC", "https://rpc.mainnet.chain.robinhood.com")
SOL_RPC = os.environ.get("FLY_SOL_RPC", "https://api.mainnet-beta.solana.com")
WALLET = os.environ.get("FLY_WALLET",
                        "0x6ce4085EfB52a6eBDb7d6989beb8860847f4b42A")
# base58, case-sensitive — do not lowercase
TOKEN = os.environ.get("FLY_TOKEN",
                       "H9Q6v2VGf6t28M46gfdChxNr1JPMhQHVB6C3xb7FAouc")
# the wallet that made the first eight launches, still the fee recipient there
WALLET_V1 = os.environ.get("FLY_WALLET_V1",
                           "0x739Ccc9dd8Ed6412F00782927dbd087c4e72bFc3")

app = FastAPI(title="Spiderrh")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"],
    allow_headers=["*"])

_cache = {"at": 0.0, "data": None}
TTL = 20.0


def rpc(url, method, params):
    r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                                 "method": method, "params": params},
                      timeout=15).json()
    if "error" in r:
        raise RuntimeError(str(r["error"])[:200])
    return r.get("result")


def mint_facts(info):
    """Symbol and ui supply from a jsonParsed SPL mint account."""
    value = (info or {}).get("value") or {}
    data = value.get("data") or {}
    parsed = data.get("parsed") or {}
    inf = parsed.get("info") or {}
    symbol = ""
    name = ""
    for ext in inf.get("extensions") or []:
        if ext.get("extension") == "tokenMetadata":
            state = ext.get("state") or {}
            symbol = state.get("symbol") or ""
            name = state.get("name") or ""
    decimals = inf.get("decimals")
    if decimals is None:
        decimals = 6
    raw = inf.get("supply")
    supply = None if raw is None else int(raw) / (10 ** int(decimals))
    return name, symbol, supply


def as_int(v, default=0):
    if v is None:
        return default
    return int(v, 16) if str(v).startswith("0x") else int(v)


def state():
    now = time.time()
    if _cache["data"] and now - _cache["at"] < TTL:
        return _cache["data"]

    out = {"chain": {"name": "Solana", "id": "mainnet-beta", "rpc": SOL_RPC},
           "ok": True, "error": None}
    try:
        out["chain"]["block"] = rpc(SOL_RPC, "getSlot", [])

        try:
            bal = as_int(rpc(RPC, "eth_getBalance", [WALLET, "latest"]))
            old = as_int(rpc(RPC, "eth_getBalance", [WALLET_V1, "latest"]))
            out["wallet"] = {
                "address": WALLET, "eth": bal / 1e18,
                "launches_left": int(bal / 1e18 / 0.00055),
                "previous": {"address": WALLET_V1, "eth": old / 1e18},
            }
        except Exception:
            out["wallet"] = None

        name, symbol, supply = mint_facts(rpc(
            SOL_RPC, "getAccountInfo",
            [TOKEN, {"encoding": "jsonParsed"}]))
        out["token"] = {
            "address": TOKEN,
            "name": name or "Spider Brain",
            "symbol": symbol or "SPIDER",
            "supply": supply,
            "addresses_touched": None,
            "transfers": None,
            "pair": "GOOGL",
            "creator_tax_pct": 1,
            "url": f"https://solscan.io/token/{TOKEN}",
        }
    except Exception as exc:
        out["ok"] = False
        out["error"] = str(exc)[:200]

    out["updated"] = int(now)
    _cache.update(at=now, data=out)
    return out


@app.get("/api/state")
def api_state():
    return state()


@app.get("/api/health")
def health():
    return {"ok": True, "t": int(time.time())}


@app.get("/")
def root():
    return {"service": "spiderrh", "see": "/api/state"}
