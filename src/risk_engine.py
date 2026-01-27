#!/usr/bin/env python3
"""
Lightweight risk engine – 250 lines, zero deps except sqlite3 & requests.
"""
import os, json, sqlite3, math, requests, subprocess, datetime as dt
from pathlib import Path
from collections import defaultdict, Counter

DB = Path(".github/risk_scoring.db")
CORE = {"src/auth", "src/api", "middleware", "services"}
EXCLUDE = {"test", "vendor", "node_modules", ".md", ".json", ".lock"}
MAX_SCORE = 6

# ---------- utils ----------
def _run(cmd): return subprocess.check_output(cmd, text=True).strip()
def _api(url, tok, params=None):
    h = {"Accept": "application/vnd.github.v3+json"}
    if tok: h["Authorization"] = f"token {tok}"
    r = requests.get(url, headers=h, params=params)
    return r.json() if r.status_code == 200 else []

# ---------- data ----------
def commits_since(owner, repo, tok, days=30):
    since = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    return _api(url, tok, {"since": since, "per_page": 100})

def file_churns(owner, repo, tok, commits):
    churn, counts, authors = defaultdict(int), defaultdict(int), defaultdict(set)
    for c in commits:
        sha, date = c["sha"], c["commit"]["author"]["date"]
        details = _api(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}", tok)
        for f in details.get("files", []):
            fn = f["filename"]
            if any(x in fn for x in EXCLUDE): continue
            churn[fn] += f.get("additions", 0) + f.get("deletions", 0)
            counts[fn] += 1
            authors[fn].add(c["author"]["login"] if c["author"] else "unknown")
    return churn, counts, authors

# ---------- scoring ----------
def score_file(fn, churn, cnt, authors, avg_churn, top20, commits_24h):
    s, reasons = 0, []
    # structural
    if churn[fn] > avg_churn:
        s += 2; reasons.append("High churn")
    if fn in top20:
        s += 1; reasons.append("Top 20% churn")
    # temporal
    if cnt[fn] > 5:
        s += 1; reasons.append("Active (>5 commits)")
    if _24h_spike(fn, commits_24h):
        s += 1; reasons.append("24 h spike")
    # centrality
    if any(c in fn for c in CORE):
        s += 1; reasons.append("Core system")
    # bus factor
    if len(authors[fn]) == 1:
        s += 1; reasons.append("Single author")
    band = "normal" if s <= 1 else "watch" if s <= 3 else "high" if s == 4 else "critical"
    return {"file": fn, "score": s, "band": band, "reasons": reasons}

def _24h_spike(fn, commits):
    files = [f for c in commits for f in c.get("files", []) if f["filename"] == fn]
    return len(files) >= 2

# ---------- persistence ----------
def init_db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("create table if not exists hist(file, score, band, ts, primary key(file, ts))")
    return con

def streak(con, fn, band):
    cur = con.execute("select band from hist where file=? order by ts desc limit 2", (fn,))
    last_two = [r[0] for r in cur]
    return last_two.count(band) if len(last_two) == 2 else 0

# ---------- main ----------
def main(repo, token):
    owner, name = repo.split("/")
    print(f"🔍 Analyzing {owner}/{name} ...")
    commits = commits_since(owner, name, token, 30)
    churn, cnt, authors = file_churns(owner, name, token, commits)
    if not churn:
        print("No source files touched in last 30 days."); exit(0)

    avg = sum(churn.values()) / len(churn)
    top20 = set(sorted(churn, key=churn.get, reverse=True)[:max(1, len(churn)//5)])
    con = init_db()

    # Pre-filter commits for 24h spike check
    cutoff_24h = (dt.datetime.utcnow() - dt.timedelta(days=1)).isoformat()
    commits_24h = [c for c in commits if c["commit"]["author"]["date"] > cutoff_24h]

    rows, alerts = [], []
    for fn in churn:
        sc = score_file(fn, churn, cnt, authors, avg, top20, commits_24h)
        con.execute("insert or replace into hist(file,score,band,ts) values(?,?,?,?)",
                    (fn, sc["score"], sc["band"], dt.datetime.utcnow()))
        rows.append(sc)
        if sc["band"] == "critical" and streak(con, fn, "critical") >= 2:
            alerts.append(fn)

    con.commit()
    html = _render_html(rows, alerts, repo)
    out = Path("risk_report.html")
    out.write_text(html, encoding="utf8")
    return out

# ---------- html ----------
def _render_html(rows, alerts, repo):
    crit = [r for r in rows if r["band"] == "critical"]
    high = [r for r in rows if r["band"] == "high"]
    top = sorted(rows, key=lambda x: x["score"], reverse=True)[:10]
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Risk Report – {repo}</title>
  <style>
    body{{font-family:system-ui, sans-serif; margin:2rem;}}
    .card{{border:1px solid #ddd; border-radius:6px; padding:1rem; margin-bottom:1rem;}}
    .critical{{border-left:6px solid #d73a49;}}
    .high{{border-left:6px solid #e36209;}}
    .reasons{{color:#555; font-size:0.9rem;}}
    .alert{{background:#fff5f5; border:1px solid #fdb8c0; padding:0.8rem; border-radius:4px;}}
  </style>
</head>
<body>
  <h1>🚨 GitHub Risk Inspector – {repo}</h1>
  <p>Generated {dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>
  <h2>Summary</h2>
  <ul>
    <li>Files analyzed: {len(rows)}</li>
    <li>Critical: {len(crit)}</li>
    <li>High: {len(high)}</li>
    <li>Alerts triggered: {len(alerts)}</li>
  </ul>
  {''.join(f'<div class="alert">🔴 Alert: <strong>{a}</strong> – review recommended</div>' for a in alerts)}
  <h2>Top Risky Files</h2>
  {''.join(f'''
  <div class="card {r["band"]}">
    <strong>{r["file"]}</strong> – score {r["score"]}/{MAX_SCORE} ({r["band"]})
    <div class="reasons">{', '.join(r["reasons"])}</div>
  </div>
  ''' for r in top)}
</body>
</html>
""".strip()

if __name__ == "__main__":
    import sys, os
    repo = sys.argv[1] if len(sys.argv) > 1 else input("repo (owner/name): ")
    token = os.getenv("GITHUB_TOKEN", "")
    out = main(repo, token)
    print(f"\n📊 Report → {out}")
