"""FOMC 금리 확률 — CME FedWatch 와 같은 방식으로 30일 연방기금금리 선물(ZQ) 가격에서 계산

- 선물 가격 P → 그 달 평균 실효금리 기대치 = 100 - P
- 첫 회의: 다음 달에 회의가 없으면 다음 달 선물이 회의 후 금리. 회의 달 평균에서 회의 전 금리를 역산
- 이어지는 회의: 직전 회의 후 금리를 시작점으로, 회의 달 평균에서 회의 후 금리를 역산
- 회의 전후 금리 차이를 0.25%p 단위로 나눠 인상·동결·인하 확률 (인접한 두 결과로 나눔)
새 금리는 결정 다음 날부터 적용. 가격: 야후 파이낸스(ZQ{월코드}{연도 2자리}.CBT), 실패하면 CME 시세 JSON.
CME 가 공개하는 FedWatch 수치와는 실효금리 가정 차이로 몇 %p 다를 수 있다.
"""
import calendar, datetime, json, urllib.parse, urllib.request

from calendar_ctx import FOMC_DECISIONS

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json,text/plain,*/*"}
MCODE = "FGHJKMNQUVXZ"                       # 선물 월물 코드 1~12월
STEP = 0.25


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _yahoo(y, m):
    sym = "ZQ%s%02d.CBT" % (MCODE[m - 1], y % 100)
    j = json.loads(_get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d"
                        % urllib.parse.quote(sym)))
    r = j["chart"]["result"][0]
    p = r["meta"].get("regularMarketPrice")
    if not p:
        p = [c for c in r["indicators"]["quote"][0]["close"] if c][-1]
    p = float(p)
    if not 90 < p < 100:
        raise ValueError("%s 가격 이상: %s" % (sym, p))
    return p


def _cme():
    """CME 시세 JSON (상품 305 = 30일 연방기금금리 선물) → {(연, 월): 가격}"""
    j = json.loads(_get("https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/305/G"))
    out = {}
    for q in j.get("quotes", []):
        px = None
        for k in ("last", "priorSettle", "close"):
            v = str(q.get(k) or "").replace(",", "").strip()
            try:
                px = float(v)
                break
            except ValueError:
                continue
        try:
            mon = datetime.datetime.strptime((q.get("expirationMonth") or "").strip().title(), "%b %Y")
        except ValueError:
            continue
        if px and 90 < px < 100:
            out[(mon.year, mon.month)] = px
    return out


def _nxt(ym):
    y, m = ym
    return (y + 1, 1) if m == 12 else (y, m + 1)


def _prv(ym):
    y, m = ym
    return (y - 1, 12) if m == 1 else (y, m - 1)


def prices(months):
    """필요한 월물 가격. 야후에서 하나라도 못 받으면 CME 로 채움"""
    P, src, err = {}, "야후 파이낸스", []
    for ym in months:
        try:
            P[ym] = _yahoo(*ym)
        except Exception as e:
            err.append("%d-%02d %s" % (ym[0], ym[1], str(e)[:60]))
    if len(P) < len(months):
        try:
            c = _cme()
            for ym in months:
                if ym not in P and ym in c:
                    P[ym] = c[ym]
                    src = "야후 파이낸스·CME"
        except Exception as e:
            err.append("CME %s" % str(e)[:80])
    if err:
        print("[페드워치] 일부 월물 실패:", "; ".join(err))
    return P, src


def compute(today, P, meetings):
    """meetings: 오늘 이후 결정일(date) 목록. 결정일 다음 날부터 새 금리 적용"""
    mm = {(d.year, d.month) for d in meetings}
    rate = lambda ym: 100 - P[ym]
    res, start = [], None
    for d in meetings:
        ym, n = (d.year, d.month), calendar.monthrange(d.year, d.month)[1]
        pre, post = d.day, n - d.day
        if ym not in P:
            break
        a, end = rate(ym), None
        if start is None:
            if _nxt(ym) not in mm and _nxt(ym) in P:
                end = rate(_nxt(ym))
                start = (a * n - end * post) / pre
            elif _prv(ym) not in mm and _prv(ym) in P and post > 0:
                start = rate(_prv(ym))
                end = (a * n - start * pre) / post
        elif post >= 5:
            end = (a * n - start * pre) / post
        elif _nxt(ym) not in mm and _nxt(ym) in P:
            end = rate(_nxt(ym))
        if start is None or end is None:
            break
        res.append({"date": d.isoformat(), "pre": start, "post": end})
        start = end
    if not res:
        return []
    base = res[0]["pre"]
    for r in res:
        mv = (r["post"] - r["pre"]) / STEP
        if abs(mv) > 3:                          # 75bp 넘는 움직임은 가격 오류로 본다
            return []
        up, dn = max(mv, 0.0), max(-mv, 0.0)
        r.update(hike=round(min(up, 1) * 100, 1), cut=round(min(dn, 1) * 100, 1),
                 hike50=round(max(up - 1, 0) * 100, 1), cut50=round(max(dn - 1, 0) * 100, 1),
                 move_bp=round(mv * 25, 1), cum_bp=round((r["post"] - base) / STEP * 25, 1),
                 pre=round(r["pre"], 3), post=round(r["post"], 3))
        r["hold"] = round(max(0.0, 100 - r["hike"] - r["cut"]), 1)
    return res


def fedwatch(today=None):
    """→ {"asof", "src", "now", "meetings": [...]} 또는 None"""
    today = today or (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()
    meets = [datetime.date.fromisoformat(d) for d in FOMC_DECISIONS]
    meets = [d for d in meets if d >= today][:3]
    if not meets:
        return None
    need = set()
    for d in meets:
        ym = (d.year, d.month)
        need |= {ym, _nxt(ym)}
    P, src = prices(sorted(need))
    res = compute(today, P, meets)
    if not res:
        return None
    return {"asof": today.isoformat(), "src": src, "now": res[0]["pre"], "meetings": res}


def items(fw, hist):
    """지표 탭 표 항목. hist: history/trend.json (1주 전 확률과 비교)"""
    if not fw:
        return [{"name": "FOMC 금리 확률", "value": "수집 실패", "change": "",
                 "comment": "연방기금금리 선물 가격을 받지 못함"}]
    today = datetime.date.fromisoformat(fw["asof"])
    old = {}
    for h in hist or []:
        try:
            if (today - datetime.date.fromisoformat(h["date"])).days >= 7:
                old = h.get("fomc") or {}
        except (KeyError, ValueError):
            continue
    out = []
    for i, m in enumerate(fw["meetings"]):
        d = datetime.date.fromisoformat(m["date"])
        side = ("인상", m["hike"] + m["hike50"]) if m["move_bp"] >= 0 else ("인하", m["cut"] + m["cut50"])
        prev = (old.get("m") or {}).get(m["date"])
        ch = ""
        if prev is not None:
            ch = "%+.1f%%p (1주)" % ((m["hike"] + m["hike50"] - m["cut"] - m["cut50"]) - prev)
        mix = "인상 %.0f%% · 동결 %.0f%% · 인하 %.0f%%" % (m["hike"] + m["hike50"], m["hold"], m["cut"] + m["cut50"])
        out.append({"name": "%d/%d FOMC 금리 %s 확률 (%d일 후)" % (d.month, d.day, side[0], (d - today).days),
                    "value": "%.1f%%" % side[1], "change": ch,
                    "comment": "%s · 선물 내재 금리 %.2f%%→%.2f%% · 지금부터 누적 %+.0fbp" % (
                        mix, m["pre"], m["post"], m["cum_bp"])})
    return out


def trend_rec(fw):
    """history/trend.json 에 남길 값: 회의별 (인상 - 인하) 확률"""
    if not fw:
        return None
    return {"m": {m["date"]: round(m["hike"] + m["hike50"] - m["cut"] - m["cut50"], 1) for m in fw["meetings"]}}
