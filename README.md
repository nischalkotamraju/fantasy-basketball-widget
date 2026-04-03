# ESPN Fantasy Basketball Widget

An iOS widget built with [Scriptable](https://scriptable.app) that shows your ESPN private fantasy basketball league — live matchup scores, bench suggestions, injury alerts, and top free agents — all on your home screen.

![Widget Preview](widget_preview.png)

## Features

- **Live matchups** — current week scores for all 6 matchups, winner highlighted in green
- **Bench today** — players on your roster whose NBA team isn't playing, so you know who to sit
- **Injury alerts** — injured starters with status (OUT / DTD / IR) and projected return date
- **Top free agents** — highest-scoring available players with position and average points
- Refreshes automatically every 15 minutes

## Stack

- **Backend**: Python + FastAPI, deployed on [Railway](https://railway.app)
- **Data**: ESPN Fantasy API (private league via `espn_s2` + `SWID` cookies)
- **Proxy**: Residential proxy to bypass ESPN's IP restrictions on cloud servers
- **Widget**: JavaScript running in [Scriptable](https://scriptable.app) on iOS

## Setup

### 1. Get your ESPN cookies

Log into ESPN Fantasy on your browser, open DevTools, and grab:
- `espn_s2`
- `SWID`

### 2. Deploy the backend

```bash
git clone https://github.com/yourusername/espn-fantasy-scraper
cd espn-fantasy-scraper
```

Set these environment variables in Railway (or a `.env` file for local):

```
ESPN_S2=your_espn_s2_cookie
ESPN_SWID={your-swid-with-braces}
LEAGUE_ID=your_league_id
SEASON_YEAR=2024
MY_TEAM_NAME=Your Exact Team Name
PROXY_HOST=your.proxy.host
PROXY_PORT=6540
PROXY_USER=proxy_username
PROXY_PASS=proxy_password
```

Push to Railway — the `Procfile` handles the rest.

### 3. Install the widget

1. Install [Scriptable](https://apps.apple.com/app/scriptable/id1405459188) on your iPhone
2. Copy `widget.js` into Scriptable (via iCloud or paste directly)
3. Update `API_BASE_URL` and `MY_TEAM` at the top of the script
4. Add a large Scriptable widget to your home screen and select the script

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /matchups` | Current week scores |
| `GET /standings` | League standings |
| `GET /injuries` | Injury report by team |
| `GET /free-agents` | Top available free agents |
| `GET /advice?team=Your+Team` | Full widget data (used by the widget) |

## Project Structure

```
├── main.py              # FastAPI app
├── services/
│   ├── league.py        # ESPN API client (direct HTTP + proxy)
│   └── advice.py        # Daily advice engine
├── widget.js            # Scriptable iOS widget
├── widget_demo.js       # Demo widget with fake data (for previewing)
├── Procfile             # Railway startup
└── requirements.txt
```

## Notes

- ESPN's fantasy API is unofficial and undocumented — it may break without notice
- Railway's shared IPs are blocked by ESPN, hence the residential proxy requirement
- iOS refreshes widgets on its own schedule — setting `refreshAfterDate` to 1 minute won't guarantee 1-minute updates; expect 15–30 minutes in practice
