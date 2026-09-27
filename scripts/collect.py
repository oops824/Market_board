import json, urllib.request, datetime, os, csv, io
import signals

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
    """일봉 약 6개월치 -> (종가, 마지막 날짜, 고가, 저가, 거래량). 신호 계산용"""
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/"
                       "%s?range=6mo&interval=1d" % sym))
    r = j["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = [(c, h, l, v) for c, h, l, v in zip(q["close"], q["high"], q["low"], q["volume"])
            if c is not None]
    d = datetime.datetime.utcfromtimestamp(r["timestamp"][-1]).strftime("%Y-%m-%d")
    if len(rows) < 6:
        raise ValueError("데이터 부족")
    cl, hi, lo, vo = (list(x) for x in zip(*rows))
    return cl, d, hi, lo, vo


def chg(cl, n):
    if len(cl) <= n:
        return None
    return (cl[-1] / cl[-1 - n] - 1) * 100

def row(label, cl, d, note, hi=None, lo=None, vo=None):
    c5, c20 = chg(cl, 5), chg(cl, 20)
    parts = []
    if c5 is not None:
        parts.append({"t": "5일 {:+.2f}%".format(c5), "c": "up" if c5 >= 0 else "dn"})
    if c20 is not None:
        parts.append({"t": "20일 {:+.2f}%".format(c20), "c": "up" if c20 >= 0 else "dn"})
    return {"name": label,
            "value": "{:,.2f}$".format(cl[-1]),
            "change": "",
            "badges": parts,
            "tags": signals.top(signals.price_signals(cl, hi, lo, vo), 3),
            "comment": "%s 종가 · %s" % (d, note)}

def etf():
    out = []
    for sym, ko, leaders in ETFS:
        try:
            cl, d, hi, lo, vo = yahoo3(sym)
            out.append(row("%s (%s)" % (ko, sym), cl, d, "섹터 ETF", hi, lo, vo))
        except Exception as e:
            out.append(fail("%s (%s)" % (ko, sym), e))
        for lsym, lko in leaders:
            try:
                lcl, ld, lhi, llo, lvo = yahoo3(lsym)
                out.append(row("  └ %s (%s)" % (lko, lsym), lcl, ld, "%s 대장주" % ko,
                               lhi, llo, lvo))
            except Exception as e:
                out.append({"name": "  └ %s (%s)" % (lko, lsym), "value": "수집 실패",
                            "change": "", "comment": str(e)[:60]})
    return out
    
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
        {"title": "DeFiLlama 프로토콜 수익 랭킹", "note": "24시간 기준 상위 8", "items": llama()},
    ],
}

os.makedirs("reports", exist_ok=True)
day = now.strftime("%Y-%m-%d")
for path in ("data.json", "reports/%s.json" % day):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("collect done")
