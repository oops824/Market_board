import json, urllib.request, datetime, os

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
cut = (now - datetime.timedelta(days=90)).strftime("%Y-%m-%d")

TFF, LEG = "gpe5-46if", "6dca-aqww"

def rows(ds):
    url = ("https://publicreporting.cftc.gov/resource/%s.json"
           "?$where=report_date_as_yyyy_mm_dd>'%sT00:00:00'&$limit=50000" % (ds, cut))
    req = urllib.request.Request(url, headers={"User-Agent": "market-board"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

def pick(data, kw):
    ms = [r for r in data if kw in (r.get("market_and_exchange_names") or "").upper()]
    if not ms:
        raise ValueError("계약명 매칭 실패")
    dates = sorted({r["report_date_as_yyyy_mm_dd"] for r in ms}, reverse=True)[:2]
    out = []
    for d in dates:
        c = sorted([r for r in ms if r["report_date_as_yyyy_mm_dd"] == d],
                   key=lambda r: float(r.get("open_interest_all") or 0), reverse=True)
        out.append((d[:10], c[0]))
    return out

def net(r, a, b):
    return float(r.get(a) or 0) - float(r.get(b) or 0)

TARGETS = [("나스닥100", "NASDAQ", "tff"), ("S&P500", "S&P 500", "tff"),
           ("비트코인", "BITCOIN", "tff"), ("금", "GOLD", "leg")]

cache, items = {}, []
for ko, kw, kind in TARGETS:
    try:
        ds = TFF if kind == "tff" else LEG
        if ds not in cache:
            cache[ds] = rows(ds)
        p = pick(cache[ds], kw)
        if kind == "tff":
            L, S, label = "lev_money_positions_long_all", "lev_money_positions_short_all", "레버리지펀드"
        else:
            L, S, label = "noncomm_positions_long_all", "noncomm_positions_short_all", "비상업(투기)"
        cur = net(p[0][1], L, S)
        prev = net(p[1][1], L, S) if len(p) > 1 else cur
        cm = "기준일 %s · 3일 지연 데이터" % p[0][0]
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
                               "note": "전주 대비 순포지션 증감 (계약 수)", "items": items})

day = now.strftime("%Y-%m-%d")
for p in ("data.json", "reports/%s.json" % day):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("cot done")
