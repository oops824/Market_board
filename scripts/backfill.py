import json, urllib.request, urllib.parse, datetime, os

UA = {"User-Agent": "Mozilla/5.0 (market-board)"}
START = "2026-08-01"

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# 현재 기록에 들어있는 프로토콜 이름 수집
try:
    with open("history/trend.json", encoding="utf-8") as f:
        hist = json.load(f)
except Exception:
    hist = []

names = set()
for h in hist:
    for n in (h.get("defi") or {}):
        names.add(n)
if not names:
    raise SystemExit("기존 기록이 없습니다. 먼저 macro.py를 한 번 실행하세요.")

print("대상 프로토콜:", ", ".join(sorted(names)))

# DeFiLlama 프로토콜 목록에서 slug 찾기
ov = get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true"
         "&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue")
slug = {}
for p in ov.get("protocols", []):
    nm = p.get("name")
    if nm in names:
        slug[nm] = p.get("module") or p.get("slug") or nm

start_ts = int(datetime.datetime.strptime(START, "%Y-%m-%d")
               .replace(tzinfo=datetime.timezone.utc).timestamp())

daily = {}   # {날짜: {프로토콜: 값}}
for nm in sorted(names):
    sg = slug.get(nm)
    if not sg:
        print("건너뜀 (slug 없음):", nm)
        continue
    try:
        j = get("https://api.llama.fi/summary/fees/%s?dataType=dailyRevenue"
                % urllib.parse.quote(str(sg)))
        chart = j.get("totalDataChart") or []
        for row in chart:
            ts, val = int(row[0]), float(row[1] or 0)
            if ts < start_ts:
                continue
            d = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            daily.setdefault(d, {})[nm] = round(val / 1e6, 2)
        print("완료:", nm, len(chart), "행")
    except Exception as e:
        print("실패:", nm, str(e)[:80])

# 기존 기록과 병합 (기존 값이 우선)
by_date = {h["date"]: h for h in hist}
for d, vals in daily.items():
    rec = by_date.get(d) or {"date": d}
    merged = dict(vals)
    merged.update(rec.get("defi") or {})
    rec["defi"] = merged
    by_date[d] = rec

out = sorted(by_date.values(), key=lambda h: h["date"])[-400:]
os.makedirs("history", exist_ok=True)
with open("history/trend.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("총 %d일치 저장" % len(out))
# ---------- 매크로 지표 과거 채우기 ----------
def yh_hist(sym, rng="1y"):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1d"
           % (urllib.parse.quote(sym), rng))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read().decode())
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = {}
    for t, c in zip(res["timestamp"], q["close"]):
        if c is None:
            continue
        d = datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        out[d] = float(c)
    return out

SIMPLE = [("^TNX", "tnx"), ("^IRX", "irx"), ("DX-Y.NYB", "dxy"), ("^VIX", "vix")]
RATIOS = [("HYG", "TLT", "risk"), ("RSP", "SPY", "breadth"), ("SMH", "SPY", "smh")]

series = {}
for sym, key in SIMPLE:
    try:
        series[key] = yh_hist(sym)
        print("완료:", sym, len(series[key]), "일")
    except Exception as e:
        print("실패:", sym, str(e)[:60])

cache = {}
for a, b, key in RATIOS:
    try:
        for s in (a, b):
            if s not in cache:
                cache[s] = yh_hist(s)
        ha, hb = cache[a], cache[b]
        series[key] = {d: ha[d] / hb[d] for d in ha if d in hb and hb[d]}
        print("완료:", key, len(series[key]), "일")
    except Exception as e:
        print("실패:", key, str(e)[:60])

# 기존 기록에 병합 (기존 값 우선)
try:
    with open("history/trend.json", encoding="utf-8") as f:
        cur = json.load(f)
except Exception:
    cur = []
by_date = {h["date"]: h for h in cur}

for key, vals in series.items():
    for d, v in vals.items():
        if d < START:
            continue
        rec = by_date.get(d) or {"date": d}
        if key not in rec:
            rec[key] = round(v, 4)
        by_date[d] = rec

final = sorted(by_date.values(), key=lambda h: h["date"])[-400:]
with open("history/trend.json", "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False)
print("매크로 병합 후 총 %d일" % len(final))
