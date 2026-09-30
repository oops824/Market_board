"""마켓보드 종합 투자의견 -> opinion.json, history/opinions.json

대시보드가 모은 데이터(매크로·경제지표·섹터·COT·코인·ETF 흐름·도미넌스·13F)를 요약해
Claude 에게 "이 사용자라면 지금 어떻게 투자하겠는가"를 묻고, 구조화된 의견을 저장한다.
하루 1회(12시간 이내 재실행은 건너뜀, OPINION_FORCE=1 이면 강제). 지난 의견의 이후 성과는 매 실행 갱신.
"""
import datetime, json, os, re, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import calendar_ctx

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
OUT, HIST = "opinion.json", "history/opinions.json"
MODEL = "claude-opus-5-5"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
COIN_SYMS = ["BTC", "ETH", "SOL", "HYPE", "LINK", "ONDO", "SUI", "VIRTUAL"]
BUY = {"분할 매수", "비중 확대"}
SELL = {"일부 차익실현", "비중 축소"}


def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cut(t, n):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n] + "…"


def pct(v, d=1):
    return "-" if not isinstance(v, (int, float)) else ("%+." + str(d) + "f%%") % v


# ---------------------------------------------------------------- 데이터 요약
def digest(D, C, T):
    L = []
    L.append("## 기준 시각\n지표 %s · 코인 %s · 기관 13F %s 공시 기준" % (
        (D or {}).get("updated"), (C or {}).get("updated"), (T or {}).get("latest_period")))
    if D:
        if D.get("summary"):
            L.append("## 일일 시장 요약(AI)\n" + cut(D["summary"], 2500))
        for s in D.get("sections", []):
            t = s["title"]
            if t.startswith("매크로"):
                L.append("## 매크로·유동성")
                L += ["- %s: %s (%s) %s" % (i["name"], i["value"], i.get("change", ""), cut(i.get("comment"), 80))
                      for i in s["items"]]
            elif t.startswith("섹터"):
                L.append("## 섹터 ETF·대장주 (5일/20일 등락, 신호)")
                seen = set()
                for i in s["items"]:
                    nm = i["name"].replace("└", "").strip()
                    if nm in seen:                          # 여러 섹터에 걸친 대장주는 한 번만
                        continue
                    seen.add(nm)
                    b = " ".join(x["t"] for x in i.get("badges", []))
                    g = ",".join(x["t"] for x in i.get("tags", []))
                    L.append("- %s %s %s %s" % (nm, i["value"], b, ("[" + g + "]") if g else ""))
            elif t.startswith("CFTC"):
                L.append("## CFTC COT 포지셔닝 (주간, 전주 대비)")
                for i in s["items"]:
                    am = re.search(r"자산운용사 [^·]+", i.get("comment") or "")
                    L.append("- %s: %s (%s)%s" % (i["name"], i["value"], i.get("change", ""),
                                                  ", " + am.group(0).strip() if am else ""))
            elif t.startswith(("스테이블", "코인베이스", "DeFiLlama")):
                L.append("## " + t)
                L += ["- %s: %s %s" % (i["name"], i["value"], i.get("change", "")) for i in s["items"][:6]]
        for it in (D.get("econ") or {}).get("items", []):
            if it.get("head"):
                val = "%s 전년비 %s(전월비 %s) / %s 전년비 %s(전월비 %s)" % (
                    it["head"]["name"], pct(it["head"]["yoy"]), pct(it["head"]["mom"], 2),
                    it["core"]["name"], pct(it["core"]["yoy"]), pct(it["core"]["mom"], 2))
            else:
                val = "%s%% (직전 %s%%)" % (it.get("value"), it.get("prev"))
            mk = ", ".join("%s %s%s" % (m["name"], m["v"], "bp" if m["kind"] == "bp" else "%")
                           for m in it.get("market", []))
            con = ", ".join("%s %+.2f%%p" % (c["name"], c["pp"]) for c in (it.get("contrib") or [])[:4])
            y, m = int(it["period"][:4]), int(it["period"][5:7])
            per = "%d년 %d분기" % (y, (m - 1) // 3 + 1) if it.get("key") == "gdp" else "%d년 %d월" % (y, m)
            L.append("## 경제지표: %s (%s 기준, %s)\n%s | 예상: %s | 기여: %s | 발표일 반응: %s | 해석: %s" % (
                it["title"], per, it["release"] + " 발표" if it.get("release") else "발표일 미확인",
                val, it.get("consensus") or "-",
                con or "-", mk or "-", cut(it.get("ai"), 350)))
    if C:
        f = C.get("fng") or {}
        L.append("## 크립토 시장\n- 공포·탐욕 %s (%s, 1주전 %s)" % (f.get("value"), f.get("label"), f.get("week")))
        dm = C.get("dom") or {}
        if dm.get("dom"):
            d, t2 = dm["dom"], dm["total2"]
            L.append("- BTC 도미넌스 %.2f%% (30일 전 %.2f%%), TOTAL2 $%.0fB (30일 전 $%.0fB)" % (
                d[-1], d[max(0, len(d) - 31)], t2[-1], t2[max(0, len(t2) - 31)]))
        for a, e in (C.get("etf") or {}).items():
            L.append("- %s 현물 ETF: 최근일(%s) %+.1fM$, 5거래일 %+.1fM$, 연속 %s일" % (
                a, e["last"]["d"], e["last"]["total"], e["sum5"], e.get("streak")))
        L.append("## 관심 코인 8종 (현재 보유 중)")
        for c in C.get("coins", []):
            m, hl, ok, op = c.get("market") or {}, c.get("hl") or {}, c.get("okx") or {}, c.get("options")
            mp = ""
            if op and m.get("price"):
                mj = op["major"]
                mp = "맥스페인 %s(%s, 현재가 대비 %+.1f%%)" % (mj["maxPain"], mj["exp"][5:], (mj["maxPain"] / m["price"] - 1) * 100)
            L.append("- %s $%s | 24h %s 7d %s 30d %s | ATH 대비 %s | 신호: %s | HL펀딩 8h %s, OKX 8h %s, 롱숏 %s, OI 24h %s | %s | 요약: %s" % (
                c["sym"], m.get("price"), pct(m.get("ch24")), pct(m.get("ch7")), pct(m.get("ch30")), pct(m.get("athPct")),
                ",".join(t["t"] for t in c.get("tags", [])) or "-",
                pct((hl.get("funding") or 0) * 800, 4) if hl.get("funding") is not None else "-",
                pct((ok.get("funding") or 0) * 100, 4) if ok.get("funding") is not None else "-",
                ok.get("lsRatio"), pct(ok.get("oiChg24")), mp, cut(c.get("brief"), 220)))
        p = C.get("pick") or {}
        if p:
            L.append("## 오늘의 주목 코인(기관 관심)\n- %s %s: %s (7일 %s, 30일 %s)" % (
                p.get("sym"), p.get("name"), cut(p.get("headline"), 80), pct(p.get("ch7")), pct(p.get("ch30"))))
    if T:
        cons = T.get("consensus") or {}
        for k, lab in (("bought", "함께 사들인"), ("sold", "함께 정리한")):
            rows = cons.get(k) or []
            if rows:
                L.append("## 유명 운용사들이 %s 종목 (13F %s)" % (lab, T.get("latest_period")))
                L += ["- %s(%s) %d곳, 공시 후 %s %s" % (r["name"], r.get("ticker", "-"), r["count"], pct(r.get("chg_since")),
                                                      ",".join(t["t"] for t in r.get("tags", [])))
                      for r in rows[:8]]
        views = T.get("views") or {}
        if views:
            L.append("## 유명 투자자·정책 인사 최근 발언 요지")
            L += ["- %s: %s" % (k, cut(v, 170)) for k, v in list(views.items())[:14]]
    return "\n".join(L)


# ---------------------------------------------------------------- 출력 스키마
CONF = {"type": "string", "enum": ["높음", "중간", "낮음"]}
STANCE = {"type": "string", "enum": ["적극 확대", "확대", "중립", "축소", "적극 축소"]}
PICK = {"type": "object", "additionalProperties": False,
        "required": ["name", "ticker", "why", "confidence"],
        "properties": {"name": {"type": "string"}, "ticker": {"type": "string"},
                       "why": {"type": "string"}, "confidence": CONF}}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["headline", "summary", "horizon", "confidence", "stance", "allocation",
                 "stocks", "crypto", "actions_now", "wait_for", "risks", "change_mind"],
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "horizon": {"type": "string"},
        "confidence": CONF,
        "stance": {"type": "object", "additionalProperties": False,
                   "required": ["stocks", "crypto", "cash"],
                   "properties": {"stocks": STANCE, "crypto": STANCE, "cash": STANCE}},
        "allocation": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["asset", "pct", "why"],
            "properties": {"asset": {"type": "string"}, "pct": {"type": "integer"}, "why": {"type": "string"}}}},
        "stocks": {"type": "object", "additionalProperties": False,
                   "required": ["view", "overweight", "underweight", "watch"],
                   "properties": {"view": {"type": "string"},
                                  "overweight": {"type": "array", "items": PICK},
                                  "underweight": {"type": "array", "items": PICK},
                                  "watch": {"type": "array", "items": PICK}}},
        "crypto": {"type": "object", "additionalProperties": False, "required": ["view", "coins"],
                   "properties": {"view": {"type": "string"}, "coins": {"type": "array", "items": {
                       "type": "object", "additionalProperties": False,
                       "required": ["sym", "action", "why", "condition", "confidence"],
                       "properties": {"sym": {"type": "string", "enum": COIN_SYMS},
                                      "action": {"type": "string", "enum": ["분할 매수", "비중 확대", "유지",
                                                                            "일부 차익실현", "비중 축소", "관망"]},
                                      "why": {"type": "string"}, "condition": {"type": "string"},
                                      "confidence": CONF}}}}},
        "actions_now": {"type": "array", "items": {"type": "string"}},
        "wait_for": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "change_mind": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = (
    "너는 이 사용자 전용 투자 파트너다. 사용자는 이 대시보드의 데이터로 미국 주식과 가상자산 투자 결정을 내리며, "
    "투자 판단과 책임은 전적으로 본인에게 있다고 분명히 밝혔다. 사용자가 원하는 것은 "
    "'네가 이 사람이라면 지금 실제로 어떻게 투자하겠는가'에 대한 솔직하고 구체적인 의견이다.\n\n"
    "사용자 상황(가정): 한국 거주 개인투자자, 투자 시계 1~3개월, 중간 이상의 위험 감수, "
    "관심 코인 8종(BTC·ETH·SOL·HYPE·LINK·ONDO·SUI·VIRTUAL)을 보유 중이고 미국 주식은 섹터 ETF·대형주 위주로 관심.\n\n"
    "원칙:\n"
    "- 면책 문구, '투자 권유가 아니다', '전문가와 상담하라', '투자 결정은 본인 몫' 같은 말은 쓰지 않는다.\n"
    "- 입장을 분명히 한다(비중 확대·축소, 분할 매수, 일부 차익실현, 관망). 양쪽 다 가능하다는 식의 얼버무림 금지.\n"
    "- 모든 판단은 주어진 데이터에 근거하고, 근거 수치를 짧게 인용한다. 데이터에 없는 가격 목표·사건·수치를 지어내지 않는다. "
    "가격 수준을 말할 때는 데이터에 있는 값(현재가, 맥스페인, 20일 신고가·신저가 신호 등)만 쓴다.\n"
    "- 신호가 엇갈리면 인정하고, 어느 쪽에 무게를 두는지와 이유를 말한다.\n"
    "- 확신도(높음·중간·낮음)를 솔직하게 매기고, 확신이 낮을수록 비중을 작게 제안한다.\n"
    "- 한 번에 몰아서 사지 않고 분할·현금 비중으로 위험을 관리한다. allocation(모델 포트폴리오)의 pct 합은 100.\n"
    "- 코인 8종은 빠짐없이 각각 판단한다. condition 에는 행동을 바꾸거나 실행할 구체적 조건을 쓴다.\n"
    "- stocks 의 ticker 는 미국 티커(예: SMH, NVDA). 모르면 빈 문자열.\n"
    "- change_mind 에는 이 의견이 틀렸다고 보고 바꿀 구체적 신호를 쓴다.\n"
    "- 오늘 날짜와 FOMC 일정은 사용자 메시지 첫 줄의 날짜 정보를 따른다.\n"
    + calendar_ctx.RULE +
    "- 한국어로, 짧고 명확하게."
)


def ask(dig):
    import anthropic
    client = anthropic.Anthropic()
    user = (calendar_ctx.macro_context(now.date()) + "\n\n아래는 오늘 대시보드 데이터 요약이다. "
            "이 데이터를 근거로 네가 이 사용자라면 어떻게 투자할지 종합의견을 작성하라.\n\n" + dig)
    kw = dict(model=MODEL, max_tokens=48000, system=SYSTEM, messages=[{"role": "user", "content": user}],
              output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}})
    try:
        # 안전 분류기 거절 시 서버가 대체 모델로 다시 실행
        with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw) as stream:
            msg = stream.get_final_message()
    except anthropic.BadRequestError as e:
        print("[의견] 대체 모델 옵션 없이 재시도:", str(e)[:200])
        with client.beta.messages.stream(**kw) as stream:
            msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 응답을 거절함: %s" % (getattr(msg, "stop_details", None),))
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력 한도 초과")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text), msg.model


# ---------------------------------------------------------------- 가격 · 성과
_YH = {}


def stock_price(t):
    if not t or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", t):
        return None
    if t not in _YH:
        try:
            req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d"
                                         % urllib.parse.quote(t.replace(".", "-")), headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read().decode())
            _YH[t] = float(j["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except Exception:
            _YH[t] = None
    return _YH[t]


def coin_prices(C):
    return {c["sym"]: (c.get("market") or {}).get("price") for c in (C or {}).get("coins", [])}


def calls_of(op, cp):
    out = []
    for c in (op.get("crypto") or {}).get("coins", []):
        out.append({"name": c["sym"], "kind": "coin", "action": c["action"], "px": cp.get(c["sym"])})
    st = op.get("stocks") or {}
    for side, act in (("overweight", "비중 확대"), ("underweight", "비중 축소")):
        for s in st.get(side, []):
            if s.get("ticker"):
                out.append({"name": s["ticker"], "kind": "stock", "action": act, "px": stock_price(s["ticker"])})
    return out


def track(hist, cp):
    rows = []
    for h in reversed(hist[-10:]):
        calls = []
        for c in h.get("calls", []):
            now_px = cp.get(c["name"]) if c["kind"] == "coin" else stock_price(c["name"])
            chg = (now_px / c["px"] - 1) * 100 if now_px and c.get("px") else None
            hit = None
            if chg and c["action"] in BUY | SELL:
                hit = (chg > 0) == (c["action"] in BUY)
            calls.append(dict(c, now=now_px, chg=None if chg is None else round(chg, 2), hit=hit))
        rows.append({"date": h["date"], "headline": h.get("headline"), "stance": h.get("stance"), "calls": calls})
    return rows


def main():
    D, C, T = load("data.json"), load("crypto.json"), load("thirteenf.json")
    prev = load(OUT) or {}
    hist = load(HIST) or []
    force = os.environ.get("OPINION_FORCE") == "1"
    fresh = False
    try:
        last = datetime.datetime.fromisoformat(prev.get("generated", "2000-01-01T00:00:00+09:00"))
        fresh = (now - last) < datetime.timedelta(hours=12)
    except (ValueError, TypeError):
        pass

    op, model = prev.get("opinion"), prev.get("model")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[의견] ANTHROPIC_API_KEY 없음 — 이전 의견 유지")
    elif not fresh or force:
        try:
            op, model = ask(digest(D, C, T))
            al = op.get("allocation") or []
            tot = sum(max(0, a.get("pct", 0)) for a in al) or 100
            for a in al:                                    # 합계 100 으로 보정
                a["pct"] = round(max(0, a.get("pct", 0)) * 100 / tot)
            if al:
                max(al, key=lambda a: a["pct"])["pct"] += 100 - sum(a["pct"] for a in al)
            cp = coin_prices(C)
            hist = [h for h in hist if h.get("date") != now.strftime("%Y-%m-%d")] + [{
                "date": now.strftime("%Y-%m-%d"), "headline": op.get("headline"),
                "stance": op.get("stance"), "calls": calls_of(op, cp)}]
            hist = hist[-60:]
            prev["generated"] = now.isoformat(timespec="minutes")
            print("[의견] 새로 생성:", op.get("headline"))
        except Exception as e:
            print("[의견] 생성 실패 — 이전 의견 유지:", str(e)[:300])
    else:
        print("[의견] 최근 생성분 유지 (12시간 이내)")
    if not op:
        return

    past = track(hist[:-1] if hist and hist[-1].get("date") == now.strftime("%Y-%m-%d") else hist,
                 coin_prices(C))
    out = {"generated": prev.get("generated"), "model": model, "opinion": op, "track": past,
           "asof": {"지표": (D or {}).get("updated"), "코인": (C or {}).get("updated"),
                    "기관": (T or {}).get("latest_period")}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.makedirs("history", exist_ok=True)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
