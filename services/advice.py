"""
Daily fantasy advice engine.

Pulls today's NBA schedule from ESPN's public API, then for the user's team:
  1. Identifies which starters have no game today → suggest bench them
  2. Identifies which starters are injured → suggest drop/replace
  3. Finds best available free agents at those positions who ARE playing today
"""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from .league import get_league, _get_owner

load_dotenv()

MY_TEAM_NAME = os.getenv("MY_TEAM_NAME", "")  # Set this in .env to your exact team name

NBA_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

INJURY_STATUSES_BAD = {"OUT", "INJURED_RESERVE", "DOUBTFUL"}
INJURY_STATUSES_SHOW = {"OUT", "INJURED_RESERVE", "DAY_TO_DAY", "SUSPENSION", "SUSPENDED"}
INJURY_STATUSES_QUESTIONABLE = {"QUESTIONABLE", "DAY_TO_DAY"}


def _short_status(status: str) -> str:
    return {
        "OUT": "OUT",
        "INJURED_RESERVE": "IR",
        "DAY_TO_DAY": "DTD",
        "SUSPENSION": "SSPD",
        "SUSPENDED": "SSPD",
    }.get(status.upper(), status[:4])


# Cache injury return dates so we don't re-fetch per player
_injury_cache: dict = {}
_injury_cache_loaded = False

def _load_injury_cache():
    """Load all NBA injuries from ESPN once per process and cache by player name."""
    global _injury_cache, _injury_cache_loaded
    if _injury_cache_loaded:
        return
    try:
        resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
            timeout=8
        )
        data = resp.json()
        for team_entry in data.get("injuries", []):
            for injury in team_entry.get("injuries", []):
                name = injury.get("athlete", {}).get("displayName", "").lower()
                details = injury.get("details", {})
                return_date = details.get("returnDate", "")
                status = injury.get("status", "")
                if name:
                    _injury_cache[name] = {
                        "return_date": return_date,
                        "status": status,
                    }
        _injury_cache_loaded = True
        print(f"Injury cache loaded: {len(_injury_cache)} players")
    except Exception as e:
        print(f"Injury cache load failed: {e}")
        _injury_cache_loaded = True


def get_return_date(player_name: str) -> str:
    """Return estimated return date string like 'Apr 10', or '' if unknown."""
    _load_injury_cache()
    entry = _injury_cache.get(player_name.lower(), {})
    return_date = entry.get("return_date", "")
    if not return_date:
        return ""
    try:
        dt = datetime.strptime(return_date[:10], "%Y-%m-%d")
        # %-d is Linux only, use cross-platform approach
        return dt.strftime("%b") + " " + str(dt.day)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Step 1: Fetch today's NBA teams playing
# ---------------------------------------------------------------------------

def get_teams_playing_today() -> set[str]:
    """
    Hit ESPN's public NBA scoreboard for today and return a set of
    pro team abbreviations that have a game today (e.g. {'LAL', 'GSW', ...}).
    """
    today = datetime.now().strftime("%Y%m%d")
    try:
        resp = requests.get(NBA_SCOREBOARD_URL, params={"dates": today}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Could not fetch NBA schedule: {e}")

    playing = set()
    for event in data.get("events", []):
        for competition in event.get("competitions", []):
            for competitor in competition.get("competitors", []):
                abbrev = competitor.get("team", {}).get("abbreviation", "")
                if abbrev:
                    playing.add(abbrev.upper())
    return playing


# ---------------------------------------------------------------------------
# Step 2: Map espn-api proTeam names to ESPN scoreboard abbreviations
# ---------------------------------------------------------------------------

# espn-api uses full team names; scoreboard uses abbreviations.
# This map covers all 30 NBA teams.
PRO_TEAM_TO_ABBREV = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    # espn-api alternate names
    "GS Warriors": "GSW", "LA Lakers": "LAL", "SA Spurs": "SAS", "NO Pelicans": "NOP",
    "NY Knicks": "NYK", "OKC Thunder": "OKC", "Por Trail Blazers": "POR",
}

# Translate espn-api proTeam abbreviations → ESPN scoreboard abbreviations
ESPNAPI_TO_SCOREBOARD = {
    "GSW": "GS",
    "NYK": "NY",
    "SAS": "SA",
    "UTA": "UTAH",
    "WAS": "WSH",
    "PHL": "PHI",
    "PHO": "PHX",
    "NOP": "NO",
    "MIN": "MIN",
    "CLE": "CLE",
    "CHA": "CHA",
    "LAL": "LAL",
    "LAC": "LAC",
    "OKC": "OKC",
    "POR": "POR",
    "DET": "DET",
    "BOS": "BOS",
    "MIA": "MIA",
    "SAC": "SAC",
    "MIL": "MIL",
    "ATL": "ATL",
    "IND": "IND",
    "HOU": "HOU",
    "DAL": "DAL",
    "MEM": "MEM",
    "TOR": "TOR",
    "CHI": "CHI",
    "BKN": "BKN",
    "NOP": "NO",
    "ORL": "ORL",
}

def pro_team_playing(pro_team: str, playing_today: set[str]) -> bool:
    if not pro_team:
        return False
    # Try direct match first (e.g. ATL, BOS, MIA — same in both)
    if pro_team.upper() in playing_today:
        return True
    # Try translated abbreviation
    translated = ESPNAPI_TO_SCOREBOARD.get(pro_team.upper(), "")
    if translated and translated in playing_today:
        return True
    return False


# ---------------------------------------------------------------------------
# Step 3: Build advice for a single team
# ---------------------------------------------------------------------------

def build_team_advice(team, box_score, playing_today: set[str], fa_by_position: dict) -> dict:
    """
    Given a fantasy team and today's schedule, return:
      - sit_suggestions: active starters who have no game today
      - injured_starters: starters who are hurt
      - fa_pickups: recommended free agent adds keyed by injured/sitting player
    """
    sit_suggestions = []
    injured_starters = []
    fa_pickups = []

    # Use team.roster as source of truth — box score lineup is frozen at matchup start
    # and won't reflect recent drops/adds
    roster = team.roster

    # espn-api marks bench players with acquisition type or we check slot from box score
    # Since slot_position isn't on roster players, treat all non-IR roster spots as active
    # and use the box score only to identify bench slots by name matching
    bench_names = set()
    if box_score:
        lineup = box_score.home_lineup if box_score.home_team == team else box_score.away_lineup
        bench_names = {p.name for p in lineup if getattr(p, "slot_position", "") in ("BE", "Bench")}

    starters = [p for p in roster if p.name not in bench_names and
                (getattr(p, "injuryStatus", None) or "ACTIVE").upper() != "INJURED_RESERVE" and
                getattr(p, "slot_position", "") not in ("BE", "IR", "Bench")]
    bench = [p for p in roster if p.name in bench_names]

    for player in starters:
        pro_team = getattr(player, "proTeam", "") or ""
        status = (getattr(player, "injuryStatus", None) or "ACTIVE").upper()
        playing = pro_team_playing(pro_team, playing_today)

        # Injured/questionable starter — show all non-active statuses
        if status in INJURY_STATUSES_SHOW:
            return_date = get_return_date(player.name)
            injured_starters.append({
                "name": player.name,
                "position": getattr(player, "position", ""),
                "status": status,
                "status_short": _short_status(status),
                "return_date": return_date,
                "pro_team": pro_team,
                "playing_today": pro_team_playing(pro_team, playing_today),
            })
            # Find best FA to stream while this player is out
            pos = getattr(player, "position", "")
            replacements = fa_by_position.get(pos, [])
            if replacements:
                best = replacements[0]
                fa_pickups.append({
                    "add": best["name"],
                    "add_position": best["position"],
                    "add_avg_pts": best["avg_points"],
                    "add_playing_today": best["playing_today"],
                    "while_out": player.name,
                    "while_out_status": status,
                })

        # Starter has no game today — suggest bench swap
        elif not playing and status not in INJURY_STATUSES_QUESTIONABLE:
            # Find a bench player who IS playing today
            bench_swap = next(
                (p for p in bench if pro_team_playing(getattr(p, "proTeam", ""), playing_today)
                 and (getattr(p, "injuryStatus", None) or "ACTIVE").upper() == "ACTIVE"),
                None
            )
            suggestion = {
                "name": player.name,
                "position": getattr(player, "position", ""),
                "pro_team": pro_team,
                "no_game_today": True,
            }
            if bench_swap:
                suggestion["swap_with"] = bench_swap.name
                suggestion["swap_position"] = getattr(bench_swap, "position", "")
            sit_suggestions.append(suggestion)

    return {
        "team_name": team.team_name,
        "owner": _get_owner(team),
        "sit_suggestions": sit_suggestions,
        "injured_starters": injured_starters,
        "fa_pickups": fa_pickups,
    }


# ---------------------------------------------------------------------------
# Step 4: Pre-bucket free agents by position
# ---------------------------------------------------------------------------

def get_fa_by_position(league, playing_today: set[str], size: int = 60) -> dict:
    """
    Fetch free agents and bucket them by position, filtered to healthy players
    who are playing today (best pickups only).
    """
    try:
        fa_list = league.free_agents(size=size)
    except Exception:
        return {}

    by_pos = {}
    for player in fa_list:
        pos = getattr(player, "position", "")
        status = (getattr(player, "injuryStatus", None) or "ACTIVE").upper()
        if status in INJURY_STATUSES_BAD:
            continue

        pro_team = getattr(player, "proTeam", "")
        playing = pro_team_playing(pro_team, playing_today)
        avg_pts = round(getattr(player, "avg_points", 0) or 0, 1)

        entry = {
            "name": player.name,
            "position": pos,
            "pro_team": pro_team,
            "avg_points": avg_pts,
            "playing_today": playing,
            "status": status,
        }

        if pos not in by_pos:
            by_pos[pos] = []
        by_pos[pos].append(entry)

    # Sort each position bucket by avg_points desc, playing today first
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: (p["playing_today"], p["avg_points"]), reverse=True)

    return by_pos


# ---------------------------------------------------------------------------
# Main advice endpoint
# ---------------------------------------------------------------------------

def get_daily_advice(team_name: str = None) -> dict:
    """
    Full daily advice: matchups, sit/start recommendations, FA pickups.
    If team_name is provided (or MY_TEAM_NAME in .env), also returns
    personalized advice for that team.
    """
    global _injury_cache, _injury_cache_loaded
    _injury_cache = {}
    _injury_cache_loaded = False
    league = get_league()
    playing_today = get_teams_playing_today()
    box_scores = league.box_scores()
    fa_by_pos = get_fa_by_position(league, playing_today)

    # Build a team_name -> box_score map
    box_map = {}
    for bs in box_scores:
        if bs.home_team:
            box_map[bs.home_team.team_name] = bs
        if bs.away_team:
            box_map[bs.away_team.team_name] = bs

    # Matchups summary — use all teams to catch any box_score gaps
    matchups = []
    seen_pairs = set()
    for bs in box_scores:
        try:
            home = bs.home_team
            away = bs.away_team
            if not home or not away:
                continue
            pair = tuple(sorted([home.team_name, away.team_name]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            matchups.append({
                "home_team": home.team_name,
                "home_score": round(bs.home_score or 0, 1),
                "away_team": away.team_name,
                "away_score": round(bs.away_score or 0, 1),
            })
        except Exception:
            continue

    # Teams playing today summary (for display)
    teams_with_games = sorted(playing_today)

    # My team advice
    target = team_name or MY_TEAM_NAME
    my_advice = None
    if target:
        my_team = next((t for t in league.teams if t.team_name.lower() == target.lower()), None)
        if my_team:
            bs = box_map.get(my_team.team_name)
            my_advice = build_team_advice(my_team, bs, playing_today, fa_by_pos)
        else:
            my_advice = {"error": f"Team '{target}' not found. Check MY_TEAM_NAME in .env"}

    # Top healthy free agents sorted by avg points
    healthy_fa = []
    seen = set()
    for pos_list in fa_by_pos.values():
        for p in pos_list:
            if p["name"] not in seen:
                healthy_fa.append(p)
                seen.add(p["name"])
    healthy_fa.sort(key=lambda p: p["avg_points"], reverse=True)

    return {
        "date": datetime.now().strftime("%b %d"),
        "nba_teams_playing_today": len(playing_today),
        "matchups": matchups,
        "my_team_advice": my_advice,
        "top_free_agents": healthy_fa[:8],
    }