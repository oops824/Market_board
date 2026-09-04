import json, urllib.request, csv, io, datetime

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
def fred(sid, days=400):
    st = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    txt = get("https://fred.stlouisfed.org/graph/fredgraph.csv"
              "?id=%s&cosd=%s" % (sid, st))
    rows = list(csv.reader(io.StringIO(txt)))
    out = []
    for r in rows[1:]:
        if len(r) < 2:
            continue
        v = r[1].strip()
        if v in ("", "."):
            continue
        out.append((r[0].strip(), float(v)))
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

FRED_ITEMS = [
    ("하이일드 스프레드", "BAMLH0A0HYM2", "%", 2,
     "위험자산 조기경보. 확대=신용 경계"),
    ("10년 실질금리", "DFII10", "%", 2,
     "금·성장주 밸류에이션 핵심 변수"),
    ("장단기 금리차 10y-2y", "T10Y2Y", "%p", 2,
     "베어 플래트닝/스티프닝 확인"),
    ("달러지수 (광의)", "DTWEXBGS", "", 2,
     "강세=위험자산·원자재 역풍"),
]

def macro_items():
    out = []
    for ko, sid, unit, dec, note in FRED_ITEMS:
        try:
            s = fred(sid)
            d, v = s[-1]
            w = v - ago(s, 7)
            p = pctile(s, v)
            cm = "%s · %s" % (d, note)
            if p is not None:
                cm += " · 1년 백분위 %.0f%%" % p
            out.append({"name": ko,
                        "value": ("{:,.%df}%s" % dec).format(v, unit),
                        "change": ("{:+.%df}%s (1주)" % dec).format(w, unit),
                        "comment": cm})
        except Exception as e:
            out.append(fail(ko, e))
    # 순유동성 = 연준 자산 - 역레포 - 재무부계정
    try:
        wal, rrp, tga = fred("WALCL", 500), fred("RRPONTSYD", 500), fred("WTREGEN", 500)
        def bn(s, scale):
            return s[-1][1] * scale, ago(s, 28) * scale
        w0, w1 = bn(wal, 0.001)      # 백만$ -> 십억$
        r0, r1 = bn(rrp, 1.0)        # 십억$
        t0, t1 = bn(tga, 1.0)        # 십억$
        cur, prev = w0 - r0 - t0, w1 - r1 - t1
        out.append({"name": "연준 순유동성",
                    "value": "{:,.0f}B$".format(cur),
                    "change": "{:+,.0f}B$ (4주)".format(cur - prev),
                    "comment": "%s · 연준자산-역레포-TGA · 증가=위험자산 우호" % wal[-1][0]})
    except Exception as e:
        out.append(fail("연준 순유동성", e))
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
                               "note": "FRED · 발표 지연 있음", "items": macro_items()})
payload["sections"].append({"title": "스테이블코인 발행량",
                            "note": "암호화폐 대기자금", "items": stables()})
payload["sections"].append({"title": "코인베이스 프리미엄",
                            "note": "실시간 · 미국 기관 매수 강도", "items": cb_premium()})

day = now.strftime("%Y-%m-%d")
for p in ("data.json", "reports/%s.json" % day):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("macro done")
