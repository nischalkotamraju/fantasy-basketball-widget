"""
ESPN Fantasy Basketball — Click CLI layer.

Usage examples:
    python cli.py standings
    python cli.py injuries
    python cli.py free-agents
    python cli.py free-agents --position C --top 10
    python cli.py matchups
"""

import click
from tabulate import tabulate
from services.league import (
    get_standings,
    get_injury_report,
    get_free_agent_suggestions,
    get_current_matchups,
)


@click.group()
def cli():
    """ESPN Fantasy Basketball CLI — your league stats at your fingertips."""
    pass


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

@cli.command()
def standings():
    """Show league standings sorted by total fantasy points."""
    click.echo("\n🏀  League Standings\n")
    try:
        data = get_standings()
        rows = [
            [
                t["rank"],
                t["team_name"],
                t["owner"],
                f"{t['wins']}-{t['losses']}",
                t["week_points"],
            ]
            for t in data
        ]
        headers = ["Rank", "Team", "Owner", "W-L", "Week Pts"]
        click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


# ---------------------------------------------------------------------------
# Injury Report
# ---------------------------------------------------------------------------

@cli.command()
def injuries():
    """Show injured players grouped by team."""
    click.echo("\n🚑  Injury Report\n")
    try:
        report = get_injury_report()
        if not report:
            click.secho("No injuries found across all rosters.", fg="green")
            return

        for entry in report:
            click.secho(f"  {entry['team_name']} ({entry['owner']})", fg="yellow", bold=True)
            rows = [
                [p["name"], p["position"], p["pro_team"], p["status"]]
                for p in entry["injured_players"]
            ]
            click.echo(tabulate(rows, headers=["Player", "Pos", "Pro Team", "Status"], tablefmt="simple"))
            click.echo()
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


# ---------------------------------------------------------------------------
# Free Agents
# ---------------------------------------------------------------------------

@cli.command("free-agents")
@click.option("--position", "-p", default=None, help="Filter by position (PG, SG, SF, PF, C)")
@click.option("--top", "-n", default=15, show_default=True, help="Number of results to show")
def free_agents(position, top):
    """Show top available free agents, optionally filtered by position."""
    label = f" ({position})" if position else ""
    click.echo(f"\n📋  Top Free Agents{label}\n")
    try:
        players = get_free_agent_suggestions(position=position, top_n=top)
        if not players:
            click.secho("No free agents found for the given filters.", fg="yellow")
            return

        rows = [
            [
                i + 1,
                p["name"],
                p["position"],
                p["pro_team"],
                p["avg_points"],
                p["total_points"],
                p["injury_status"],
            ]
            for i, p in enumerate(players)
        ]
        headers = ["#", "Player", "Pos", "Pro Team", "Avg Pts", "Total Pts", "Status"]
        click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


# ---------------------------------------------------------------------------
# Matchups
# ---------------------------------------------------------------------------

@cli.command()
def matchups():
    """Show current week matchups with scores."""
    click.echo("\n⚔️   Current Week Matchups\n")
    try:
        data = get_current_matchups()
        for m in data:
            home = m["home_team"]
            away = m["away_team"]
            hs = m["home_score"]
            as_ = m["away_score"]
            winner = m["winner"]

            home_marker = " ✓" if winner == home else ""
            away_marker = " ✓" if winner == away else ""

            click.echo(
                f"  {home}{home_marker}  {hs}  vs  {as_}  {away}{away_marker}"
            )
        click.echo()
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


if __name__ == "__main__":
    cli()