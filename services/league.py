"""
Core ESPN Fantasy Basketball service.
Uses direct HTTP client instead of espn-api to support proxy routing.
"""

import os
from dotenv import load_dotenv
from .espn_client import fetch, fetch_free_agents

load_dotenv()

MY_TEAM_NAME = os.getenv("MY_TEAM_NAME", "")

POSITION_MAP = {
    0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C",
    5: "PG/SG", 6: "SF/PF", 7: "PG/SF", 8: "PF/C",
    9: "PG/SG/SF", 10: "SG/SF", 11: "PG/SG/SF/PF",
    12: "PG/SG/SF/PF/C", 13: "UT", 14: "BE", 15: "IR", 17: "BE", 20: "BE", 21: "IR"
}

INJURY_STATUSES_SHOW = {"OUT", "INJURED_RESERVE", "DAY_TO_DAY", "SUSPENSION", "SUSPENDED"}

def _short_status(status: str) -> str:
    return {
        "OUT": "OUT",
        "INJURED_RESERVE": "IR",
        "DAY_TO_DAY": "DTD",
        "SUSPENSION": "SSPD",
        "SUSPENDED": "SSPD",
    }.get(status.upper(), status[:4])

def _get_owner(team: dict) -> str:
    owners = team.get("owners", [])
    if owners:
        o = owners[0]
        if isinstance(o, dict):
            return f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        return str(o)
    return team.get("location", "") + " " + team.get("nickname", "")

def _team_name(team: dict) -> str:
    return (team.get("location", "") + " " + team.get("nickname", "")).strip() or team.get("name", "Unknown")

def _player_position(player: dict) -> str:
    slot_id = player.get("lineupSlotId", -1)
    default_pos = player.get("playerPoolEntry", {}).get("player", {}).get("defaultPositionId", -1)
    pos_map = {1: "PG", 2: "SG", 3: "SF", 4: "PF", 5: "C", 6: "PG/SG", 7: "SG/SF", 8: "SF/PF", 9: "PF/C"}
    return pos_map.get(default_pos, "?")

def _injury_status(player: dict) -> str:
    return player.get("playerPoolEntry", {}).get("injuryStatus", "ACTIVE")

def _avg_points(player: dict) -> float:
    stats = player.get("playerPoolEntry", {}).get("playerStats", {}).get("appliedStatTotal", 0)
    return round(float(stats) if stats else 0, 1)

def get_league():
    """Return raw league data."""
    return fetch(["mTeam", "mRoster", "mMatchup", "mMatchupScore", "mStandings", "mSettings"])

# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def get_standings() -> list[dict]:
    data = get_league()
    teams = data.get("teams", [])
    box = fetch(["mMatchup", "mMatchupScore"])
    schedules = box.get("schedule", [])

    # Get current week scores
    current_period = data.get("status", {}).get("currentScoringPeriod", {}).get("id", 1)
    week_scores = {}
    for matchup in schedules:
        if matchup.get("matchupPeriodId") == current_period or True:
            home = matchup.get("home", {})
            away = matchup.get("away", {})
            if home:
                week_scores[home.get("teamId")] = round(home.get("totalPoints", 0), 1)
            if away:
                week_scores[away.get("teamId")] = round(away.get("totalPoints", 0), 1)

    sorted_teams = sorted(teams, key=lambda t: week_scores.get(t.get("id"), 0), reverse=True)

    standings = []
    for rank, team in enumerate(sorted_teams, 1):
        record = team.get("record", {}).get("overall", {})
        standings.append({
            "rank": rank,
            "team_name": _team_name(team),
            "owner": _get_owner(team),
            "wins": record.get("wins", 0),
            "losses": record.get("losses", 0),
            "week_points": week_scores.get(team.get("id"), 0),
        })
    return standings

# ---------------------------------------------------------------------------
# Current Matchups
# ---------------------------------------------------------------------------

def get_current_matchups() -> list[dict]:
    data = get_league()
    schedules = data.get("schedule", [])
    current_period = data.get("status", {}).get("currentMatchupPeriod", 1)
    teams_by_id = {t["id"]: t for t in data.get("teams", [])}

    matchups = []
    seen = set()
    for matchup in schedules:
        if matchup.get("matchupPeriodId") != current_period:
            continue
        home_id = matchup.get("home", {}).get("teamId")
        away_id = matchup.get("away", {}).get("teamId")
        if not home_id or not away_id:
            continue
        pair = tuple(sorted([home_id, away_id]))
        if pair in seen:
            continue
        seen.add(pair)

        home_team = teams_by_id.get(home_id, {})
        away_team = teams_by_id.get(away_id, {})
        matchups.append({
            "home_team": _team_name(home_team),
            "home_score": round(matchup.get("home", {}).get("totalPoints", 0), 1),
            "away_team": _team_name(away_team),
            "away_score": round(matchup.get("away", {}).get("totalPoints", 0), 1),
        })
    return matchups

# ---------------------------------------------------------------------------
# Injury Report
# ---------------------------------------------------------------------------

def get_injury_report() -> list[dict]:
    data = get_league()
    report = []
    for team in data.get("teams", []):
        injured = []
        for entry in team.get("roster", {}).get("entries", []):
            status = _injury_status(entry)
            if status.upper() not in ("ACTIVE", "NORMAL", "NA", "NONE", ""):
                player = entry.get("playerPoolEntry", {}).get("player", {})
                injured.append({
                    "name": player.get("fullName", "?"),
                    "position": _player_position(entry),
                    "status": status,
                    "pro_team": str(player.get("proTeamId", "?")),
                })
        if injured:
            report.append({
                "team_name": _team_name(team),
                "owner": _get_owner(team),
                "injured_players": injured,
            })
    return report

# ---------------------------------------------------------------------------
# Free Agents
# ---------------------------------------------------------------------------

def get_free_agent_suggestions(position: str = None, top_n: int = 15) -> list[dict]:
    data = fetch_free_agents(size=top_n * 3)
    players = data.get("players", [])
    suggestions = []
    for entry in players:
        pool = entry.get("playerPoolEntry", {})
        player = pool.get("player", {})
        status = pool.get("injuryStatus", "ACTIVE")
        if status.upper() in ("OUT", "INJURED_RESERVE"):
            continue
        avg_pts = round(float(pool.get("playerStats", {}).get("appliedStatTotal", 0) or 0), 1)
        pos = _player_position(entry)
        if position and position.upper() not in pos.upper():
            continue
        suggestions.append({
            "name": player.get("fullName", "?"),
            "position": pos,
            "avg_points": avg_pts,
            "injury_status": status,
        })
        if len(suggestions) >= top_n:
            break
    suggestions.sort(key=lambda p: p["avg_points"], reverse=True)
    return suggestions

# ---------------------------------------------------------------------------
# Helpers used by advice.py
# ---------------------------------------------------------------------------

def _get_owner_from_team(team):
    return _get_owner(team)