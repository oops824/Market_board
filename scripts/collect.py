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
    
# (티커, 한글명, [(대장주 티커, 한글명), ...])
ETFS = [
    ("SMH", "반도체", [("NVDA", "엔비디아"), ("TSM", "TSMC"), ("AVGO", "브로드컴")]),
    ("XLK", "기술", [("AAPL", "애플"), ("MSFT", "마이크로소프트"), ("AVGO", "브로드컴")]),
    ("IGV", "소프트웨어", [("MSFT", "마이크로소프트"), ("ORCL", "오라클"), ("CRM", "세일즈포스")]),
    ("ITA", "방산", [("GE", "GE에어로스페이스"), ("RTX", "RTX"), ("LMT", "록히드마틴")]),
    ("ARKX", "우주", [("RKLB", "로켓랩"), ("LHX", "L3해리스"), ("IRDM", "이리듐")]),
    ("LIT", "배터리", [("TSLA", "테슬라"), ("ALB", "앨버말"), ("SQM", "SQM")]),
    ("GRID", "AI인프라·전력망", [("ETN", "이튼"), ("PWR", "콰나서비스"), ("VRT", "버티브")]),
    ("XLU", "유틸리티(전력)", [("NEE", "넥스트에라"), ("CEG", "콘스텔레이션"), ("VST", "비스트라")]),
]

def yahoo3(sym):
    """종가 리스트와 마지막 날짜 반환 (약 3개월치)"""
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/"
                       "%s?range=3mo&interval=1d" % sym))
    r = j["chart"]["result"][0]
    cl = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    d = datetime.datetime.utcfromtimestamp(r["timestamp"][-1]).strftime("%Y-%m-%d")
    if len(cl) < 6:
        raise ValueError("데이터 부족")
    return cl, d

def chg(cl, n):
    if len(cl) <= n:
        return None
    return (cl[-1] / cl[-1 - n] - 1) * 100

def row(label, cl, d, note):
    c5, c20 = chg(cl, 5), chg(cl, 20)
    ch = "5일 {:+.2f}%".format(c5) if c5 is not None else ""
    if c20 is not None:
        ch += " / 20일 {:+.2f}%".format(c20)
    return {"name": label,
            "value": "{:,.2f}$".format(cl[-1]),
            "change": ch,
            "comment": "%s 종가 · %s" % (d, note)}

def etf():
    out = []
    for sym, ko, leaders in ETFS:
        try:
            cl, d = yahoo3(sym)
            out.append(row("%s (%s)" % (ko, sym), cl, d, "섹터 ETF"))
        except Exception as e:
            out.append(fail("%s (%s)" % (ko, sym), e))
        for lsym, lko in leaders:
            try:
                lcl, ld = yahoo3(lsym)
                out.append(row("  └ %s (%s)" % (lko, lsym), lcl, ld, "%s 대장주" % ko))
            except Exception as e:
                out.append({"name": "  └ %s (%s)" % (lko, lsym), "value": "수집 실패",
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
