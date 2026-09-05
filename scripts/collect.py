import json, urllib.request, datetime, os, csv, io

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)

def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "market-board"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def fail(name, e):
    return {"name": name, "value": "수집 실패", "change": "", "comment": str(e)[:90]}

def yahoo(sym):
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/"
                       "%s?range=1mo&interval=1d" % sym))
    r = j["chart"]["result"][0]
    cl = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    d = datetime.datetime.utcfromtimestamp(r["timestamp"][-1]).strftime("%Y-%m-%d")
    if len(cl) < 6:
        raise ValueError("데이터 부족")
    return cl[-6:], d

def stooq(sym):
    txt = get("https://stooq.com/q/d/l/?s=%s.us&i=d" % sym.lower())
    rows = [r for r in csv.DictReader(io.StringIO(txt))
            if r.get("Close") not in (None, "", "N/D")][-6:]
    if len(rows) < 6:
        raise ValueError("Stooq 응답 이상")
    return [float(r["Close"]) for r in rows], rows[-1]["Date"]
    
# (티커, 한글명, [대장주 3종목])
ETFS = [
    ("SMH", "반도체", ["NVDA", "TSM", "AVGO"]),
    ("XLK", "기술", ["AAPL", "MSFT", "AVGO"]),
    ("IGV", "소프트웨어", ["MSFT", "ORCL", "CRM"]),
    ("ITA", "방산", ["GE", "RTX", "LMT"]),
    ("ARKX", "우주", ["RKLB", "LHX", "IRDM"]),
    ("LIT", "배터리", ["TSLA", "ALB", "SQM"]),
    ("GRID", "AI인프라·전력망", ["ETN", "PWR", "VRT"]),
    ("XLU", "유틸리티(전력)", ["NEE", "CEG", "VST"]),
]

def etf():
    out = []
    for sym, ko, leaders in ETFS:
        cl = d = None
        errs = []
        for fn in (yahoo, stooq):
            try:
                cl, d = fn(sym)
                break
            except Exception as e:
                errs.append("%s:%s" % (fn.__name__, str(e)[:40]))
        if cl is None:
            out.append(fail("%s (%s)" % (ko, sym), " / ".join(errs)))
        else:
            out.append({"name": "%s (%s)" % (ko, sym),
                        "value": "{:,.2f}$".format(cl[-1]),
                        "change": "{:+.2f}%".format((cl[-1] / cl[0] - 1) * 100),
                        "comment": "%s 종가 · 5거래일 변화" % d})
        for lsym in leaders:
            try:
                lcl, ld = yahoo(lsym)
                out.append({"name": "  └ %s" % lsym,
                            "value": "{:,.2f}$".format(lcl[-1]),
                            "change": "{:+.2f}%".format((lcl[-1] / lcl[0] - 1) * 100),
                            "comment": "%s 대장주 · 5거래일 변화" % ko})
            except Exception as e:
                out.append({"name": "  └ %s" % lsym, "value": "수집 실패",
                            "change": "", "comment": str(e)[:60]})
    return out
    
def hyperliquid():
    try:
        raw = json.loads(post("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"}))
        meta, ctxs, want, out = raw[0]["universe"], raw[1], ["BTC", "ETH", "SOL", "HYPE"], []
        for m, c in zip(meta, ctxs):
            if m["name"] in want:
                px = float(c.get("markPx") or 0)
                oi = float(c.get("openInterest") or 0) * px
                out.append({"name": m["name"],
                            "value": "OI {:,.0f}M$".format(oi / 1e6),
                            "change": "{:+.4f}%".format(float(c.get("funding") or 0) * 100),
                            "comment": "마크가격 {:,.2f}$ · 시간당 펀딩비".format(px)})
        return out or [fail("하이퍼리퀴드", "대상 코인 없음")]
    except Exception as e:
        return [fail("하이퍼리퀴드", e)]

def llama():
    try:
        raw = json.loads(get("https://api.llama.fi/overview/fees?excludeTotalDataChart=true"
                             "&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue"))
        ps = sorted(raw.get("protocols", []),
                    key=lambda p: p.get("total24h") or 0, reverse=True)[:8]
        return [{"name": p.get("name", "?"),
                 "value": "{:,.2f}M$".format((p.get("total24h") or 0) / 1e6),
                 "change": "{:+.1f}%".format(p.get("change_1d") or 0),
                 "comment": "%s · 24시간 프로토콜 수익" % (p.get("category") or "")}
                for p in ps] or [fail("DeFiLlama", "데이터 없음")]
    except Exception as e:
        return [fail("DeFiLlama", e)]

payload = {
    "updated": now.strftime("%Y-%m-%d %H:%M KST"),
    "summary": "자동 수집 완료.",
    "sections": [
        {"title": "섹터 ETF 가격", "note": "최근 5거래일 변화", "items": etf()},
        {"title": "하이퍼리퀴드 펀딩비 · 미결제약정", "note": "실시간", "items": hyperliquid()},
        {"title": "DeFiLlama 프로토콜 수익 랭킹", "note": "24시간 기준 상위 8", "items": llama()},
    ],
}

os.makedirs("reports", exist_ok=True)
day = now.strftime("%Y-%m-%d")
for path in ("data.json", "reports/%s.json" % day):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("collect done")
