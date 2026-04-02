"""
Injury-based free agent pickup recommendations using ESPN's depth chart API.

Logic:
  1. Scan all fantasy rosters for injured players
  2. For each injured player, find their NBA team's depth chart
  3. Find the next healthy player at that position on the depth chart
  4. If that player is a free agent in the fantasy league, recommend the pickup
"""

import requests
from .league import get_league

ESPN_NBA_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

INJURY_STATUSES_BAD = {"OUT", "INJURED_RESERVE", "DOUBTFUL"}

# espn-api proTeam abbreviation -> ESPN NBA team ID
# Source: site.api.espn.com/apis/site/v2/sports/basketball/nba/teams
PRO_TEAM_TO_ESPN_ID = {
    "ATL": 1,   "BOS": 2,   "BKN": 17,  "CHA": 30,
    "CHI": 4,   "CLE": 5,   "DAL": 6,   "DEN": 7,
    "DET": 8,   "GSW": 9,   "HOU": 10,  "IND": 11,
    "LAC": 12,  "LAL": 13,  "MEM": 29,  "MIA": 14,
    "MIL": 15,  "MIN": 16,  "NOP": 3,   "NYK": 18,
    "OKC": 25,  "ORL": 19,  "PHL": 20,  "PHO": 21,
    "POR": 22,  "SAC": 23,  "SAS": 24,  "TOR": 28,
    "UTA": 26,  "WAS": 27,
}


def get_depth_chart(espn_team_id: int) -> dict:
    """
    Fetch ESPN's depth chart for an NBA team.
    Returns a dict of position -> [player_name, ...] ordered starter to bench.
    """
    url = f"{ESPN_NBA_BASE}/teams/{espn_team_id}/depthcharts"
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {}

    depth = {}
    for position_group in data.get("positionGroups", []):
        for position in position_group.get("positions", []):
            pos_name = position.get("position", {}).get("abbreviation", "")
            athletes = []
            for entry in position.get("athletes", []):
                athlete = entry.get("athlete", {})
                name = athlete.get("fullName", "")
                athlete_id = str(athlete.get("id", ""))
                status = athlete.get("status", {}).get("type", {}).get("name", "active")
                if name:
                    athletes.append({
                        "name": name,
                        "id": athlete_id,
                        "status": status,
                    })
            if pos_name and athletes:
                depth[pos_name] = athletes

    return depth


def get_injury_based_pickups(league=None) -> list[dict]:
    """
    Main function: find injured rostered players, look up depth chart,
    return FA pickup recommendations.
    """
    if league is None:
        league = get_league()

    # Build a set of all free agent names for quick lookup
    try:
        fa_list = league.free_agents(size=150)
    except Exception:
        fa_list = []

    fa_by_name = {}
    for p in fa_list:
        status = (getattr(p, "injuryStatus", None) or "ACTIVE").upper()
        if status not in INJURY_STATUSES_BAD:
            fa_by_name[p.name.lower()] = {
                "name": p.name,
                "position": getattr(p, "position", ""),
                "pro_team": getattr(p, "proTeam", ""),
                "avg_points": round(getattr(p, "avg_points", 0) or 0, 1),
                "total_points": round(getattr(p, "total_points", 0) or 0, 1),
            }

    # Find all injured rostered players across all teams
    injured_rostered = []
    for team in league.teams:
        for player in team.roster:
            status = (getattr(player, "injuryStatus", None) or "ACTIVE").upper()
            if status in INJURY_STATUSES_BAD:
                injured_rostered.append({
                    "player_name": player.name,
                    "fantasy_team": team.team_name,
                    "pro_team": getattr(player, "proTeam", ""),
                    "position": getattr(player, "position", ""),
                    "status": status,
                })

    # For each injured player, check their team's depth chart
    recommendations = []
    seen_suggestions = set()  # avoid duplicate pickup suggestions

    for injured in injured_rostered:
        pro_team = injured["pro_team"]
        espn_id = PRO_TEAM_TO_ESPN_ID.get(pro_team)
        if not espn_id:
            continue

        depth = get_depth_chart(espn_id)
        if not depth:
            continue

        # Find the next healthy player at any matching position
        player_pos = injured["position"]  # e.g. "PG", "C", "SF"

        # Try exact position match first, then related positions
        positions_to_check = [player_pos]
        # Add positional fallbacks for multi-eligible players
        fallbacks = {
            "PG": ["SG", "G"],
            "SG": ["PG", "G"],
            "SF": ["PF", "F"],
            "PF": ["SF", "F"],
            "C":  ["PF", "F/C"],
        }
        positions_to_check += fallbacks.get(player_pos, [])

        found = False
        for pos in positions_to_check:
            if pos not in depth:
                continue
            for depth_player in depth[pos]:
                name = depth_player["name"]
                d_status = depth_player.get("status", "active").lower()

                # Skip if injured on depth chart
                if any(s in d_status for s in ["out", "injured", "doubtful"]):
                    continue

                # Skip the injured player themselves
                if name.lower() == injured["player_name"].lower():
                    continue

                # Check if this depth chart player is a free agent
                if name.lower() in fa_by_name and name not in seen_suggestions:
                    fa_info = fa_by_name[name.lower()]
                    seen_suggestions.add(name)
                    recommendations.append({
                        "add": name,
                        "add_avg_pts": fa_info["avg_points"],
                        "add_position": fa_info["position"],
                        "add_pro_team": fa_info["pro_team"],
                        "replaces": injured["player_name"],
                        "replaces_status": injured["status"],
                        "replaces_fantasy_team": injured["fantasy_team"],
                        "reason": f"{injured['player_name']} ({injured['status']}) → depth chart next up",
                    })
                    found = True
                    break
            if found:
                break

    # Sort by avg points of the suggested pickup
    recommendations.sort(key=lambda r: r["add_avg_pts"], reverse=True)
    return recommendations