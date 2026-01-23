#!/usr/bin/env python3
"""
Demo generator for GitHub Risk Inspector.
Creates sample output without hitting GitHub API.
"""
import os, sys, json, webbrowser, sqlite3, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from risk_engine import main, DB, init_db

def demo():
    # Create sample data
    con = init_db()
    
    # Sample risky files
    sample_data = [
        ("src/auth/login.py", 4, "critical", ["High churn", "Core system", "Single author"]),
        ("src/api/endpoints.py", 3, "high", ["High churn", "Active (>5 commits)"]),
        ("middleware/cache.py", 2, "watch", ["High churn"]),
        ("services/user.py", 1, "normal", ["Active (>5 commits)"]),
        ("utils/helpers.py", 5, "critical", ["High churn", "Top 20% churn", "Core system", "24 h spike"]),
    ]
    
    # Insert sample data
    for fn, score, band, reasons in sample_data:
        con.execute("insert or replace into hist(file,score,band,ts) values(?,?,?,?)",
                    (fn, score, band, dt.datetime.utcnow()))
    
    con.commit()
    
    # Generate HTML report
    rows = [{"file": fn, "score": score, "band": band, "reasons": reasons} 
            for fn, score, band, reasons in sample_data]
    
    alerts = [fn for fn, score, band, _ in sample_data if band == "critical"]
    
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Risk Report – Demo</title>
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
  <h1>🚨 GitHub Risk Inspector – Demo</h1>
  <p>Generated {dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>
  <h2>Summary</h2>
  <ul>
    <li>Files analyzed: {len(sample_data)}</li>
    <li>Critical: 2</li>
    <li>High: 1</li>
    <li>Alerts triggered: 2</li>
  </ul>
  {''.join(f'<div class="alert">🔴 Alert: <strong>{a}</strong> – review recommended</div>' for a in alerts)}
  <h2>Top Risky Files</h2>
  {''.join(f'''
  <div class="card {r["band"]}">
    <strong>{r["file"]}</strong> – score {r["score"]}/6 ({r["band"]})
    <div class="reasons">{", ".join(r["reasons"])}</div>
  </div>
  ''' for r in rows)}
</body>
</html>
""".strip()
    
    out = Path("risk_report.html")
    out.write_text(html, encoding="utf8")
    print(f"Demo report generated → {out}")
    return out

if __name__ == "__main__":
    out = demo()
    print(f"\n📊 Opening {out}")
    webbrowser.open(out)
