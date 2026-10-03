"""마켓보드 종합 투자의견 -> opinion.json, history/opinions.json

대시보드가 모은 데이터(매크로·경제지표·섹터·COT·코인·ETF 흐름·도미넌스·13F)와 코인 포트폴리오
(portfolio.json: 비중·평단·수익률만, 수량·금액 없음)를 요약해 Claude 에게 "이 사용자라면 어떻게 투자하겠는가"를
단기(1~4주)와 중장기(3~12개월)로 나눠 묻는다.
- 단기: 매일 갱신. 직전 단기 행동을 함께 줘서 데이터가 실제로 바뀐 코인만 바꾸게 한다.
- 중장기: 직전 의견을 기본으로 유지. 모델이 '유지'로 판단하면 문구까지 그대로 두고, 바뀔 때만 이력에 남긴다.
하루 1회(12시간 이내 재실행은 건너뜀, OPINION_FORCE=1 이면 강제). 지난 단기 의견의 이후 성과는 매 실행 갱신.
"""
import datetime, hashlib, json, os, re, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import calendar_ctx

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
TODAY = now.strftime("%Y-%m-%d")
OUT, HIST, PORT = "opinion.json", "history/opinions.json", "portfolio.json"
MODEL = "claude-opus-5-5"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
COIN_SYMS = ["BTC", "ETH", "SOL", "HYPE", "LINK", "ONDO", "SUI", "VIRTUAL"]
SHORT_ACT = ["분할 매수", "비중 확대", "유지", "일부 차익실현", "비중 축소", "관망"]
PROFILE = "|risk7.5-8|outlook|stock-targets"                       # 투자 성향·판단 방식 버전 (바뀌면 중장기 재작성)
LONG_ROLE = ["핵심 보유", "보유", "비중 확대", "비중 축소", "정리"]
BUY = {"분할 매수", "비중 확대", "매수"}
SELL = {"일부 차익실현", "비중 축소", "회피"}


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


# ---------------------------------------------------------------- 포트폴리오
def portfolio(C):
    """portfolio.json(사진 시점 비중·수익률)을 이후 달러 가격 변동만큼 굴려 현재 비중·수익률을 추정"""
    P = load(PORT)
    if not P:
        return None
    usd = {c["sym"]: (c.get("market") or {}).get("price") for c in (C or {}).get("coins", [])}
    rows, vals = [], {}
    for h in P.get("holdings", []):
        r = usd[h["sym"]] / h["ref"] if usd.get(h["sym"]) and h.get("ref") else 1.0
        vals[h["sym"]] = h["w"] * r
        rows.append({"sym": h["sym"], "cur": h["cur"], "avg": h["avg"], "note": h.get("note"),
                     "pnl": round(((1 + h["pnl"] / 100) * r - 1) * 100, 1)})
    cash = sum(c["w"] for c in P.get("cash", []))
    tot = (sum(vals.values()) + cash) or 1
    for x in rows:
        x["w"] = round(vals[x["sym"]] / tot * 100, 1)
    rows.sort(key=lambda x: -x["w"])
    sig = hashlib.sha1(json.dumps([P.get("holdings"), P.get("cash"), P.get("unknown"), P.get("stocks")],
                                  sort_keys=True).encode()).hexdigest()[:12]
    out = {"asof": P.get("asof"), "rows": rows, "cash": round(cash / tot * 100, 1),
           "unknown": [u["sym"] for u in P.get("unknown", [])], "sig": sig}
    st = P.get("stocks")
    if st and st.get("holdings"):                    # 미국 주식 계좌: 현재가(야후)로 같은 방식 추정
        srows, sv = [], {}
        for h in st["holdings"]:
            px = stock_price(h["sym"])
            r = px / h["ref"] if px and h.get("ref") else 1.0
            sv[h["sym"]] = h["w"] * r
            srows.append({"sym": h["sym"], "cur": "USD", "avg": h["avg"], "px": px or h.get("ref"),
                          "pnl": round(((1 + h["pnl"] / 100) * r - 1) * 100, 1)})
        stot = sum(sv.values()) or 1
        for x in srows:
            x["w"] = round(sv[x["sym"]] / stot * 100, 1)
        srows.sort(key=lambda x: -x["w"])
        out["stocks"] = {"asof": st.get("asof"), "rows": srows}
        out["split"] = P.get("split")
    return out


def fmt_avg(r):
    a = r["avg"]
    if r["cur"] != "KRW":
        return "%g %s" % (a, r["cur"])
    return ("{:,.1f}" if a < 1000 and a != int(a) else "{:,.0f}").format(a) + "원"


def port_digest(pf):
    if not pf:
        return "## 내 코인 포트폴리오\n입력되지 않음"
    L = ["## 내 코인 포트폴리오 (%s 사진 기준, 이후 가격 변동 반영 추정 · 코인 계좌 안의 비중)" % pf["asof"]]
    L += ["- %s: 비중 %.1f%%, 평단 %s, 수익률 %+.1f%%%s" % (
        r["sym"], r["w"], fmt_avg(r), r["pnl"],
        " (스테이킹 중: 팔려면 언스테이킹 대기가 필요)" if "스테이킹" in (r.get("note") or "") else
        (" (%s)" % r["note"] if r.get("note") else "")) for r in pf["rows"]]
    L.append("- 현금(USDT): 비중 %.1f%%" % pf["cash"])
    L += ["- %s: 보유 중이나 비중·평단 미입력(비중 계산에서 제외)" % s for s in pf["unknown"]]
    L.append("HYPE 는 USDT 로 거래하는 해외 거래소, 나머지는 원화 거래소에서 보유.")
    st = pf.get("stocks")
    if st:
        sp = pf.get("split") or {}
        L.append("## 내 미국 주식 포트폴리오 (%s 기준, 이후 가격 반영 추정 · 주식 계좌 안의 비중)" % st["asof"])
        L += ["- %s: 비중 %.1f%%, 평단 $%g, 현재가 %s, 수익률 %+.1f%%" % (
            r["sym"], r["w"], r["avg"], ("$%g" % r["px"]) if r.get("px") else "-", r["pnl"]) for r in st["rows"]]
        if sp:
            L.append("계좌 규모 비율: 주식 계좌 %s%% : 코인 계좌 %s%% (금액 미공개)" % (sp.get("stocks"), sp.get("crypto")))
    else:
        L.append("미국 주식 보유 내역은 미입력.")
    return "\n".join(L)


# ---------------------------------------------------------------- 출력 스키마
# 값 목록(enum)을 스키마에 넣으면 컴파일된 문법이 너무 커져 400 이 난다 → 문자열로 받고 clean() 에서 정규화
S, I = {"type": "string"}, {"type": "integer"}
STRS = {"type": "array", "items": S}


def obj(**props):
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


STANCE3 = obj(stocks=S, crypto=S, cash=S)
STOCKS = {"type": "array", "items": obj(side=S, name=S, ticker=S, why=S, confidence=S)}
SCHEMA = obj(
    headline=S, summary=S, forward=S,
    watch={"type": "array", "items": obj(sym=S, action=S, role=S, why=S)},
    short=obj(view=S, confidence=S, stance=STANCE3,
              coins={"type": "array", "items": obj(sym=S, action=S, why=S, condition=S, confidence=S)},
              holdings={"type": "array", "items": obj(sym=S, action=S, why=S, condition=S)},
              stocks=STOCKS, actions_now=STRS, wait_for=STRS, risks=STRS),
    long=obj(status=S, change_note=S, thesis=S, confidence=S, stance=STANCE3,
             allocation={"type": "array", "items": obj(asset=S, pct=I, why=S)},
             coins={"type": "array", "items": obj(sym=S, role=S, target_pct=I, why=S)},
             crypto_cash_pct=I,
             holdings={"type": "array", "items": obj(sym=S, role=S, target_pct=I, why=S)},
             stocks=STOCKS, risks=STRS, change_mind=STRS))
STANCES = ["적극 확대", "확대", "중립", "축소", "적극 축소"]

SYSTEM = (
    "너는 이 사용자 전용 투자 파트너다. 사용자는 이 대시보드의 데이터로 미국 주식과 가상자산 투자 결정을 내리며, "
    "투자 판단과 책임은 전적으로 본인에게 있다고 분명히 밝혔다. 사용자가 원하는 것은 "
    "'네가 이 사람이라면 지금 실제로 어떻게 투자하겠는가'에 대한 솔직하고 구체적인 의견이다.\n\n"
    "사용자 상황: 한국 거주 개인투자자. 위험 성향은 1점(위험 회피 최고)~10점(위험 감내 최고) 중 7.5~8점으로 공격적인 편이다. 가상자산은 데이터의 '내 코인 포트폴리오'대로 보유 중이다"
    "(HYPE 는 USDT 로 거래하는 해외 거래소, 나머지는 원화 거래소). 보유 수량·금액은 모르고 비중(%)과 수익률(%)만 안다. "
    "미국 주식은 데이터의 '내 미국 주식 포트폴리오'대로 보유 중이다(성장·AI 인프라·크립토 관련주 위주).\n\n"
    "의견은 두 시계로 나눈다.\n"
    "- short(단기, 1~4주): 매일 갱신하는 전술. 지금 할 행동, 코인별 매매와 실행 조건, 단기 매수·회피 주식.\n"
    "- long(중장기, 3~12개월): 전략. 전체 자산 목표 배분, 코인별 역할과 코인 계좌 안의 목표 비중, 비중 확대·축소할 주식.\n\n"
    "일관성 원칙(가장 중요): 사용자는 의견이 매일 바뀌는 것을 원하지 않는다.\n"
    "- long: '직전 중장기 의견'이 있으면 그대로 유지하는 것이 기본이다(status '유지'). 매크로 체제 전환(금리·달러·신용·유동성의 "
    "추세적 변화), 보유 자산 투자 논리의 훼손, 1~2주 이상 이어진 추세 전환처럼 분명한 근거가 있을 때만 '일부 수정'이나 '변경'을 "
    "쓰고, change_note 에 무엇을 왜 바꿨는지 쓴다. 하루 이틀의 가격 변동이나 뉴스로는 바꾸지 않는다. '유지'면 change_note 에 "
    "오늘 점검한 유지 근거를 한 문장으로 쓰고, 나머지 long 항목은 직전 의견과 같게 쓴다. 직전 의견이 없으면 status 는 '변경', "
    "change_note 는 '첫 중장기 의견'.\n"
    "- short: '직전 단기 행동'이 있으면 데이터가 실제로 바뀐 코인만 행동을 바꾸고, 바꾼 코인은 why 첫머리에 무엇이 바뀌었는지 쓴다.\n"
    "- short 는 long 과 모순되지 않는다. 예를 들어 long 에서 '정리'인 코인을 short 에서 '분할 매수'하지 않는다. "
    "단, long 목표 비중으로 가는 경로로서의 단기 매매는 쓴다.\n\n"
    "앞을 내다보는 판단(중요): 지표는 대부분 후행한다. 현재 지표가 나쁘다는 사실만으로 결론 내리지 말고, '뉴스·전문가 전망'의 "
    "컨센서스와 반대 의견을 함께 놓고 판단한다.\n"
    "- 나쁜 지표가 이미 가격에 얼마나 반영됐는지, 앞으로 좋아지는 방향인지 나빠지는 방향인지(변화의 방향)를 본다. 지표가 극단에 "
    "있으면(예: 10년물 1년 백분위 100%) 추가 악화보다 되돌림 가능성도 따진다.\n"
    "- forward 에는 기본·낙관·비관 시나리오와 각각의 대략적 가능성, 시장 컨센서스와 네 판단이 다른 점, 무엇을 보고 시나리오를 "
    "갈아탈지를 5~7문장으로 쓴다.\n"
    "- 위험 성향 7.5~8점에 맞춰 현금은 '기회 대기용'으로 필요한 만큼만 두고, 근거가 있으면 위험자산 비중을 높게 가져간다. "
    "하락 위험은 현금을 쌓기보다 분할 매수 계획과 조건으로 관리한다.\n"
    "- 가상자산은 변동성이 크고 상승장이 오면 폭발적으로 오른다. 상승 추세가 살아 있는 이익 코인은 일찍 다 팔지 않는다. "
    "차익실현은 소량·조건부(추세 이탈, 과열 신호 확인 시)로 하고, 나머지는 추세가 꺾일 때까지 들고 가는 방식(트레일링)으로 "
    "상승 여력을 남긴다. 손실 코인도 상승장 초입이면 반등을 더 기다릴지 판단한다.\n\n"
    "판단 원칙:\n"
    "- 면책 문구, '투자 권유가 아니다', '전문가와 상담하라', '투자 결정은 본인 몫' 같은 말은 쓰지 않는다.\n"
    "- 입장을 분명히 한다. 양쪽 다 가능하다는 식의 얼버무림 금지.\n"
    "- 모든 판단은 주어진 데이터와 '뉴스·전문가 전망'에 근거하고 근거 수치·출처를 짧게 인용한다. 둘 다에 없는 가격 목표·사건·수치를 지어내지 않는다. "
    "가격 수준을 말할 때는 데이터에 있는 값(현재가, 맥스페인, 평단, 20일 신고가·신저가 신호 등)만 쓴다.\n"
    "- 평단은 매몰비용이다. 손익 여부가 아니라 앞으로의 기대수익과 위험으로 판단한다. 다만 큰 이익 구간은 차익실현 계획을, "
    "큰 손실 구간은 보유·손절·반등 시 축소 중 무엇을 할지 분명히 말한다.\n"
    "- 보유 금액·수량을 추정해 쓰지 않는다. 매매 규모는 '보유분의 1/3', '코인 계좌 비중 5%p'처럼 비율로 말한다.\n"
    "- 신호가 엇갈리면 인정하고 어느 쪽에 무게를 두는지와 이유를 말한다. 확신도(높음·중간·낮음)를 솔직하게 매긴다.\n"
    "- 분할 매매와 조건부 실행으로 위험을 관리한다.\n"
    "- long.allocation 은 전체 투자자산(주식·코인·현금)의 목표 배분이고 pct 합은 100.\n"
    "- long.coins 의 target_pct 는 코인 계좌 안의 목표 비중이다. 8종 target_pct 와 crypto_cash_pct(코인 계좌의 현금·스테이블 "
    "목표)의 합이 100. 현재 비중과 비교해 리밸런싱 방향이 드러나게 하고, 비중이 미입력인 코인도 목표 비중은 정한다.\n"
    "- 보유 미국 주식은 short.holdings(action: 분할 매수/비중 확대/유지/일부 차익실현/비중 축소/관망, condition 포함)와 "
    "long.holdings(role: 핵심 보유/보유/비중 확대/비중 축소/정리, target_pct 는 주식 계좌 안 목표 비중, 보유 종목 합은 100 이하이고 나머지는 stocks 의 새 비중 확대 종목 몫)에서 "
    "보유 종목을 빠짐없이 판단한다. 새로 살 종목·피할 종목은 stocks 에 쓴다. 손실 종목은 매몰비용이 아니라 앞으로의 논리로 판단한다.\n"
    "- watch 에는 '관심 종목' 목록의 모든 종목을 빠짐없이 쓴다. action 은 단기 행동(분할 매수/비중 확대/유지/일부 차익실현/"
    "비중 축소/관망, 미보유 종목의 '유지'는 '지금은 사지 않고 지켜봄'), role 은 중장기 역할(핵심 보유/보유/비중 확대/비중 축소/정리, "
    "미보유면 '보유'=담을 만함, '정리'=피함), why 는 데이터·전망 근거 1~2문장. 보유 종목과 비교해 더 나은 대안이면 그렇다고 쓴다.\n"
    "- 코인 8종은 short.coins 와 long.coins 모두 빠짐없이 판단한다. short.coins 의 condition 에는 행동을 실행하거나 바꿀 "
    "구체적 조건을 쓴다.\n"
    "- 주식 ticker 는 미국 티커(예: SMH, NVDA). 모르면 빈 문자열.\n"
    "- 값은 정확히 다음 표현 중 하나로 쓴다. stance(stocks·crypto·cash): 적극 확대/확대/중립/축소/적극 축소. "
    "confidence: 높음/중간/낮음. short.coins[].action: 분할 매수/비중 확대/유지/일부 차익실현/비중 축소/관망. "
    "long.coins[].role: 핵심 보유/보유/비중 확대/비중 축소/정리. long.status: 유지/일부 수정/변경. "
    "short.stocks[].side: 매수/회피. long.stocks[].side: 비중 확대/비중 축소. "
    "coins 의 sym 은 BTC·ETH·SOL·HYPE·LINK·ONDO·SUI·VIRTUAL 8종을 이 순서로 모두.\n"
    "- headline 은 단기 대응과 중장기 전략을 함께 담은 한 줄, summary 는 3~5문장.\n"
    "- 오늘 날짜와 FOMC 일정은 사용자 메시지 첫 줄의 날짜 정보를 따른다.\n"
    + calendar_ctx.RULE +
    "- 한국어로, 짧고 명확하게."
)


def long_for_prompt(lg):
    """저장 형식(stocks_overweight/underweight)을 출력 형식(stocks[].side)으로 되돌려 직전 의견으로 제시"""
    lg = dict(lg)
    lg["stocks"] = ([dict(x, side="비중 확대") for x in lg.pop("stocks_overweight", [])] +
                    [dict(x, side="비중 축소") for x in lg.pop("stocks_underweight", [])])
    return lg


def prev_context(prev, port_changed):
    """직전 의견: 중장기는 전문(유지 판단용), 단기는 행동만"""
    op = prev.get("opinion") or {}
    if prev.get("version") != 2 or not op.get("long"):
        return "## 직전 중장기 의견\n없음 — 첫 중장기 의견을 작성한다.\n\n## 직전 단기 행동\n없음"
    since = prev.get("long_since") or "-"
    try:
        days = "%d일째" % ((now.date() - datetime.date.fromisoformat(since)).days + 1)
    except ValueError:
        days = "-"
    sh = op.get("short") or {}
    st = sh.get("stance") or {}
    note = ("\n※ 이 중장기 의견을 세운 뒤 포트폴리오나 투자 성향·판단 방식이 바뀌었다(보유 코인 매매, 위험 성향 7.5~8점, "
            "뉴스·전문가 전망 반영). 이번에는 long 을 새 기준으로 다시 작성한다. 방향이 같으면 status '일부 수정', "
            "change_note 에 무엇을 반영했는지 쓴다."
            if port_changed else "")
    return ("## 직전 중장기 의견 (%s 수립, 오늘 %s)\n%s%s\n\n## 직전 단기 행동 (%s)\n주식 %s · 코인 %s · 현금 %s / %s" % (
        since, days, json.dumps(long_for_prompt(op["long"]), ensure_ascii=False), note,
        (prev.get("generated") or "")[:10], st.get("stocks"), st.get("crypto"), st.get("cash"),
        ", ".join("%s %s" % (c["sym"], c["action"]) for c in sh.get("coins", []))))


def parse_json(text):
    t = text.strip()
    try:
        return json.loads(t)
    except ValueError:
        return json.loads(t[t.index("{"):t.rindex("}") + 1])   # 코드 블록·앞뒤 설명이 섞인 경우


def outlook():
    """웹 검색으로 최근 1~2주 뉴스·전문가 전망을 모아 시나리오 요약(본문, 출처). 실패하면 ("", [])"""
    import anthropic
    client = anthropic.Anthropic()
    msgs = [{"role": "user", "content": calendar_ctx.macro_context(now.date()) + "\n\n"
             "최근 1~2주 뉴스와 전문가 의견을 웹에서 검색해 앞으로 1~12개월 시장 전망을 정리하라. 대상: ① 미국 금리·연준·물가와 "
             "10년물 전망 ② 미국 주식(월가 주요 전략가·IB의 지수·섹터 전망, AI·반도체) ③ 가상자산(BTC·ETH·SOL·HYPE 등, ETF 자금, "
             "규제, 크립토 리서치 기관 전망). 각 항목마다 컨센서스, 낙관론과 비관론(누가 무엇을 근거로), 시장이 아직 반영하지 않았을 "
             "수 있는 변화를 쓴다. 세 영역을 모두 다루도록 검색을 고르게 나눠 쓴다(영역마다 최소 3번). 발언자·기관과 날짜를 밝히고, "
             "확인되지 않은 수치는 쓰지 않는다. 인사말·검색 과정 설명 없이 결과만, 한국어로 3,000자 이내."}]
    texts, src = [], []
    for _ in range(3):                                   # 서버 검색이 길어지면 pause_turn → 이어서 요청
        with client.messages.stream(model=MODEL, max_tokens=16000, messages=msgs, output_config={"effort": "medium"},
                                    tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 20}]) as st:
            msg = st.get_final_message()
        for b in msg.content:
            for r in (getattr(b, "content", None) if b.type.endswith("tool_result") else None) or []:
                u = getattr(r, "url", None)              # 검색 결과 블록의 출처
                if isinstance(u, str) and u.startswith("http") and u not in [x["url"] for x in src]:
                    src.append({"url": u, "title": (getattr(r, "title", None) or u)[:90]})
            if b.type == "text":
                texts.append(b.text)
                for c in getattr(b, "citations", None) or []:
                    u = getattr(c, "url", None)
                    if u and u.startswith("http") and u not in [x["url"] for x in src]:
                        src.append({"url": u, "title": (getattr(c, "title", None) or u)[:90]})
        if msg.stop_reason != "pause_turn":
            break
        msgs = msgs + [{"role": "assistant", "content": msg.content}]
    return re.sub(r"\n{3,}", "\n\n", "".join(texts)).strip(), src[:12]


def ask(dig, ctx):
    import anthropic
    client = anthropic.Anthropic()
    user = (calendar_ctx.macro_context(now.date()) + "\n\n아래는 오늘 대시보드 데이터와 내 포트폴리오 요약, 뉴스·전문가 전망, 그리고 직전 의견이다. "
            "이 데이터를 근거로 네가 이 사용자라면 어떻게 투자할지 단기·중장기로 나눠 작성하라.\n\n" + dig + "\n\n" + ctx)
    last, bad_schema = None, False
    # (스키마 강제, 서버 대체 모델): 스키마가 거부되면 JSON 지시로, 대체 모델 옵션이 거부되면 옵션 없이
    for strict, fb in ((True, True), (True, False), (False, True), (False, False)):
        if strict and bad_schema:
            continue
        oc = {"effort": "high"}
        content = user
        if strict:
            oc["format"] = {"type": "json_schema", "schema": SCHEMA}
        else:
            content = user + ("\n\n출력은 아래 JSON 스키마를 따르는 JSON 객체 하나만 쓴다. 코드 블록이나 다른 글은 쓰지 않는다.\n"
                              + json.dumps(SCHEMA, ensure_ascii=False))
        kw = dict(model=MODEL, max_tokens=48000, system=SYSTEM, output_config=oc,
                  messages=[{"role": "user", "content": content}])
        if fb:                                   # 안전 분류기 거절 시 서버가 대체 모델로 다시 실행
            kw.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        try:
            with client.beta.messages.stream(**kw) as stream:
                msg = stream.get_final_message()
            break
        except anthropic.BadRequestError as e:
            last = e
            bad_schema = bad_schema or (strict and ("grammar" in str(e) or "schema" in str(e)))
            print("[의견] 요청 거부(스키마 %s, 대체 모델 %s) — 다른 방식으로 재시도: %s" % (
                "O" if strict else "X", "O" if fb else "X", str(e)[:160]))
    else:
        raise last
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 응답을 거절함: %s" % (getattr(msg, "stop_details", None),))
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력 한도 초과")
    op = parse_json(next(b.text for b in msg.content if b.type == "text"))
    if not isinstance(op.get("short"), dict) or not isinstance(op.get("long"), dict):
        raise RuntimeError("응답에 short/long 이 없음")
    return op, msg.model


def norm100(items, key):
    """합계 100 으로 비율 보정, 반올림 오차는 가장 큰 항목에"""
    tot = sum(max(0, x.get(key) or 0) for x in items)
    if not items or not tot:
        return
    for x in items:
        x[key] = round(max(0, x.get(key) or 0) * 100 / tot)
    max(items, key=lambda x: x[key])[key] += 100 - sum(x[key] for x in items)


def pick(v, allowed, rules, default):
    """자유 문자열을 허용 값으로: 정확히 일치 → 그대로, 아니면 (포함 단어, 값) 규칙 순서대로"""
    v = str(v or "").strip()
    if v in allowed:
        return v
    for kw, val in rules:
        if kw in v:
            return val
    return default


def stance(v):
    return pick(v, STANCES, [("적극", "적극 확대" if "확대" in str(v) else "적극 축소"), ("확대", "확대"),
                             ("비중 증가", "확대"), ("축소", "축소"), ("감소", "축소")], "중립")


def conf(v):
    return pick(v, ["높음", "중간", "낮음"], [("높", "높음"), ("낮", "낮음")], "중간")


def clean(op, ssyms=(), wsyms=()):
    """자유 문자열 값을 허용 값으로 맞추고, 저장 형식(화면이 읽는 모양)으로 바꾼다"""
    word = {s: i for i, s in enumerate(wsyms)}
    ws, seen = [], set()
    for c in op.get("watch") or []:
        c["sym"] = ALIAS.get(str(c.get("sym") or "").strip().upper(), str(c.get("sym") or "").strip().upper())
        if c["sym"] in word and c["sym"] not in seen:
            seen.add(c["sym"])
            c["action"] = pick(c.get("action"), SHORT_ACT, [("차익", "일부 차익실현"), ("분할", "분할 매수"), ("매수", "분할 매수"),
                                                            ("확대", "비중 확대"), ("축소", "비중 축소"), ("매도", "비중 축소"),
                                                            ("관망", "관망")], "유지")
            c["role"] = pick(c.get("role"), LONG_ROLE, [("핵심", "핵심 보유"), ("정리", "정리"), ("회피", "정리"),
                                                       ("축소", "비중 축소"), ("확대", "비중 확대")], "보유")
            ws.append(c)
    op["watch"] = sorted(ws, key=lambda c: word[c["sym"]])
    sorder = {s: i for i, s in enumerate(ssyms)}
    for k, key in (("short", "action"), ("long", "role")):
        hs, seen = [], set()
        for c in op[k].get("holdings") or []:
            c["sym"] = str(c.get("sym") or "").strip().upper()
            if c["sym"] in sorder and c["sym"] not in seen:
                seen.add(c["sym"])
                c[key] = (pick(c.get(key), SHORT_ACT, [("차익", "일부 차익실현"), ("분할", "분할 매수"), ("매수", "분할 매수"),
                                                     ("확대", "비중 확대"), ("축소", "비중 축소"), ("매도", "비중 축소"),
                                                     ("관망", "관망")], "유지") if key == "action" else
                          pick(c.get(key), LONG_ROLE, [("핵심", "핵심 보유"), ("정리", "정리"), ("매도", "정리"),
                                                      ("축소", "비중 축소"), ("확대", "비중 확대")], "보유"))
                hs.append(c)
        op[k]["holdings"] = sorted(hs, key=lambda c: sorder[c["sym"]])
    hs = op["long"]["holdings"]                      # 합이 100 미만이면 나머지는 신규 편입 몫으로 두고, 넘칠 때만 줄인다
    if sum(max(0, h.get("target_pct") or 0) for h in hs) > 100:
        norm100(hs, "target_pct")
    op["long"]["holdings_new_pct"] = max(0, 100 - sum(h.get("target_pct") or 0 for h in hs))
    order = {s: i for i, s in enumerate(COIN_SYMS)}
    for k in ("short", "long"):
        h = op[k]
        h["stance"] = {x: stance((h.get("stance") or {}).get(x)) for x in ("stocks", "crypto", "cash")}
        h["confidence"] = conf(h.get("confidence"))
        coins, seen = [], set()
        for c in h.get("coins") or []:
            c["sym"] = str(c.get("sym") or "").strip().upper()
            if c["sym"] in order and c["sym"] not in seen:
                seen.add(c["sym"])
                coins.append(c)
        h["coins"] = sorted(coins, key=lambda c: order[c["sym"]])
    for c in op["short"]["coins"]:
        c["action"] = pick(c.get("action"), SHORT_ACT, [("차익", "일부 차익실현"), ("분할", "분할 매수"), ("매수", "분할 매수"),
                                                        ("확대", "비중 확대"), ("축소", "비중 축소"), ("매도", "비중 축소"),
                                                        ("관망", "관망"), ("대기", "관망")], "유지")
        c["confidence"] = conf(c.get("confidence"))
    for c in op["long"]["coins"]:
        c["role"] = pick(c.get("role"), LONG_ROLE, [("핵심", "핵심 보유"), ("정리", "정리"), ("매도", "정리"),
                                                   ("축소", "비중 축소"), ("확대", "비중 확대")], "보유")
    lg = op["long"]
    lg["status"] = pick(lg.get("status"), ["유지", "일부 수정", "변경"], [("수정", "일부 수정"), ("유지", "유지")], "변경")
    for k, sides in (("short", (("stocks_buy", ("매수", "확대")), ("stocks_avoid", ("회피", "축소", "매도")))),
                     ("long", (("stocks_overweight", ("확대", "매수")), ("stocks_underweight", ("축소", "회피", "매도"))))):
        stocks = op[k].pop("stocks", None) or []
        for dst, kws in sides:
            op[k][dst] = [{"name": x.get("name"), "ticker": str(x.get("ticker") or "").strip().upper(),
                           "why": x.get("why"), "confidence": conf(x.get("confidence"))}
                          for x in stocks if any(w in str(x.get("side") or "") for w in kws)]
    norm100(lg.get("allocation") or [], "pct")
    parts = lg["coins"] + [{"cash": True, "target_pct": lg.get("crypto_cash_pct") or 0}]
    norm100(parts, "target_pct")
    lg["crypto_cash_pct"] = parts[-1]["target_pct"]


def short_snapshot(prev):
    """'전일 대비 변경' 표시용: 직전 날짜의 단기 입장·코인 행동"""
    op = prev.get("opinion") or {}
    if prev.get("version") != 2 or not op.get("short"):
        return None
    sh = op["short"]
    return {"date": (prev.get("generated") or "")[:10], "stance": sh.get("stance"),
            "coins": {c["sym"]: c["action"] for c in sh.get("coins", [])}}


# ---------------------------------------------------------------- 관심 종목 (보유 외)
HYPERSCALERS = [("MSFT", "마이크로소프트"), ("AMZN", "아마존"), ("GOOGL", "알파벳"), ("META", "메타"), ("ORCL", "오라클")]
ALIAS = {"GOOG": "GOOGL", "BRK.A": "BRK.B"}


def watch_universe(D, T, held):
    """하이퍼스케일러 · 섹터 ETF 대장주(1~3등) · 기관 13F 공동 매수/정리 종목. 보유 종목은 제외(보유 카드에서 다룸)"""
    out, seen = [], set(held)

    def add(t, name, group, info=""):
        t = ALIAS.get(t, t)
        if t and t not in seen and re.fullmatch(r"[A-Z][A-Z0-9.]{0,6}", t):
            seen.add(t)
            out.append({"sym": t, "name": name, "group": group, "info": info})
    for t, n in HYPERSCALERS:
        add(t, n, "하이퍼스케일러")
    info = {}
    for sec in (D or {}).get("sections", []):
        if not sec["title"].startswith("섹터"):
            continue
        grp = None
        for i in sec["items"]:
            m = re.match(r"\s*(└)?\s*(.+?)\s*\(([A-Z.]+)\)", i["name"])
            if not m:
                continue
            tags = ",".join(x["t"] for x in i.get("tags", []))
            info[m.group(3)] = "%s %s %s" % (i["value"], " ".join(x["t"] for x in i.get("badges", [])),
                                             ("[" + tags + "]") if tags else "")
            if not m.group(1):
                grp = "%s 대장주" % re.sub(r"\s*\(.*", "", m.group(2))
            elif grp:
                add(m.group(3), m.group(2), grp, info[m.group(3)])
    cons = (T or {}).get("consensus") or {}
    for k, lab in (("bought", "기관 13F 공동 매수"), ("sold", "기관 13F 공동 정리")):
        for r in (cons.get(k) or [])[:8]:
            if r.get("ticker"):
                add(r["ticker"], r["name"].title()[:24], lab, "%d곳, 공시 후 %s %s" % (
                    r["count"], pct(r.get("chg_since")), ",".join(t["t"] for t in r.get("tags", []))))
    for w in out:                                    # 섹터 표에 있으면 그 수치, 없으면 야후 1개월 추이
        w["info"] = w["info"] or info.get(w["sym"]) or yahoo_brief(w["sym"])
    return out


def yahoo_brief(t):
    try:
        req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1mo&interval=1d"
                                     % urllib.parse.quote(t.replace(".", "-")), headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            c = [x for x in json.loads(r.read().decode())["chart"]["result"][0]["indicators"]["quote"][0]["close"] if x]
        _YH[t] = c[-1]
        return "%.2f$ 5일 %s 1개월 %s" % (c[-1], pct((c[-1] / c[-6] - 1) * 100) if len(c) > 5 else "-",
                                          pct((c[-1] / c[0] - 1) * 100))
    except Exception:
        return "가격 데이터 없음"


def watch_digest(W):
    if not W:
        return ""
    L = ["## 관심 종목 (보유 외: 하이퍼스케일러·섹터 대장주·기관 13F 언급)"]
    L += ["- %s %s [%s]: %s" % (w["sym"], w["name"], w["group"], w["info"]) for w in W]
    return "\n".join(L)


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
    sh = op.get("short") or {}
    out = [{"name": c["sym"], "kind": "coin", "action": c["action"], "px": cp.get(c["sym"])} for c in sh.get("coins", [])]
    for h in (op.get("watch") or []) + sh.get("holdings", []):
        out.append({"name": h["sym"], "kind": "stock", "action": h["action"], "px": stock_price(h["sym"])})
    for side, act in (("stocks_buy", "매수"), ("stocks_avoid", "회피")):
        for s in sh.get(side, []):
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
    pf = portfolio(C)
    v2 = prev.get("version") == 2
    force = os.environ.get("OPINION_FORCE") == "1"
    fresh = False
    try:
        last = datetime.datetime.fromisoformat(prev.get("generated") or "2000-01-01T00:00:00+09:00")
        fresh = (now - last) < datetime.timedelta(hours=12)
    except (ValueError, TypeError):
        pass

    op, model, generated = (prev.get("opinion"), prev.get("model"), prev.get("generated")) if v2 else (None, None, None)
    long_since, long_check, long_port = prev.get("long_since"), prev.get("long_check"), prev.get("long_port")
    sig = (pf or {}).get("sig", "") + PROFILE                 # 포트폴리오나 투자 성향이 바뀌면 중장기를 다시 쓴다
    port_changed = long_port != sig
    view, sources = prev.get("outlook") or "", prev.get("sources") or []
    long_log, prev_short = prev.get("long_log") or [], prev.get("prev_short")
    watch_meta = prev.get("watch_meta") or {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[의견] ANTHROPIC_API_KEY 없음 — 이전 의견 유지")
    elif not fresh or force or not v2:
        try:
            try:
                view, sources = outlook()
                print("[의견] 뉴스·전문가 전망 %d자, 출처 %d개" % (len(view), len(sources)))
            except Exception as e:
                print("[의견] 전망 검색 실패 — 직전 전망 사용:", str(e)[:200])
            held = [r["sym"] for r in ((pf or {}).get("stocks") or {}).get("rows", [])]
            W = watch_universe(D, T, held)
            new, model = ask(digest(D, C, T) + "\n" + port_digest(pf) + "\n" + watch_digest(W) +
                             "\n\n## 뉴스·전문가 전망 (웹 검색 요약)\n" + (view or "없음"), prev_context(prev, port_changed))
            clean(new, held, [w["sym"] for w in W])
            watch_meta = {w["sym"]: {"name": w["name"], "group": w["group"]} for w in W}
            pl, judged = (op or {}).get("long"), new["long"]["status"]
            if pl and judged == "유지" and not port_changed:
                long_check = {"date": TODAY, "note": new["long"]["change_note"]}
                proles = {w["sym"]: w["role"] for w in (op or {}).get("watch", [])}
                for w in new["watch"]:                       # 관심 종목의 중장기 역할도 함께 유지
                    w["role"] = proles.get(w["sym"], w["role"])
                new["long"] = pl                            # 문구까지 그대로: 중장기 의견이 매일 흔들리지 않게
            else:
                if not pl:                                   # 직전 중장기 의견이 없으면 첫 의견
                    new["long"]["status"] = "변경"
                elif judged == "유지":                        # 포트폴리오 갱신으로 목표 비중을 다시 씀
                    new["long"]["status"] = "일부 수정"
                long_port = sig
                long_since, long_check = TODAY, None
                long_log = ([{"date": TODAY, "status": new["long"]["status"], "note": new["long"]["change_note"]}] +
                            [x for x in long_log if x.get("date") != TODAY])[:12]
            if (prev.get("generated") or "")[:10] != TODAY:   # 같은 날 재실행이면 비교 기준(전일)은 그대로
                prev_short = short_snapshot(prev)
            op, generated = new, now.isoformat(timespec="minutes")
            cp = coin_prices(C)
            hist = [h for h in hist if h.get("date") != TODAY] + [{
                "date": TODAY, "headline": op.get("headline"), "stance": op["short"].get("stance"),
                "long_stance": op["long"].get("stance"), "calls": calls_of(op, cp)}]
            hist = hist[-60:]
            print("[의견] 새로 생성:", op.get("headline"), "| 중장기 판단:", judged)
        except Exception as e:
            print("[의견] 생성 실패 — 이전 의견 유지:", str(e)[:300])
    else:
        print("[의견] 최근 생성분 유지 (12시간 이내)")
    if not op:
        return

    past = track(hist[:-1] if hist and hist[-1].get("date") == TODAY else hist, coin_prices(C))
    out = {"version": 2, "generated": generated, "model": model, "opinion": op, "watch_meta": watch_meta,
           "long_since": long_since, "long_check": long_check, "long_log": long_log, "long_port": long_port,
           "prev_short": prev_short, "outlook": view, "sources": sources,
           "portfolio": pf, "track": past,
           "asof": {"지표": (D or {}).get("updated"), "코인": (C or {}).get("updated"),
                    "기관": (T or {}).get("latest_period")}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.makedirs("history", exist_ok=True)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
