import json, urllib.request, datetime, os, csv, io

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)

def get(url, data=None):
    h = {"User-Agent": "Mozilla/5.0 (market-board)"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def fail(name, e):
    return {"name": name, "value": "수집 실패", "change": "", "comment": str(e)[:90]}

ETFS = [("SMH","반도체"),("XLK","기술"),("IGV","소프트웨어"),
        ("ITA","방산"),("ARKX","우주"),("LIT","배터리")]

def etf():
    out = []
    for sym, ko in ETFS:
        try:
            txt = get("https://stooq.com/q/d/l/?s=%s.us&i=d" % sym.lower())
            rows = [r for r in csv.DictReader(io.StringIO(txt))
                    if r.get("Close") not in (None, "", "N/D")][-6:]
            last, prev = float(rows[-1]["Close"]), float(rows[0]["Close"])
            out.append({"name": "%s (%s)" % (ko, sym),
                        "value": "%,.2f$".replace("%,", "{:,").format(last) if False else "{:,.2f}$".format(last),
                        "change": "{:+.2f}%".format((last/prev-1)*100),
                        "comment": "%s 종가 · 5거래일 변화" % rows[-1]["Date"]})
        except Exception as e:
            out.append(fail("%s (%s)" % (ko, sym), e))
    return out

def hyperliquid():
    try:
        raw = json.loads(get("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"}))
        meta, ctxs, want, out = raw[0]["universe"], raw[1], ["BTC","ETH","SOL","HYPE"], []
        for m, c in zip(meta, ctxs):
            if m["name"] in want:
                px = float(c.get("markPx") or 0)
                oi = float(c.get("openInterest") or 0) * px
                out.append({"name": m["name"],
                            "value": "OI {:,.0f}M$".format(oi/1e6),
                            "change": "{:+.4f}%".format(float(c.get("funding") or 0)*100),
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
                 "value": "{:,.2f}M$".format((p.get("total24h") or 0)/1e6),
                 "change": "{:+.1f}%".format(p.get("change_1d") or 0),
                 "comment": "%s · 24시간 프로토콜 수익" % (p.get("category") or "")}
                for p in ps] or [fail("DeFiLlama", "데이터 없음")]
    except Exception as e:
        return [fail("DeFiLlama", e)]

payload = {
    "updated": now.strftime("%Y-%m-%d %H:%M KST"),
    "summary": "자동 수집 완료. 해석 코멘트는 4단계에서 분석 에이전트를 붙이면 이 자리에 들어갑니다.",
    "sections": [
        {"title": "섹터 ETF 가격", "note": "최근 5거래일 변화 (Stooq)", "items": etf()},
        {"title": "하이퍼리퀴드 펀딩비 · 미결제약정", "note": "실시간", "items": hyperliquid()},
        {"title": "DeFiLlama 프로토콜 수익 랭킹", "note": "24시간 기준 상위 8", "items": llama()},
    ],
}

os.makedirs("reports", exist_ok=True)
day = now.strftime("%Y-%m-%d")
for path in ("data.json", "reports/%s.json" % day):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
files = sorted([f for f in os.listdir("reports")
                if f.endswith(".json") and f != "list.json"], reverse=True)
with open("reports/list.json", "w", encoding="utf-8") as f:
    json.dump(files, f)
print("done:", day)
