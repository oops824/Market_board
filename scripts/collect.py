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
    ("XLF", "금융", [("JPM", "JP모건"), ("V", "비자"), ("GS", "골드만삭스")]),
    ("XLV", "헬스케어", [("LLY", "일라이릴리"), ("UNH", "유나이티드헬스"), ("JNJ", "존슨앤드존슨")]),
    ("XLE", "에너지", [("XOM", "엑슨모빌"), ("CVX", "셰브론"), ("COP", "코노코필립스")]),
    ("XLI", "산업재", [("CAT", "캐터필러"), ("UBER", "우버"), ("HON", "허니웰")]),
    ("XLY", "경기소비재", [("AMZN", "아마존"), ("HD", "홈디포"), ("BKNG", "부킹홀딩스")]),
    ("XLP", "필수소비재", [("COST", "코스트코"), ("WMT", "월마트"), ("PG", "P&G")]),
    ("XLC", "커뮤니케이션", [("META", "메타"), ("GOOGL", "알파벳"), ("NFLX", "넷플릭스")]),
    ("IWM", "소형주", []),
    ("BLOK", "크립토 관련주", [("COIN", "코인베이스"), ("HOOD", "로빈후드"), ("MSTR", "스트래티지")]),
]

_Y3 = {}


def yahoo3(sym):
    """일봉 약 6개월치 -> (종가, 마지막 날짜, 고가, 저가, 거래량). 신호 계산용 (여러 섹터에 겹치는 종목은 한 번만 받음)"""
    if sym not in _Y3:
        _Y3[sym] = _yahoo3(sym)
    return _Y3[sym]


def _yahoo3(sym):
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

def trend_of(sigs):
    """전체 신호에서 추세 방향: 골든/데드크로스 > 추세 상승/하락 > 20일 신고가/신저가 (표에는 상위 3개만 남아 추세 태그가 빠질 수 있음)"""
    t = {x["t"] for x in sigs}
    for kw, v in (("골든크로스", "up"), ("데드크로스", "down"), ("추세 상승", "up"), ("추세 하락", "down"),
                  ("20일 신고가", "up"), ("20일 신저가", "down")):
        if kw in t:
            return v
    return "flat"


def row(label, cl, d, note, hi=None, lo=None, vo=None):
    c5, c20 = chg(cl, 5), chg(cl, 20)
    sigs = signals.price_signals(cl, hi, lo, vo)
    parts = []
    if c5 is not None:
        parts.append({"t": "5일 {:+.2f}%".format(c5), "c": "up" if c5 >= 0 else "dn"})
    if c20 is not None:
        parts.append({"t": "20일 {:+.2f}%".format(c20), "c": "up" if c20 >= 0 else "dn"})
    return {"name": label,
            "value": "{:,.2f}$".format(cl[-1]),
            "change": "",
            "badges": parts,
            "tags": signals.top(sigs, 3),
            "trend": trend_of(sigs),
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
    
QUAD = {"lead": "주도", "improve": "개선(돌아서는 중)", "weaken": "약화", "lag": "소외"}


def rotation():
    """섹터 ETF의 SPY 대비 상대강도: 20일(최근)·3개월(63일) 초과수익(%p)으로 4분면 분류
    주도: 둘 다 플러스 / 개선: 3개월은 뒤지지만 최근 20일은 앞섬(돌아서는 중) / 약화: 반대 / 소외: 둘 다 마이너스"""
    try:
        spy = yahoo3("SPY")[0]
    except Exception as e:
        print("SPY 실패:", e)
        return None, []
    def r(cl, n, end=0):
        if len(cl) <= n + end:
            return None
        return (cl[-1 - end] / cl[-1 - end - n] - 1) * 100
    items, rows = [], []
    for sym, ko, _ in ETFS:
        try:
            cl = yahoo3(sym)[0]
        except Exception:
            continue
        n = min(len(cl), len(spy))
        e, s = cl[-n:], spy[-n:]
        if None in (r(e, 63), r(s, 63)):
            continue
        rs20, rs63 = r(e, 20) - r(s, 20), r(e, 63) - r(s, 63)
        prev = r(e, 20, 5) - r(s, 20, 5) if r(e, 20, 5) is not None else rs20
        q = ("lead" if rs20 > 0 else "weaken") if rs63 > 0 else ("improve" if rs20 > 0 else "lag")
        items.append({"etf": sym, "name": ko, "r5": round(r(e, 5), 2), "r20": round(r(e, 20), 2),
                      "r63": round(r(e, 63), 2), "rs20": round(rs20, 2), "rs63": round(rs63, 2),
                      "d5": round(rs20 - prev, 2), "q": q})
        rows.append({"name": "%s (%s)" % (ko, sym), "value": "20일 {:+.1f}%p".format(rs20), "change": "",
                     "badges": [{"t": "3개월 {:+.1f}%p".format(rs63), "c": "up" if rs63 >= 0 else "dn"},
                                {"t": QUAD[q], "c": {"lead": "up", "improve": "up", "weaken": "warn", "lag": "dn"}[q]}],
                     "comment": "SPY 대비 초과수익 · 5일 전보다 20일 상대강도 {:+.1f}%p".format(rs20 - prev)})
    items.sort(key=lambda x: -x["rs20"])
    rows.sort(key=lambda x: -float(x["value"].split()[1].rstrip("%p")))
    spy_r = {"r5": round(r(spy, 5), 2), "r20": round(r(spy, 20), 2), "r63": round(r(spy, 63), 2)}
    return {"asof": now.strftime("%Y-%m-%d"), "spy": spy_r, "items": items}, rows


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

sector_items = etf()
rot, rot_rows = rotation()
payload = {
    "updated": now.strftime("%Y-%m-%d %H:%M KST"),
    "summary": "자동 수집 완료.",
    "sections": [
        {"title": "섹터 ETF 가격", "note": "최근 5거래일 변화", "items": sector_items},
        {"title": "섹터 로테이션 (SPY 대비 상대강도)", "note": "20일·3개월 초과수익(%p), 4분면 분류",
         "items": rot_rows},
        {"title": "DeFiLlama 프로토콜 수익 랭킹", "note": "24시간 기준 상위 8", "items": llama()},
    ],
    "rotation": rot,
}

os.makedirs("reports", exist_ok=True)
day = now.strftime("%Y-%m-%d")
for path in ("data.json", "reports/%s.json" % day):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
print("collect done")
