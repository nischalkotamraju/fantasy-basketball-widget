"""
Core ESPN Fantasy Basketball service.
All ESPN API interactions live here — shared by the CLI and REST API.
"""

import os
import requests
from dotenv import load_dotenv
from espn_api.basketball import League

load_dotenv()

# Build proxy config from env vars
def _get_proxies():
    host = os.getenv("PROXY_HOST")
    port = os.getenv("PROXY_PORT")
    user = os.getenv("PROXY_USER")
    pwd  = os.getenv("PROXY_PASS")
    if host and port and user and pwd:
        url = f"http://{user}:{pwd}@{host}:{port}"
        return {"http": url, "https": url}
    return None

def _make_proxied_session():
    """Return a requests.Session pre-configured with the proxy."""
    session = requests.Session()
    proxies = _get_proxies()
    if proxies:
        session.proxies.update(proxies)
    return session

# Patch requests.Session globally so espn-api picks up the proxy
_proxies = _get_proxies()
if _proxies:
    import espn_api.requests.espn_requests as _espn_req

    # Patch requests.get in the espn_api module directly
    _original_get = requests.get
    def _proxied_get(url, **kwargs):
        kwargs.setdefault("proxies", _proxies)
        return _original_get(url, **kwargs)

    requests.get = _proxied_get
    _espn_req.requests.get = _proxied_get


def _get_owner(team) -> str:
    """Safely extract owner name — handles both old 'owner' str and new 'owners' list."""
    if hasattr(team, "owners") and team.owners:
        o = team.owners[0]
        if isinstance(o, dict):
            return f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        return str(o)
    if hasattr(team, "owner"):
        return str(team.owner)
    return "Unknown"


def get_league() -> League:
    """Instantiate and return the ESPN league object using .env credentials."""
    league_id = int(os.getenv("LEAGUE_ID", 0))
    year = int(os.getenv("SEASON_YEAR", 2025))
    espn_s2 = os.getenv("ESPN_S2")
    swid = os.getenv("ESPN_SWID")

    if not all([league_id, espn_s2, swid]):
        raise ValueError(
            "Missing credentials. Make sure LEAGUE_ID, ESPN_S2, and ESPN_SWID "
            "are set in your .env file."
        )

    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def get_standings() -> list[dict]:
    """
    Return all teams sorted by current week fantasy points (descending).
    Each entry includes rank, team name, owner, wins, losses, and this week's score.
    """
    league = get_league()
    box_scores = league.box_scores()

    # Build a map of team_id -> current week score from box scores
    week_scores = {}
    for matchup in box_scores:
        if matchup.home_team:
            week_scores[matchup.home_team.team_id] = round(matchup.home_score, 1)
        if matchup.away_team:
            week_scores[matchup.away_team.team_id] = round(matchup.away_score, 1)

    teams = sorted(
        league.teams,
        key=lambda t: week_scores.get(t.team_id, 0),
        reverse=True,
    )

    standings = []
    for rank, team in enumerate(teams, start=1):
        standings.append({
            "rank": rank,
            "team_name": team.team_name,
            "owner": _get_owner(team),
            "wins": team.wins,
            "losses": team.losses,
            "week_points": week_scores.get(team.team_id, 0),
        })
    return standings


# ---------------------------------------------------------------------------
# Injury Report
# ---------------------------------------------------------------------------

INJURY_STATUSES = {"INJURED_RESERVE", "OUT", "DOUBTFUL", "QUESTIONABLE", "DAY_TO_DAY"}


def get_injury_report() -> list[dict]:
    """
    Scan every roster in the league and return players with injury designations.
    Groups results by team.
    """
    league = get_league()
    report = []

    for team in league.teams:
        injured_players = []
        for player in team.roster:
            status = getattr(player, "injuryStatus", None) or getattr(player, "injury_status", "ACTIVE")
            if status and status.upper() not in ("ACTIVE", "NORMAL", "NA", "NONE", ""):
                injured_players.append({
                    "name": player.name,
                    "position": player.position,
                    "status": status,
                    "pro_team": getattr(player, "proTeam", "N/A"),
                })

        if injured_players:
            report.append({
                "team_name": team.team_name,
                "owner": _get_owner(team),
                "injured_players": injured_players,
            })

    return report


# ---------------------------------------------------------------------------
# Free Agent Suggestions
# ---------------------------------------------------------------------------

def get_free_agent_suggestions(position: str = None, top_n: int = 15) -> list[dict]:
    """
    Return top available free agents sorted by avg points this season.
    Optionally filter by position (e.g. 'PG', 'C', 'SF', etc.)
    """
    league = get_league()

    size = top_n * 3 if position else top_n * 2
    try:
        fa_list = league.free_agents(size=size)
    except Exception as e:
        raise RuntimeError(f"Could not fetch free agents: {e}")

    suggestions = []
    for player in fa_list:
        player_pos = getattr(player, "position", "")
        if position and position.upper() not in player_pos.upper():
            continue

        avg_points = getattr(player, "avg_points", 0) or 0
        total_points = getattr(player, "total_points", 0) or 0
        pro_team = getattr(player, "proTeam", "N/A")
        status = getattr(player, "injuryStatus", None) or getattr(player, "injury_status", "ACTIVE")

        suggestions.append({
            "name": player.name,
            "position": player_pos,
            "pro_team": pro_team,
            "avg_points": round(avg_points, 1),
            "total_points": round(total_points, 1),
            "injury_status": status,
        })

        if len(suggestions) >= top_n:
            break

    suggestions.sort(key=lambda p: p["avg_points"], reverse=True)
    return suggestions


# ---------------------------------------------------------------------------
# Current Matchups
# ---------------------------------------------------------------------------

def get_current_matchups() -> list[dict]:
    """
    Return this week's matchups with current scores.
    """
    league = get_league()
    box_scores = league.box_scores()

    matchups = []
    for matchup in box_scores:
        home = matchup.home_team
        away = matchup.away_team
        matchups.append({
            "home_team": home.team_name,
            "home_owner": _get_owner(home),
            "home_score": round(matchup.home_score, 1),
            "away_team": away.team_name,
            "away_owner": _get_owner(away),
            "away_score": round(matchup.away_score, 1),
            "winner": (
                home.team_name if matchup.home_score > matchup.away_score
                else away.team_name if matchup.away_score > matchup.home_score
                else "TIE"
            ),
        })

    return matchups