import datetime
import json
import os
import sys
import urllib.request

LOGIN = os.environ.get("PROFILE_LOGIN", "Sercan0x")
OUT = os.environ.get("PULSE_OUT", "assets/pulse.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
      commitContributionsByRepository(maxRepositories: 5) { repository { name isPrivate } contributions { totalCount } }
    }
    repositories(first: 50, ownerAffiliations: OWNER, privacy: PUBLIC) { nodes { releases { totalCount } } }
  }
}
"""

SANS = "Segoe UI, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Cascadia Mono, Consolas, monospace"


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-pulse"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data or not data.get("data", {}).get("user"):
        raise RuntimeError(json.dumps(data.get("errors"))[:300])
    return data["data"]["user"]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    return longest


def render(u, today):
    c = u["contributionsCollection"]
    weeks = c["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = c["contributionCalendar"]["totalContributions"] + c["restrictedContributionsCount"]
    active = sum(1 for d in days if d["contributionCount"] > 0)
    longest = streaks(days)
    releases = sum(n["releases"]["totalCount"] for n in u["repositories"]["nodes"])
    repos = [(r["repository"]["name"] if not r["repository"]["isPrivate"] else "private work", r["contributions"]["totalCount"]) for r in c["commitContributionsByRepository"]][:4]
    W, H = 1000, 420
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    o.append('<defs><linearGradient id="pcb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f2a3a"/><stop offset="1" stop-color="#0a1a26"/></linearGradient>'
             '<linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#1d6f8f"/><stop offset="1" stop-color="#3ad0ff"/></linearGradient>'
             '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>')
    o.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18" fill="url(#pcb)" stroke="#1d4a60" stroke-width="2"/>')
    for x, y in ((22, 22), (W - 22, 22), (22, H - 22), (W - 22, H - 22)):
        o.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#1d4a60"/>')
    o.append(f'<text x="48" y="62" fill="#ffc94a" font-family="{MONO}" font-size="14" letter-spacing="2">BUILD LOG, LAST 12 MONTHS</text>')
    o.append(f'<text x="{W-48}" y="62" fill="#5f8396" font-family="{MONO}" font-size="12" text-anchor="end">UPDATED {today}</text>')
    o.append(f'<text x="48" y="146" fill="#e8eef4" font-family="{SANS}" font-size="72" font-weight="700" letter-spacing="-2">{total:,}</text>')
    o.append(f'<text x="50" y="176" fill="#b4bdc9" font-family="{SANS}" font-size="17">contributions, public and private</text>')
    stats = [("commits", c["totalCommitContributions"]), ("active days", active), ("longest streak", f"{longest}d"), ("releases", releases)]
    for i, (label, val) in enumerate(stats):
        x = 48 + (i % 2) * 190
        y = 226 + (i // 2) * 56
        o.append(f'<text x="{x}" y="{y}" fill="#3ad0ff" font-family="{SANS}" font-size="26" font-weight="700">{esc(val)}</text>')
        o.append(f'<text x="{x}" y="{y+20}" fill="#5f8396" font-family="{MONO}" font-size="12">{esc(label)}</text>')
    o.append('<path d="M450 92 V300" stroke="#1d4a60" stroke-width="2" stroke-dasharray="4 6"/>')
    o.append(f'<text x="486" y="112" fill="#ffc94a" font-family="{MONO}" font-size="13" letter-spacing="2">WHERE THE COMMITS WENT</text>')
    top = max([n for _, n in repos] or [1])
    for i, (name, n) in enumerate(repos):
        y = 152 + i * 40
        w = max(6, int(330 * n / top))
        o.append(f'<text x="486" y="{y}" fill="#e8eef4" font-family="{SANS}" font-size="16" font-weight="600">{esc(name)}</text>')
        o.append(f'<text x="{W-48}" y="{y}" fill="#e8eef4" font-family="{MONO}" font-size="15" text-anchor="end">{n}</text>')
        o.append(f'<rect x="486" y="{y+8}" width="{W-48-486}" height="5" rx="2.5" fill="#12384b"/>')
        o.append(f'<rect x="486" y="{y+8}" width="{w}" height="5" rx="2.5" fill="{"#3ad0ff" if i == 0 else "#ffc94a"}"/>')
    o.append(f'<text x="48" y="336" fill="#ffc94a" font-family="{MONO}" font-size="13" letter-spacing="2">WEEK BY WEEK</text>')
    counts = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks][-53:]
    peak = max(counts + [1])
    x0, x1, base, hmax = 48, W - 48, 392, 44
    step = (x1 - x0) / max(1, len(counts))
    for i, n in enumerate(counts):
        h = 2 if n == 0 else max(4, round(hmax * n / peak))
        col = "#12384b" if n == 0 else "url(#bar)"
        o.append(f'<rect x="{x0 + i*step + 1:.1f}" y="{base-h}" width="{step-3:.1f}" height="{h}" rx="2" fill="{col}"/>')
    if counts and counts[-1] > 0:
        cx = x0 + (len(counts) - 1) * step + step / 2
        o.append(f'<circle cx="{cx:.1f}" cy="{base-max(4, round(hmax*counts[-1]/peak))-10}" r="5" fill="#3ad0ff"/><circle cx="{cx:.1f}" cy="{base-max(4, round(hmax*counts[-1]/peak))-10}" r="11" fill="#3ad0ff" opacity="0.35" filter="url(#glow)"/>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    today = datetime.date.today().isoformat()
    try:
        svg = render(fetch(token), today)
    except Exception as e:
        print("pulse not updated:", e)
        return
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
