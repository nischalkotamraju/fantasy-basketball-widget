"""
ESPN Fantasy Basketball — FastAPI REST layer.

Run with:
    uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, Query
from services.league import (
    get_standings,
    get_injury_report,
    get_free_agent_suggestions,
    get_current_matchups,
)

app = FastAPI(
    title="ESPN Fantasy Basketball API",
    description="Scraper & analytics API for your private ESPN fantasy basketball league.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {"message": "ESPN Fantasy Basketball API is running. Visit /docs for all endpoints."}


@app.get("/standings", summary="League standings sorted by fantasy points")
def standings():
    try:
        return {"standings": get_standings()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/injuries", summary="Injury report — injured players grouped by team")
def injuries():
    try:
        return {"injury_report": get_injury_report()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/free-agents", summary="Top available free agents (optional position filter)")
def free_agents(
    position: str = Query(None, description="Filter by position: PG, SG, SF, PF, C"),
    top_n: int = Query(15, description="Number of results to return", ge=1, le=50),
):
    try:
        return {"free_agents": get_free_agent_suggestions(position=position, top_n=top_n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/matchups", summary="Current week matchups with live scores")
def matchups():
    try:
        return {"matchups": get_current_matchups()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/advice", summary="Daily lineup advice: sit/start, FA pickups, injury replacements")
def daily_advice(team: str = Query(None, description="Your team name (overrides MY_TEAM_NAME in .env)")):
    try:
        from services.advice import get_daily_advice
        return get_daily_advice(team_name=team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))