# ESPN Fantasy Basketball Scraper

A Python tool to pull stats, injuries, standings, and free agent recommendations from your **private** ESPN fantasy basketball league.

Exposes both a **REST API** (FastAPI) and a **CLI** (Click).

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get your ESPN credentials

Your league is private, so you need two cookies from ESPN:

1. Go to [espn.com](https://espn.com) and log in
2. Open **DevTools** → **Application** → **Cookies** → `https://www.espn.com`
3. Copy the values for:
   - `espn_s2`
   - `SWID`

Also grab your **League ID** from the URL when you're on your league page:
`https://fantasy.espn.com/basketball/league?leagueId=XXXXXXXX`

### 3. Create your `.env` file
```bash
cp .env.example .env
```
Then fill in your values:
```
ESPN_S2=your_espn_s2_value
ESPN_SWID={your-swid-value}
LEAGUE_ID=123456789
SEASON_YEAR=2025
```

---

## CLI Usage

```bash
# League standings (sorted by fantasy points)
python cli.py standings

# Injury report across all rosters
python cli.py injuries

# Top 15 free agents available
python cli.py free-agents

# Filter by position
python cli.py free-agents --position C
python cli.py free-agents --position PG --top 10

# This week's matchups
python cli.py matchups
```

---

## REST API Usage

Start the server:
```bash
uvicorn main:app --reload
```

Then visit **http://localhost:8000/docs** for interactive Swagger docs.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/standings` | League standings sorted by FPTS |
| GET | `/injuries` | Injured players grouped by team |
| GET | `/free-agents` | Top available free agents |
| GET | `/free-agents?position=C&top_n=10` | Filtered free agents |
| GET | `/matchups` | Current week scores |

### Example responses

**GET /standings**
```json
{
  "standings": [
    { "rank": 1, "team_name": "Hoops Squad", "owner": "John", "wins": 12, "losses": 3, "points_for": 1842.5, "points_against": 1654.2 }
  ]
}
```

**GET /injuries**
```json
{
  "injury_report": [
    {
      "team_name": "Hoops Squad",
      "owner": "John",
      "injured_players": [
        { "name": "Ja Morant", "position": "PG", "status": "OUT", "pro_team": "MEM" }
      ]
    }
  ]
}
```

---

## Project Structure

```
espn-fantasy-scraper/
├── main.py            # FastAPI REST API
├── cli.py             # Click CLI
├── services/
│   └── league.py      # Core ESPN logic (shared by both)
├── .env               # Your credentials (never commit this)
├── .env.example       # Template
└── requirements.txt
```
