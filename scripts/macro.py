import json, urllib.request, urllib.parse, csv, io, datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def fail(name, e):
    return {"name": name, "value": "수집 실패", "change": "", "comment": str(e)[:90]}

# ---------- FRED ----------
def yh(sym, rng="1y"):
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/"
                       "%s?range=%s&interval=1d" % (urllib.parse.quote(sym), rng), 30))
    r = j["chart"]["result"][0]
    ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
    out = [(datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), float(c))
           for t, c in zip(ts, cl) if c is not None]
    if not out:
        raise ValueError("빈 응답")
    return out

def ago(series, days):
    target = datetime.datetime.strptime(series[-1][0], "%Y-%m-%d") - datetime.timedelta(days=days)
    prev = [p for p in series if datetime.datetime.strptime(p[0], "%Y-%m-%d") <= target]
    return prev[-1][1] if prev else series[0][1]

def pctile(series, v, days=365):
    cut = datetime.datetime.strptime(series[-1][0], "%Y-%m-%d") - datetime.timedelta(days=days)
    vals = [p[1] for p in series if datetime.datetime.strptime(p[0], "%Y-%m-%d") >= cut]
    if len(vals) < 20:
        return None
    return sum(1 for x in vals if x <= v) / len(vals) * 100

# (표시명, 야후 티커, 단위, 소수점, 설명)
YH_ITEMS = [
    ("10년 국채금리", "^TNX", "%", 2, "성장주 밸류에이션 할인율"),
    ("2년 국채금리", "^IRX", "%", 2, "연준 정책 기대 반영"),
    ("달러지수 DXY", "DX-Y.NYB", "", 2, "강세=위험자산·원자재 역풍"),
    ("변동성 VIX", "^VIX", "", 2, "단기 스트레스"),
    ("하이일드 HYG", "HYG", "$", 2, "신용 위험선호. 하락=경계"),
    ("장기채 TLT", "TLT", "$", 2, "금리 방향 대리지표"),
    ("물가연동채 TIP", "TIP", "$", 2, "실질금리 대리지표. 하락=실질금리 상승"),
]

def macro_items():
    out, cache = [], {}
    for ko, sym, unit, dec, note in YH_ITEMS:
        try:
            s = yh(sym)
            cache[sym] = s
            d, v = s[-1]
            w = v - ago(s, 7)
            p = pctile(s, v)
            cm = "%s · %s" % (d, note)
            if p is not None:
                cm += " · 1년 백분위 %.0f%%" % p
            out.append({"name": ko,
                        "value": ("{:,.%df}" % dec).format(v) + unit,
                        "change": ("{:+.%df}" % dec).format(w) + unit + " (1주)",
                        "comment": cm})
        except Exception as e:
            out.append(fail(ko, e))

    # 장단기 금리차 (^TNX, ^IRX 는 실제값의 10배로 제공됨)
    try:
        t, i = cache["^TNX"], cache["^IRX"]
        cur = (t[-1][1] - i[-1][1]) / 10
        prev = (ago(t, 7) - ago(i, 7)) / 10
        out.append({"name": "장단기 금리차 (10y-3m)",
                    "value": "{:+.2f}%p".format(cur),
                    "change": "{:+.2f}%p (1주)".format(cur - prev),
                    "comment": "%s · 축소=베어 플래트닝 경계" % t[-1][0]})
    except Exception as e:
        out.append(fail("장단기 금리차", e))

    # 신용 스프레드 대용: HYG / TLT 비율
    try:
        h, l = cache["HYG"], cache["TLT"]
        cur = h[-1][1] / l[-1][1]
        prev = ago(h, 21) / ago(l, 21)
        hist = [(d, hv / lv) for (d, hv), (_, lv) in zip(h, l)]
        p = pctile(hist, cur)
        out.append({"name": "위험선호 HYG/TLT",
                    "value": "{:.3f}".format(cur),
                    "change": "{:+.2f}% (1개월)".format((cur / prev - 1) * 100),
                    "comment": "%s · 상승=위험선호 · 1년 백분위 %s" % (
                        h[-1][0], "%.0f%%" % p if p is not None else "-")})
    except Exception as e:
        out.append(fail("위험선호 HYG/TLT", e))

    # 시장 폭: RSP(동일가중) / SPY(시총가중)
    try:
        r, s = yh("RSP"), yh("SPY")
        cur = r[-1][1] / s[-1][1]
        prev = ago(r, 63) / ago(s, 63)
        out.append({"name": "시장 폭 RSP/SPY",
                    "value": "{:.4f}".format(cur),
                    "change": "{:+.2f}% (3개월)".format((cur / prev - 1) * 100),
                    "comment": "%s · 하락=소수 대형주 쏠림 심화" % r[-1][0]})
    except Exception as e:
        out.append(fail("시장 폭 RSP/SPY", e))

    # 반도체 주도력: SMH / SPY
    try:
        m, s = yh("SMH"), yh("SPY")
        cur = m[-1][1] / s[-1][1]
        prev = ago(m, 63) / ago(s, 63)
        out.append({"name": "반도체 주도력 SMH/SPY",
                    "value": "{:.4f}".format(cur),
                    "change": "{:+.2f}% (3개월)".format((cur / prev - 1) * 100),
                    "comment": "%s · 상승=반도체가 지수 주도" % m[-1][0]})
    except Exception as e:
        out.append(fail("반도체 주도력", e))

    return out
  # ---------- 스테이블코인 ----------
def stables():
    out = []
    try:
        j = json.loads(get("https://stablecoins.llama.fi/stablecoincharts/all"
                           "?stablecoin=undefined", 60))
        def tot(row):
            c = row.get("totalCirculatingUSD") or {}
            return sum(float(v or 0) for v in c.values())
        pts = [(int(r["date"]), tot(r)) for r in j if tot(r) > 0][-120:]
        cur = pts[-1][1]
        def back(n):
            return pts[max(0, len(pts) - 1 - n)][1]
        d = datetime.datetime.utcfromtimestamp(pts[-1][0]).strftime("%Y-%m-%d")
        out.append({"name": "스테이블코인 총 발행량",
                    "value": "{:,.1f}B$".format(cur / 1e9),
                    "change": "{:+.2f}% (30일)".format((cur / back(30) - 1) * 100),
                    "comment": "%s · 7일 %+.2f%% · 증가=대기자금 유입" % (
                        d, (cur / back(7) - 1) * 100)})
    except Exception as e:
        out.append(fail("스테이블코인 총 발행량", e))
    try:
        j = json.loads(get("https://stablecoins.llama.fi/stablecoins?includePrices=true", 60))
        ps = sorted(j.get("peggedAssets", []),
                    key=lambda p: float((p.get("circulating") or {}).get("peggedUSD") or 0),
                    reverse=True)[:3]
        for p in ps:
            c = float((p.get("circulating") or {}).get("peggedUSD") or 0)
            pm = float((p.get("circulatingPrevMonth") or {}).get("peggedUSD") or 0)
            out.append({"name": p.get("symbol") or p.get("name"),
                        "value": "{:,.1f}B$".format(c / 1e9),
                        "change": "{:+.2f}% (30일)".format((c / pm - 1) * 100) if pm else "",
                        "comment": "개별 스테이블코인 발행량"})
    except Exception as e:
        out.append(fail("주요 스테이블코인", e))
    return out

# ---------- 코인베이스 프리미엄 ----------
def cb_premium():
    out = []
    pairs = [("BTC", "BTC-USD", "BTCUSDT"), ("ETH", "ETH-USD", "ETHUSDT")]
    for ko, cb, bn in pairs:
        try:
            c = float(json.loads(get(
                "https://api.exchange.coinbase.com/products/%s/ticker" % cb))["price"])
            b = float(json.loads(get(
                "https://api.binance.com/api/v3/ticker/price?symbol=%s" % bn))["price"])
            gap = (c / b - 1) * 100
            out.append({"name": "%s 코인베이스 프리미엄" % ko,
                        "value": "{:+.3f}%".format(gap),
                        "change": "{:+.0f}bp".format(gap * 100),
                        "comment": "코인베이스 {:,.2f} vs 바이낸스 {:,.2f} · 양수=미국 매수 우위".format(c, b)})
        except Exception as e:
            out.append(fail("%s 코인베이스 프리미엄" % ko, e))
    return out

with open("data.json", encoding="utf-8") as f:
    payload = json.load(f)

payload["sections"].insert(0, {"title": "매크로 · 유동성",
                               "note": "야후 파이낸스 · 전일 종가 기준", "items": macro_items()})
payload["sections"].append({"title": "스테이블코인 발행량",
                            "note": "암호화폐 대기자금", "items": stables()})
payload["sections"].append({"title": "코인베이스 프리미엄",
                            "note": "실시간 · 미국 기관 매수 강도", "items": cb_premium()})

day = now.strftime("%Y-%m-%d")
for p in ("data.json", "reports/%s.json" % day):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("macro done")
