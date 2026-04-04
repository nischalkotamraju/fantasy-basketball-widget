const API_BASE_URL = "YOUR_RAILWAY_URL"
const MY_TEAM = "YOUR_TEAM_NAME"

async function fetchJSON(path) {
  try {
    const req = new Request(API_BASE_URL + path)
    req.headers = { "Accept": "application/json" }
    return await req.loadJSON()
  } catch(e) {
    return null
  }
}

const widget = new ListWidget()
widget.backgroundColor = new Color("#111111")
widget.setPadding(14, 16, 14, 16)
widget.url = API_BASE_URL

const data = await fetchJSON("/advice?team=" + encodeURIComponent(MY_TEAM))

const hdr = widget.addStack()
hdr.layoutHorizontally()
const ttl = hdr.addText("Fantasy")
ttl.font = Font.boldSystemFont(14)
ttl.textColor = new Color("#FFFFFF")
hdr.addSpacer()
const dt = hdr.addText(data ? data.date : "")
dt.font = Font.systemFont(12)
dt.textColor = new Color("#6B7280")
widget.addSpacer(6)

if (!data) {
  const err = widget.addText("Could not connect")
  err.font = Font.systemFont(12)
  err.textColor = new Color("#F87171")
} else {

  // Matchups - 3 col: home left | score center | away right
  addSec(widget, "MATCHUPS")
  for (const m of (data.matchups || [])) {
    const hw = m.home_score > m.away_score
    const aw = m.away_score > m.home_score
    const row = widget.addStack()
    row.layoutHorizontally()
    row.spacing = 0

    const hBox = row.addStack()
    hBox.layoutHorizontally()
    hBox.size = new Size(100, 0)
    const ht = hBox.addText(clip(m.home_team, 11))
    ht.font = hw ? Font.boldSystemFont(12) : Font.systemFont(12)
    ht.textColor = hw ? new Color("#4ADE80") : new Color("#6B7280")
    ht.lineLimit = 1
    hBox.addSpacer()

    const sBox = row.addStack()
    sBox.layoutHorizontally()
    sBox.size = new Size(110, 0)
    sBox.addSpacer()
    const hs = sBox.addText(m.home_score.toFixed(1))
    hs.font = Font.boldSystemFont(12)
    hs.textColor = hw ? new Color("#4ADE80") : new Color("#9CA3AF")
    const sep = sBox.addText("  -  ")
    sep.font = Font.systemFont(11)
    sep.textColor = new Color("#4B5563")
    const as_ = sBox.addText(m.away_score.toFixed(1))
    as_.font = Font.boldSystemFont(12)
    as_.textColor = aw ? new Color("#4ADE80") : new Color("#9CA3AF")
    sBox.addSpacer()

    row.addSpacer()
    const at = row.addText(clip(m.away_team, 11))
    at.font = aw ? Font.boldSystemFont(12) : Font.systemFont(12)
    at.textColor = aw ? new Color("#4ADE80") : new Color("#6B7280")
    at.lineLimit = 1

    widget.addSpacer(2)
  }

  widget.addSpacer(6)

  // Bench + Injuries
  const advice = data.my_team_advice
  const hasSit = advice && advice.sit_suggestions && advice.sit_suggestions.length > 0
  const hasInj = advice && advice.injured_starters && advice.injured_starters.length > 0

  if (hasSit || hasInj) {
    const cols = widget.addStack()
    cols.layoutHorizontally()

    const lc = cols.addStack()
    lc.layoutVertically()
    const lh = lc.addText("BENCH TODAY")
    lh.font = Font.boldSystemFont(10)
    lh.textColor = new Color("#6B7280")
    lc.addSpacer(3)
    if (hasSit) {
      for (const s of advice.sit_suggestions.slice(0, 4)) {
        const t = lc.addText(s.name)
        t.font = Font.systemFont(12)
        t.textColor = new Color("#FACC15")
        t.lineLimit = 1
        lc.addSpacer(3)
      }
    }

    cols.addSpacer(12)

    const rc = cols.addStack()
    rc.layoutVertically()
    const rh = rc.addText("MY INJURIES")
    rh.font = Font.boldSystemFont(10)
    rh.textColor = new Color("#6B7280")
    rc.addSpacer(3)
    if (hasInj) {
      for (const p of advice.injured_starters.slice(0, 4)) {
        const row2 = rc.addStack()
        row2.layoutHorizontally()
        row2.spacing = 0
        const nt = row2.addText(abbrev(p.name))
        nt.font = Font.systemFont(12)
        nt.textColor = new Color("#FFFFFF")
        nt.lineLimit = 1
        row2.addSpacer()
        const color = p.status === "DAY_TO_DAY" ? "#FACC15"
          : (p.status === "SUSPENSION" || p.status === "SUSPENDED") ? "#A78BFA"
          : "#F87171"
        const lbl = p.return_date ? p.status_short + " " + p.return_date : p.status_short
        const st = row2.addText(lbl)
        st.font = Font.boldSystemFont(12)
        st.textColor = new Color(color)
        rc.addSpacer(3)
      }
    }
    widget.addSpacer(6)
  }

  // Free Agents
  addSec(widget, "TOP FREE AGENTS")
  for (const p of (data.top_free_agents || []).slice(0, 5)) {
    const row = widget.addStack()
    row.layoutHorizontally()
    const nm = row.addText(clip(p.name, 22))
    nm.font = Font.systemFont(12)
    nm.textColor = new Color("#FFFFFF")
    nm.lineLimit = 1
    row.addSpacer()
    const pos = row.addText(p.position + "  ")
    pos.font = Font.systemFont(11)
    pos.textColor = new Color("#6B7280")
    const pts = row.addText(p.avg_points + " ppg")
    pts.font = Font.boldSystemFont(12)
    pts.textColor = new Color("#60A5FA")
    widget.addSpacer(2)
  }
}

widget.addSpacer()
const upd = widget.addText("Updated " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))
upd.font = Font.systemFont(10)
upd.textColor = new Color("#4B5563")
widget.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)

if (config.runsInWidget) { Script.setWidget(widget) } else { await widget.presentLarge() }
Script.complete()

function addSec(w, t) {
  const l = w.addText(t)
  l.font = Font.boldSystemFont(10)
  l.textColor = new Color("#6B7280")
  w.addSpacer(3)
}
function clip(s, max) {
  return s && s.length > max ? s.slice(0, max - 1) + "..." : (s || "")
}
function abbrev(s) {
  if (!s) return ""
  const p = s.trim().split(" ")
  return p.length < 2 ? s : p[0][0] + ". " + p.slice(1).join(" ")
}
