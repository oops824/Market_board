"""실적 발표 일정·결과 — 보유 종목·직전 의견의 관심 종목·주요 대형주

- 일정·EPS 예상·결과: 나스닥 실적 캘린더 API (미국 날짜별, 최근 10일~다음 14일 평일)
- 주가 반응: 야후 파이낸스 일봉(마지막 날 종가 보정)으로 발표 전 종가 대비 첫 거래일·지금까지 누적,
  장후 발표 뒤 아직 정규장이 열리지 않았으면 시간외·프리마켓 가격
- 발표 시각(장전·장후): 나스닥은 발표일이 지나면 비워 주므로 직전 실행이 opinion.json 에 남긴 값을 이어 쓰고,
  그것도 없으면 발표일과 다음 날 중 주가가 더 크게 움직인 쪽으로 추정한다('추정' 표시)
data.json 에 earnings(구조화)와 '실적 발표' 섹션을 넣는다. 실패해도 나머지 데이터는 그대로 둔다.
"""
import datetime, json, re, urllib.parse, urllib.request

import ychart

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                   # tzdata 가 없으면 동부 표준시로 근사
    ET = datetime.timezone(datetime.timedelta(hours=-5))
KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
now_et = now.astimezone(ET)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*",
      "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
# 실적이 시장 전체와 보유 종목 공급망으로 번지는 대형주
BELL = ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "AAPL", "TSLA", "AVGO", "TSM", "ORCL", "AMD", "MU", "ASML",
        "NFLX", "COIN", "MSTR", "HOOD", "JPM", "XOM", "LLY", "UNH", "V", "WMT", "COST"]
WHEN = {"time-pre-market": "장전", "time-after-hours": "장후"}
ALIAS = {"GOOG": "GOOGL"}                           # 같은 회사의 다른 주식 종류
BACK, FWD = 10, 14


def get(url, headers=UA, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def known_when():
    """직전 실행이 저장한 발표 시각 {(티커, 날짜): '장전'·'장후'} (추정값은 빼고)"""
    try:
        with open("opinion.json", encoding="utf-8") as f:
            E = json.load(f).get("earnings") or {}
    except Exception:
        return {}
    return {(e["sym"], e["date"]): e["when"] for e in (E.get("recent") or []) + (E.get("upcoming") or [])
            if e.get("when") in WHEN.values() and not e.get("guess")}


def universe():
    """(대상 티커 집합, 보유 티커 집합, 레버리지 보유 티커 집합)"""
    held, lev, watch = set(), set(), set()
    try:
        with open("portfolio.json", encoding="utf-8") as f:
            for h in json.load(f).get("stocks", {}).get("holdings", []):
                held.add(h["sym"])
                if h.get("lev"):
                    lev.add(h["sym"])
    except Exception as e:
        print("[실적] 포트폴리오 읽기 실패:", e)
    try:
        with open("opinion.json", encoding="utf-8") as f:
            watch = set((json.load(f).get("watch_meta") or {}).keys())
    except Exception:
        pass
    ok = lambda t: re.fullmatch(r"[A-Z][A-Z.\-]{0,6}", t or "")
    return {t for t in set(BELL) | held | watch if ok(t)}, held, lev


def money(s):
    """'$3.01' · '($0.12)' · 'N/A' → float 또는 None"""
    t = str(s or "").replace("$", "").replace(",", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    try:
        v = float(t.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def calendar(univ, known):
    """미국 날짜 기준 최근 BACK 일~다음 FWD 일 평일 → (발표 끝난 것, 예정), 실패 목록"""
    today = now_et.date()
    done, todo, err = {}, {}, []
    for k in range(-BACK, FWD + 1):
        d = today + datetime.timedelta(days=k)
        if d.weekday() >= 5:
            continue
        try:
            j = json.loads(get("https://api.nasdaq.com/api/calendar/earnings?date=%s" % d.isoformat()))
            rows = (j.get("data") or {}).get("rows") or []
        except Exception as e:
            err.append("%s %s" % (d.isoformat(), str(e)[:40]))
            continue
        for r in rows:
            s = (r.get("symbol") or "").upper().replace(".", "-")
            s = ALIAS.get(s, s)
            if s not in univ:
                continue
            when = WHEN.get(r.get("time")) or known.get((s, d.isoformat()), "")
            item = {"sym": s, "name": (r.get("name") or s)[:40], "date": d.isoformat(), "when": when,
                    "est": money(r.get("epsForecast")), "n": r.get("noOfEsts") or "",
                    "ly": money(r.get("lastYearEPS")), "eps": money(r.get("eps") or r.get("epsActual")),
                    "fq": r.get("fiscalQuarterEnding") or ""}
            # 결과가 나왔다고 볼 시각: 장전 발표는 미국 8시 반, 장후·미상은 16시 반
            cut = datetime.datetime.combine(d, datetime.time(8, 30) if when == "장전" else datetime.time(16, 30), tzinfo=ET)
            (done if now_et >= cut else todo)[s] = item
    return done, todo, err


def daily(sym):
    """[(거래소 현지 날짜, 종가)] 최근 1개월 (마지막 날 종가 보정)"""
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1mo&interval=1d"
                       % urllib.parse.quote(sym), headers={"User-Agent": UA["User-Agent"]}))
    r = ychart.fix_last(j["chart"]["result"][0])
    off = r["meta"].get("gmtoffset") or 0
    return [(datetime.datetime.utcfromtimestamp(t + off).date(), c)
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]


def extended(sym):
    """(가장 최근 시간외·프리마켓 가격, '시간외'·'프리마켓') 또는 (None, '')"""
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m&includePrePost=true"
                       % urllib.parse.quote(sym), headers={"User-Agent": UA["User-Agent"]}))
    r = j["chart"]["result"][0]
    off = r["meta"].get("gmtoffset") or 0
    pts = [(t, c) for t, c in zip(r.get("timestamp") or [], r["indicators"]["quote"][0]["close"]) if c is not None]
    if not pts:
        return None, ""
    t, c = pts[-1]
    h = datetime.datetime.utcfromtimestamp(t + off)
    hm = h.hour + h.minute / 60
    return (c, "시간외") if hm >= 16 else (c, "프리마켓") if hm < 9.5 else (None, "")


def guess(s, d):
    """발표 시각을 모를 때: 발표일 등락이 다음 날보다 크면 장전, 작으면 장후. 다음 날 봉이 없으면 ''"""
    j = next((i for i, (x, _) in enumerate(s) if x == d), None)
    if j is None or j == 0 or j + 1 >= len(s):
        return ""
    return "장전" if abs(s[j][1] / s[j - 1][1] - 1) > abs(s[j + 1][1] / s[j][1] - 1) else "장후"


def reaction(e):
    """발표 전 마지막 종가 대비 첫 거래일·누적 등락(%), 첫 거래일 전이면 시간외 등락"""
    d = datetime.date.fromisoformat(e["date"])
    s = daily(e["sym"])
    if not e["when"]:
        e["when"] = guess(s, d)
        if e["when"]:
            e["guess"] = True
    if e["when"] == "장후":
        bi = max((i for i, (x, _) in enumerate(s) if x <= d), default=None)
    else:
        bi = max((i for i, (x, _) in enumerate(s) if x < d), default=None)
    if bi is None:
        return {}
    base, out = s[bi][1], {}
    if bi + 1 < len(s):
        out.update(day1=round((s[bi + 1][1] / base - 1) * 100, 1), since=round((s[-1][1] / base - 1) * 100, 1),
                   days=len(s) - 1 - bi)
    else:
        px, lab = extended(e["sym"])
        if px:
            out.update(ext=round((px / base - 1) * 100, 1), ext_lab=lab)
    return out


def money_s(v):
    return "-" if v is None else ("-$%.2f" % -v if v < 0 else "$%.2f" % v)


def short(name):
    for w in (", Inc.", " Inc.", " Corporation", " Corp.", " Holdings", " Platforms", ".com", " Technologies"):
        name = name.replace(w, "")
    return name.strip()[:16]


def when_s(e):
    return (e.get("when") or "") + ("(추정)" if e.get("guess") else "")


def section(E, held, lev):
    items = []
    for e in E["recent"]:
        flag = "레버리지 보유" if e["sym"] in lev else "보유" if e["sym"] in held else ""
        r, b = e.get("react") or {}, []
        if "day1" in r:
            b.append({"t": "첫날 %+.1f%%" % r["day1"], "c": "up" if r["day1"] >= 0 else "dn"})
            if r.get("days", 0) > 1:
                b.append({"t": "누적 %+.1f%%" % r["since"], "c": "up" if r["since"] >= 0 else "dn"})
        elif "ext" in r:
            b.append({"t": "%s %+.1f%%" % (r["ext_lab"], r["ext"]), "c": "up" if r["ext"] >= 0 else "dn"})
        sp = ""
        if e.get("eps") is not None and e.get("est"):
            sp = " (%+.0f%%)" % ((e["eps"] / e["est"] - 1) * 100) if e["est"] > 0 else ""
        items.append({"name": "%s %s" % (e["sym"], short(e["name"])),
                      "value": ("EPS %s%s" % (money_s(e["eps"]), sp)) if e.get("eps") is not None else "예상 EPS %s" % money_s(e["est"]),
                      "badges": b + ([{"t": flag, "c": "warn"}] if flag else []),
                      "comment": "%s %s 발표 · 예상 %s · 작년 같은 분기 %s%s" % (
                          e["date"][5:].replace("-", "/"), when_s(e), money_s(e["est"]), money_s(e["ly"]),
                          "" if e.get("eps") is not None else " · 실제 EPS는 뉴스·전문가 전망 참고")})
    for e in E["upcoming"]:
        flag = "레버리지 보유" if e["sym"] in lev else "보유" if e["sym"] in held else ""
        dd = (datetime.date.fromisoformat(e["date"]) - now_et.date()).days
        items.append({"name": "%s %s" % (e["sym"], short(e["name"])),
                      "value": "예상 EPS %s" % money_s(e["est"]),
                      "badges": [{"t": "D-%d" % dd if dd > 0 else "오늘", "c": "na"}] + ([{"t": flag, "c": "warn"}] if flag else []),
                      "comment": "%s %s 발표 예정 · 작년 같은 분기 %s · 애널리스트 %s명" % (
                          e["date"][5:].replace("-", "/"), e["when"] or "", money_s(e["ly"]), e["n"] or "-")})
    if not items:
        items = [{"name": "실적 발표", "value": "수집 실패" if E["err"] else "해당 없음", "change": "",
                  "comment": "; ".join(E["err"][:3]) or "보유·관심 종목의 발표가 이 기간에 없음"}]
    return {"title": "실적 발표",
            "note": "나스닥 실적 캘린더 · 야후 파이낸스 · 최근 %d일 결과와 다음 %d일 일정 (미국 날짜)" % (BACK, FWD),
            "items": items}


def main():
    univ, held, lev = universe()
    done, todo, err = calendar(univ, known_when())
    recent = sorted(done.values(), key=lambda e: e["date"], reverse=True)
    for e in recent:
        try:
            e["react"] = reaction(e)
        except Exception as ex:
            e["react"] = {}
            err.append("%s 반응 %s" % (e["sym"], str(ex)[:40]))
    E = {"asof": now.strftime("%Y-%m-%d %H:%M KST"), "src": "나스닥 실적 캘린더·야후 파이낸스",
         "recent": recent, "upcoming": sorted(todo.values(), key=lambda e: e["date"]),
         "held": sorted(held), "lev": sorted(lev), "err": err[:10]}
    print("[실적] 대상 %d종 · 최근 발표 %d · 예정 %d · 실패 %d" % (len(univ), len(recent), len(E["upcoming"]), len(err)))
    with open("data.json", encoding="utf-8") as f:
        payload = json.load(f)
    payload["earnings"] = E
    payload["sections"] = [s for s in payload["sections"] if s.get("title") != "실적 발표"] + [section(E, held, lev)]
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
