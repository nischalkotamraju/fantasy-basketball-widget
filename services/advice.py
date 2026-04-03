import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from .league import get_current_matchups, get_free_agent_suggestions, _fetch, _owner, _team_name

load_dotenv()

MY_TEAM_NAME = os.getenv("MY_TEAM_NAME", "")
NBA_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

INJURY_STATUSES_SHOW = {"OUT", "INJURED_RESERVE", "DAY_TO_DAY", "SUSPENSION", "SUSPENDED"}

ESPNAPI_TO_SCOREBOARD = {
    "GSW": "GS", "NYK": "NY", "SAS": "SA", "UTA": "UTAH",
    "WAS": "WSH", "PHL": "PHI", "PHO": "PHX", "NOP": "NO",
}

_injury_cache = {}
_injury_cache_loaded = False

def _short_status(status):
    return {"OUT":"OUT","INJURED_RESERVE":"IR","DAY_TO_DAY":"DTD","SUSPENSION":"SSPD","SUSPENDED":"SSPD"}.get(status.upper(), status[:4])

def get_teams_playing_today():
    today = datetime.now().strftime("%Y%m%d")
    try:
        resp = requests.get(NBA_SCOREBOARD_URL, params={"dates": today}, timeout=8)
        playing = set()
        for event in resp.json().get("events", []):
            for comp in event.get("competitions", []):
                for c in comp.get("competitors", []):
                    abbrev = c.get("team", {}).get("abbreviation", "")
                    if abbrev:
                        playing.add(abbrev.upper())
        return playing
    except Exception:
        return set()

def pro_team_playing(pro_team, playing_today):
    if not pro_team:
        return False
    if pro_team.upper() in playing_today:
        return True
    translated = ESPNAPI_TO_SCOREBOARD.get(pro_team.upper(), "")
    return translated in playing_today if translated else False

def _load_injury_cache():
    global _injury_cache, _injury_cache_loaded
    if _injury_cache_loaded:
        return
    try:
        resp = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries", timeout=8)
        for team_entry in resp.json().get("injuries", []):
            for injury in team_entry.get("injuries", []):
                name = injury.get("athlete", {}).get("displayName", "").lower()
                details = injury.get("details", {})
                return_date = details.get("returnDate", "")
                if name:
                    _injury_cache[name] = {"return_date": return_date}
        _injury_cache_loaded = True
    except Exception:
        _injury_cache_loaded = True

def get_return_date(player_name):
    _load_injury_cache()
    entry = _injury_cache.get(player_name.lower(), {})
    return_date = entry.get("return_date", "")
    if not return_date:
        return ""
    try:
        dt = datetime.strptime(return_date[:10], "%Y-%m-%d")
        return dt.strftime("%b") + " " + str(dt.day)
    except Exception:
        return ""

def get_daily_advice(team_name=None):
    global _injury_cache, _injury_cache_loaded
    _injury_cache = {}
    _injury_cache_loaded = False

    playing_today = get_teams_playing_today()
    matchups = get_current_matchups()

    # Get roster data directly
    data = _fetch(["mTeam", "mRoster", "mMatchup", "mMatchupScore"])
    teams = data.get("teams", [])
    current_period = data.get("status", {}).get("currentMatchupPeriod", 1)

    # Find my team
    target = team_name or MY_TEAM_NAME
    my_team_data = None
    if target:
        for t in teams:
            name = (_team_name(t)).lower()
            if target.lower() in name or name in target.lower():
                my_team_data = t
                break

    my_advice = None
    if my_team_data:
        roster = my_team_data.get("roster", {}).get("entries", [])

        # Get lineup slots from schedule
        bench_names = set()
        for m in data.get("schedule", []):
            if m.get("matchupPeriodId") != current_period:
                continue
            for side in ["home", "away"]:
                side_data = m.get(side, {})
                if side_data.get("teamId") == my_team_data.get("id"):
                    for entry in side_data.get("rosterForCurrentScoringPeriod", {}).get("entries", []):
                        slot = entry.get("lineupSlotId", -1)
                        if slot in (20, 21, 17):  # bench/IR slots
                            player = entry.get("playerPoolEntry", {}).get("player", {})
                            bench_names.add(player.get("fullName", ""))

        sit_suggestions = []
        injured_starters = []

        # Get all NBA team abbreviations from roster
        for entry in roster:
            pool = entry.get("playerPoolEntry", {})
            player = pool.get("player", {})
            name = player.get("fullName", "")
            status = pool.get("injuryStatus", "ACTIVE").upper()

            if name in bench_names:
                continue

            # Get pro team abbreviation
            pro_team_id = player.get("proTeamId", 0)
            # Map proTeamId to abbreviation
            PRO_TEAM_MAP = {
                1:"ATL",2:"BOS",3:"NOP",4:"CHI",5:"CLE",6:"DAL",7:"DEN",
                8:"DET",9:"GSW",10:"HOU",11:"IND",12:"LAC",13:"LAL",14:"MIA",
                15:"MIL",16:"MIN",17:"BKN",18:"NYK",19:"ORL",20:"PHL",21:"PHO",
                22:"POR",23:"SAC",24:"SAS",25:"OKC",26:"UTA",27:"WAS",28:"TOR",
                29:"MEM",30:"CHA",
            }
            pro_team = PRO_TEAM_MAP.get(pro_team_id, "")
            playing = pro_team_playing(pro_team, playing_today)

            if status in INJURY_STATUSES_SHOW:
                injured_starters.append({
                    "name": name,
                    "status": status,
                    "status_short": _short_status(status),
                    "return_date": get_return_date(name),
                    "playing_today": playing,
                })
            elif not playing:
                sit_suggestions.append({"name": name, "pro_team": pro_team})

        my_advice = {
            "team_name": _team_name(my_team_data),
            "sit_suggestions": sit_suggestions,
            "injured_starters": injured_starters,
        }

    # Top healthy FAs
    fa_list = get_free_agent_suggestions(top_n=8)

    return {
        "date": datetime.now().strftime("%b %d"),
        "matchups": matchups,
        "my_team_advice": my_advice,
        "top_free_agents": fa_list,
    }
