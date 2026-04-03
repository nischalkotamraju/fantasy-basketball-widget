"""
Direct ESPN Fantasy Basketball API client with proxy support.
Bypasses espn-api library so we fully control proxy routing.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba"

def _session() -> requests.Session:
    s = requests.Session()
    s.cookies.set("espn_s2", os.getenv("ESPN_S2", ""))
    s.cookies.set("SWID", os.getenv("ESPN_SWID", ""))
    s.headers.update({"User-Agent": "Mozilla/5.0"})

    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    user = os.getenv("PROXY_USER")
    pwd  = os.getenv("PROXY_PASS")
    if host and port and user and pwd:
        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
        s.proxies = {"http": proxy_url, "https": proxy_url}

    return s

def _league_url() -> str:
    league_id = os.getenv("LEAGUE_ID")
    year = os.getenv("SEASON_YEAR", "2024")
    return f"{BASE}/seasons/{year}/segments/0/leagues/{league_id}"

def fetch(views: list, extra_headers: dict = None) -> dict:
    s = _session()
    headers = extra_headers or {}
    r = s.get(_league_url(), params={"view": views}, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_free_agents(size: int = 50) -> dict:
    s = _session()
    filters = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
            "limit": size,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }
    headers = {"x-fantasy-filter": json.dumps(filters)}
    r = s.get(_league_url(), params={"view": "kona_player_info"}, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()