import json, urllib.request, urllib.parse, datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
TFF, LEG = "gpe5-46if", "6dca-aqww"

def fetch(ds, kw):
    q = urllib.parse.urlencode({
        "$where": "upper(market_and_exchange_names) like '%%%s%%'" % kw,
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "400"})
    url = "https://publicreporting.cftc.gov/resource/%s.json?%s" % (ds, q)
    req = urllib.request.Request(url, headers={"User-Agent": "market-board"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

def latest_two(rows):
    dates = sorted({r["report_date_as_yyyy_mm_dd"] for r in rows}, reverse=True)[:2]
    out = []
    for d in dates:
        c = sorted([r for r in rows if r["report_date_as_yyyy_mm_dd"] == d],
                   key=lambda r: float(r.get("open_interest_all") or 0), reverse=True)
        out.append((d[:10], c[0]))
    return out

def net(r, a, b):
    return float(r.get(a) or 0) - float(r.get(b) or 0)

TARGETS = [("나스닥100", "NASDAQ", "tff"), ("S&P500", "S&P 500", "tff"),
           ("비트코인", "BITCOIN", "tff"), ("금", "GOLD", "leg")]

items = []
for ko, kw, kind in TARGETS:
    try:
        rows = fetch(TFF if kind == "tff" else LEG, kw)
        if not rows:
            raise ValueError("계약명 매칭 실패")
        p = latest_two(rows)
        if kind == "tff":
            L, S, label = "lev_money_positions_long_all", "lev_money_positions_short_all", "레버리지펀드"
        else:
            L, S, label = "noncomm_positions_long_all", "noncomm_positions_short_all", "비상업(투기)"
        cur = net(p[0][1], L, S)
        if len(p) < 2:
            raise ValueError("전주 데이터 없음")
        prev = net(p[1][1], L, S)
        cm = "%s · 전주(%s) 대비 · %s" % (p[0][0], p[1][0],
                                        (p[0][1].get("market_and_exchange_names") or "")[:40])
        if kind == "tff":
            am = net(p[0][1], "asset_mgr_positions_long_all", "asset_mgr_positions_short_all")
            cm += " · 자산운용사 순{} {:,.0f}".format("매수" if am >= 0 else "매도", abs(am))
        items.append({"name": ko,
                      "value": "{} 순{} {:,.0f}".format(label, "매수" if cur >= 0 else "매도", abs(cur)),
                      "change": "{:+,.0f}".format(cur - prev),
                      "comment": cm})
    except Exception as e:
        items.append({"name": ko, "value": "수집 실패", "change": "", "comment": str(e)[:90]})

with open("data.json", encoding="utf-8") as f:
    payload = json.load(f)
payload["sections"].insert(1, {"title": "CFTC COT 포지셔닝",
                               "note": "전주 대비 순포지션 증감 (계약 수) · 약 3일 지연", "items": items})

day = now.strftime("%Y-%m-%d")
for p in ("data.json", "reports/%s.json" % day):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("cot done")
