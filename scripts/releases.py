"""미국 경제지표 발표 + 발표일 시장 반응 + 물가 항목별 기여도 + AI 해석 -> data.json["econ"]

지표: 실업률, CPI(근원), PPI(근원), PCE(근원), GDP 성장률
- 수치: FRED 공개 CSV (키 불필요, BLS·BEA 원자료)
- 발표일·시장 예상치: 새 발표가 감지될 때만 Claude 웹검색 1회 (결과는 history/releases.json 에 보관)
  · 매일 실행에서 새 관측치를 처음 본 날(미국 날짜)도 발표일로 기록
- 발표일 시장 반응: 전 거래일 종가 대비 발표일 종가 (S&P500·나스닥·미 10년물·달러·금·비트코인)
- 물가 기여도(%p) = 항목 가중치(상대 중요도 근사치) × 항목 전월비
"""
import csv, datetime, io, json, os, re, sys, time, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(__file__))
import calendar_ctx

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
STATE = "history/releases.json"
KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# FRED 시리즈 → BLS 원 시리즈 (FRED 가 느리거나 막힐 때 BLS 공식 API 로 대체)
BLS_ID = {"UNRATE": "LNS14000000", "CPIAUCSL": "CUSR0000SA0", "CPILFESL": "CUSR0000SA0L1E",
          "PPIFIS": "WPSFD4", "PPIFES": "WPSFD49104", "PPIFDG": "WPSFD41", "PPIFDS": "WPSFD42"}
_BLS = None


_FRED_DOWN = False       # 한 번 완전히 실패하면 이번 실행에서는 FRED 를 건너뛴다 (시간 초과 누적 방지)


def _fred_csv(sid, start):
    global _FRED_DOWN
    if _FRED_DOWN:
        raise RuntimeError("FRED 건너뜀")
    txt = None
    for t in (30, 60):
        try:
            txt = get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s" % (sid, start), t)
            break
        except Exception as e:
            print("  ! FRED %s (%ss): %s" % (sid, t, e))
    if txt is None:
        _FRED_DOWN = True
        raise RuntimeError("FRED 응답 없음")
    out = []
    for r in list(csv.reader(io.StringIO(txt)))[1:]:
        if len(r) >= 2 and r[1] not in ("", "."):
            try:
                out.append((r[0], float(r[1])))
            except ValueError:
                pass
    return out


def _bls_all():
    """BLS 공개 API v1 (키 없음, 1회 25개 시리즈) — 필요한 BLS 시리즈를 한 번에"""
    global _BLS
    if _BLS is None:
        ids = sorted(set(BLS_ID.values()) | {sid for sid, _, _ in CPI_MAIN + CPI_DETAIL})
        y = now.year
        body = json.dumps({"seriesid": ids[:25], "startyear": str(y - 3), "endyear": str(y)}).encode()
        req = urllib.request.Request("https://api.bls.gov/publicAPI/v1/timeseries/data/", data=body,
                                     headers=dict(UA, **{"Content-Type": "application/json"}))
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode())
        _BLS = {}
        for ser in (j.get("Results") or {}).get("series") or []:
            pts = []
            for x in ser.get("data") or []:
                if re.fullmatch(r"M\d\d", x.get("period", "")) and x["period"] != "M13":
                    try:
                        pts.append(("%s-%s-01" % (x["year"], x["period"][1:]), float(x["value"])))
                    except ValueError:
                        pass
            _BLS[ser["seriesID"]] = sorted(pts)
        print("  BLS API 시리즈 %d개" % len(_BLS))
    return _BLS


# FRED 시리즈 → DBnomics 의 BEA 원 시리즈 (PCE·GDP 는 BLS 에 없으므로)
DBN_ID = {"PCEPI": "BEA/NIPA-T20804/DPCERG-M", "PCEPILFE": "BEA/NIPA-T20804/DPCCRG-M",
          "DGDSRG3M086SBEA": "BEA/NIPA-T20804/DGDSRG-M", "DSERRG3M086SBEA": "BEA/NIPA-T20804/DSERRG-M",
          "DFXARG3M086SBEA": "BEA/NIPA-T20804/DFXARG-M", "DNRGRG3M086SBEA": "BEA/NIPA-T20804/DNRGRG-M",
          "A191RL1Q225SBEA": "BEA/NIPA-T10101/A191RL-Q"}


def _dbnomics(code):
    j = json.loads(get("https://api.db.nomics.world/v22/series/%s?observations=1" % code, 60))
    doc = j["series"]["docs"][0]
    out = []
    for p, v in zip(doc["period"], doc["value"]):
        if v in (None, "NA"):
            continue
        m = re.fullmatch(r"(\d{4})-Q(\d)", p)
        d = "%s-%02d-01" % (m.group(1), (int(m.group(2)) - 1) * 3 + 1) if m else p + "-01"
        out.append((d, float(v)))
    return out


def fred(sid, start="2022-01-01"):
    """[(YYYY-MM-DD, float)] 과거->최신. FRED 실패 시 BLS 원 시리즈로 대체"""
    try:
        out = _fred_csv(sid, start)
    except Exception:
        out = []
    if len(out) < 3:
        bid = BLS_ID.get(sid, sid if sid.startswith("CUSR") else None)
        if bid:
            out = [x for x in _bls_all().get(bid, []) if x[0] >= start]
    if len(out) < 3 and sid in DBN_ID:
        try:
            out = [x for x in _dbnomics(DBN_ID[sid]) if x[0] >= start]
        except Exception as e:
            print("  ! DBnomics %s: %s" % (sid, e))
    if len(out) < 3:
        raise ValueError("%s 데이터 부족" % sid)
    return out


# ---------- 항목 정의 ----------
# 상대 중요도(가중치, %)는 BLS·BEA 공표치 기준 근사치. 기여도는 '대략적인 크기' 비교용
CPI_MAIN = [  # (FRED id, 이름, 가중치)
    ("CUSR0000SAF1", "식품", 13.6),
    ("CUSR0000SA0E", "에너지", 6.4),
    ("CUSR0000SAH1", "주거비", 35.5),
    ("CUSR0000SACL1E", "근원 상품", 19.3),
]
CPI_CORE_W = 80.0
CPI_DETAIL = [
    ("CUSR0000SETA02", "중고차", 1.9),
    ("CUSR0000SETA01", "신차", 4.3),
    ("CUSR0000SAA", "의류", 2.5),
    ("CUSR0000SAM2", "의료 서비스", 6.7),
    ("CUSR0000SETE", "자동차 보험", 2.8),
    ("CUSR0000SETG01", "항공료", 0.8),
    ("CUSR0000SAS4", "운송 서비스", 6.3),
]
PCE_PARTS = [("DGDSRG3M086SBEA", "상품", 31.5), ("DSERRG3M086SBEA", "서비스", 68.5),
             ("DFXARG3M086SBEA", "식품", 7.6), ("DNRGRG3M086SBEA", "에너지", 4.1)]
PPI_PARTS = [("PPIFDG", "상품", 33.0), ("PPIFDS", "서비스", 65.0)]

MARKETS = [("^GSPC", "S&P500", "pct"), ("^IXIC", "나스닥", "pct"), ("^TNX", "미 10년물", "bp"),
           ("DX-Y.NYB", "달러지수", "pct"), ("GC=F", "금", "pct"), ("BTC-USD", "비트코인", "pct")]


def mom(s, i=-1):
    return (s[i][1] / s[i - 1][1] - 1) * 100


def yoy(s, i=-1):
    d = s[i][0]
    prev = [v for dd, v in s if dd == str(int(d[:4]) - 1) + d[4:]]
    return (s[i][1] / prev[0] - 1) * 100 if prev else None


def r2(x):
    return None if x is None else round(x, 2)


def monthly_block(head_id, core_id, name, core_name):
    h, c = fred(head_id), fred(core_id)
    period = h[-1][0]
    return h, c, {
        "period": period,
        "head": {"name": name, "mom": r2(mom(h)), "yoy": r2(yoy(h)),
                 "mom_prev": r2(mom(h, -2)), "yoy_prev": r2(yoy(h, -2))},
        "core": {"name": core_name, "mom": r2(mom(c)), "yoy": r2(yoy(c)),
                 "mom_prev": r2(mom(c, -2)), "yoy_prev": r2(yoy(c, -2))},
        "trend": [{"d": d, "yoy": r2(yoy(h, i))} for i, (d, _) in enumerate(h)
                  if i >= len(h) - 13 and yoy(h, i) is not None],
    }


def contrib(parts, period):
    """[(이름, 가중치, 전월비)] -> 기여도 목록 (같은 기준월만)"""
    out = []
    for sid, nm, w in parts:
        try:
            s = fred(sid)
            if s[-1][0] != period:
                continue
            m = mom(s)
            out.append({"name": nm, "w": w, "mom": r2(m), "pp": round(w / 100 * m, 3)})
        except Exception as e:
            print("  ! %s: %s" % (sid, e))
    return out


def ind_unemp():
    u = fred("UNRATE")
    return {"key": "unemp", "title": "실업률", "period": u[-1][0],
            "value": u[-1][1], "prev": u[-2][1],
            "chg": round(u[-1][1] - u[-2][1], 2),
            "trend": [{"d": d, "v": v} for d, v in u[-13:]]}


def ind_cpi():
    h, c, b = monthly_block("CPIAUCSL", "CPILFESL", "CPI", "근원 CPI")
    main = contrib(CPI_MAIN, b["period"])
    pp = {x["name"]: x["pp"] for x in main}
    if {"주거비", "근원 상품"} <= set(pp) and b["core"]["mom"] is not None:
        main.append({"name": "근원 서비스(주거비 제외)", "w": round(CPI_CORE_W - 35.5 - 19.3, 1),
                     "mom": None, "pp": round(CPI_CORE_W / 100 * mom(c) - pp["주거비"] - pp["근원 상품"], 3)})
    b.update({"key": "cpi", "title": "소비자물가 CPI", "contrib": sorted(main, key=lambda x: -abs(x["pp"])),
              "detail": sorted(contrib(CPI_DETAIL, b["period"]), key=lambda x: -abs(x["pp"]))})
    return b


def ind_ppi():
    h, c, b = monthly_block("PPIFIS", "PPIFES", "PPI", "근원 PPI")
    b.update({"key": "ppi", "title": "생산자물가 PPI",
              "contrib": sorted(contrib(PPI_PARTS, b["period"]), key=lambda x: -abs(x["pp"]))})
    return b


def ind_pce():
    h, c, b = monthly_block("PCEPI", "PCEPILFE", "PCE", "근원 PCE")
    b.update({"key": "pce", "title": "개인소비지출 물가 PCE",
              "contrib": sorted(contrib(PCE_PARTS, b["period"]), key=lambda x: -abs(x["pp"]))})
    return b


def ind_gdp():
    g = fred("A191RL1Q225SBEA", "2019-01-01")
    return {"key": "gdp", "title": "GDP 성장률 (전기비 연율)", "period": g[-1][0],
            "value": g[-1][1], "prev": g[-2][1],
            "trend": [{"d": d, "v": v} for d, v in g[-8:]]}


def build_indicators(state):
    """지표별로 따로 수집. 실패한 지표는 마지막 성공값(state[k]['data'])을 재사용"""
    out = {}
    for k, fn in (("cpi", ind_cpi), ("ppi", ind_ppi), ("pce", ind_pce),
                  ("unemp", ind_unemp), ("gdp", ind_gdp)):
        try:
            out[k] = fn()
        except Exception as e:
            print("  ! %s 수집 실패: %s" % (k, e))
            cached = (state.get(k) or {}).get("data")
            if cached:
                out[k] = dict(cached, stale=True)
    return out


# ---------- 발표일 시장 반응 ----------
_YH = {}


def yahoo_daily(sym):
    if sym not in _YH:
        j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=6mo&interval=1d"
                           % urllib.request.quote(sym)))
        r = j["chart"]["result"][0]
        _YH[sym] = [(datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), c)
                    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]
    return _YH[sym]


def reaction(day):
    """발표일(미국 날짜) 종가 vs 직전 거래일 종가"""
    out = []
    for sym, nm, kind in MARKETS:
        try:
            s = yahoo_daily(sym)
            idx = [i for i, (d, _) in enumerate(s) if d == day]
            if not idx or idx[0] == 0:
                continue
            a, b = s[idx[0] - 1][1], s[idx[0]][1]
            v = round((b - a) * 100, 1) if kind == "bp" else round((b / a - 1) * 100, 2)
            out.append({"name": nm, "kind": kind, "v": v})
        except Exception as e:
            print("  ! 시장 %s: %s" % (sym, e))
    return out


# ---------- Claude ----------
SEARCH_DOMAINS = ["bls.gov", "bea.gov", "cnbc.com", "investing.com", "tradingeconomics.com",
                  "fxstreet.com"]


def claude(prompt, max_tokens=3000, search=False, _retry=True):
    if not KEY:
        return None
    body = {"model": "claude-sonnet-5", "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if search:
        # reuters.com·marketwatch.com 은 Anthropic 크롤러를 막아 목록에 넣으면 요청 전체가 400
        body["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6,
                          "allowed_domains": list(SEARCH_DOMAINS)}]
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "x-api-key": KEY,
                                          "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.loads(r.read().decode())
        txt = "".join(b.get("text", "") for b in res.get("content", [])
                      if isinstance(b, dict) and b.get("type") == "text")
        m = re.search(r"\{[\s\S]*\}", txt)
        if not m:
            print("  ! Claude 응답에 JSON 없음: stop=%s, 텍스트 %d자" % (res.get("stop_reason"), len(txt)))
            return None
        return json.loads(m.group(0))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        print("  ! Claude HTTP %s: %s" % (e.code, msg[:500]))
        blocked = re.findall(r"'([a-z0-9.-]+\.[a-z]+)'", msg) if "not accessible" in msg else []
        if search and _retry and blocked:    # 크롤러 차단 도메인을 빼고 한 번 더
            for d in blocked:
                if d in SEARCH_DOMAINS:
                    SEARCH_DOMAINS.remove(d)
            return claude(prompt, max_tokens, search, _retry=False)
        return None
    except Exception as e:
        print("  ! Claude:", str(e)[:200])
        return None


def period_label(key, period):
    y, m = int(period[:4]), int(period[5:7])
    if key == "gdp":
        q = (m - 1) // 3 + 1
        return "%d년 %d분기(%d~%d월)" % (y, q, m, m + 2)
    return "%d년 %d월" % (y, m)


def period_end(key, period):
    """기준기간의 마지막 날 (발표일은 반드시 이보다 뒤)"""
    y, m = int(period[:4]), int(period[5:7]) + (3 if key == "gdp" else 1)
    if m > 12:
        y, m = y + 1, m - 12
    return (datetime.date(y, m, 1) - datetime.timedelta(days=1)).isoformat()


def lookup_release(items):
    """발표일·시장 예상치 웹검색. items: [(key, 제목, 기준기간)]"""
    q = "\n".join("- %s: 기준기간 %s (key=%s)" % (t, period_label(k, p), k) for k, t, p in items)
    prompt = (
        "오늘은 %s이다. 아래 미국 경제지표의 해당 기준기간 발표에 대해 웹에서 확인하라.\n%s\n"
        "각 지표마다: 실제 발표일(미국 동부 기준 YYYY-MM-DD), 발표 전 시장 예상치(컨센서스).\n"
        "물가지표는 헤드라인과 근원의 전월비·전년비 예상치를, 실업률은 예상 실업률을, "
        "GDP는 해당 분기의 가장 최근 추정치(속보·잠정·확정 중 최신) 발표일과 그 발표의 예상 성장률(연율)을, "
        "어느 추정치인지 함께 한 줄로.\n"
        "확인 못하면 빈 문자열. 추측 금지.\n"
        "출력은 JSON 하나만: {\"key\": {\"release_date\": \"YYYY-MM-DD\", \"consensus\": \"...\"}, ...}"
        % (now.strftime("%Y-%m-%d"), q))
    return claude(prompt, 16000, search=True) or {}


def interpret(ind):
    """지표별 해석. ind: {key: 데이터+반응+예상치}"""
    prompt = (
        "너는 거시경제·시장 애널리스트다. 아래는 최근 발표된 미국 경제지표와 발표일 시장 반응이다.\n"
        + calendar_ctx.macro_context(now.date()) + "\n"
        "지표마다 한국어 3~4문장으로 해석하라:\n"
        "1) 결과 요약 — 예상치(consensus)가 있으면 상회/부합/하회를 명시, 전월·추세와 비교\n"
        "2) 물가지표(cpi·ppi·pce)는 contrib·detail(기여도 %p)을 근거로 어떤 항목이 물가를 끌어올렸거나 "
        "끌어내렸는지 구체적으로 (예: 주거비 +0.12%p, 에너지 −0.05%p)\n"
        "3) 발표일 시장 반응(market)이 이 결과와 어떻게 연결되는지 — 금리·달러·주식·비트코인. "
        "반응이 결과와 반대 방향이면 다른 요인 가능성을 언급\n"
        "4) 연준 정책 경로에 주는 함의 한 문장\n"
        "규칙: 주어진 숫자만 사용, 없는 수치·사건을 만들지 말 것. 기여도는 가중치 근사치 기반임을 감안해 "
        "'약'을 붙일 것. 매수/매도 추천 금지.\n" + calendar_ctx.RULE +
        "출력은 JSON 하나만. 값은 반드시 하나의 문자열(3~4문장 한 문단)이며 하위 객체로 나누지 말 것: "
        "{\"key\": \"해석 문단\", ...}\n\n" + json.dumps(ind, ensure_ascii=False))
    return claude(prompt, 16000) or {}


def main():
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    inds = build_indicators(state)
    us_today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()  # 실행: 미 동부 17:30 무렵

    for k, d in inds.items():                      # 기준기간보다 이른 발표일(잘못된 검색 결과)은 폐기
        st = state.get(k) or {}
        if st.get("release") and st.get("period") == d["period"] and st["release"] <= period_end(k, d["period"]):
            print("  ! %s 발표일 %s 이 기준기간보다 빠름 → 다시 확인" % (k, st["release"]))
            st.update({"release": None, "consensus": "", "market": [], "ai": "", "looked_up2": False})

    need_lookup = []
    for k, d in inds.items():
        st = state.get(k) or {}
        if st.get("period") != d["period"]:           # 새 발표 (또는 첫 실행)
            first_seen = bool(st)                     # 이전 기록이 있으면 오늘이 발표일
            state[k] = {"period": d["period"], "release": us_today if first_seen else None,
                        "consensus": "", "ai": "", "market": []}
            need_lookup.append((k, d["title"], d["period"]))
        elif not state[k].get("release") and not state[k].get("looked_up2"):
            need_lookup.append((k, d["title"], d["period"]))

    if need_lookup:
        print("[발표 확인]", [k for k, _, _ in need_lookup])
        found = lookup_release(need_lookup)
        for k, _, period in need_lookup:
            f = found.get(k) or {}
            rd = str(f.get("release_date") or "")
            ok = re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd) and period_end(k, period) < rd <= us_today
            if ok and not state[k].get("release"):
                state[k]["release"] = rd
            if f.get("consensus"):
                state[k]["consensus"] = str(f["consensus"])[:200]
            if ok:                            # 유효한 발표일을 찾았을 때만 '확인 완료' (아니면 다음 실행에서 재검색)
                state[k]["looked_up2"] = True

    todo = {}
    for k, d in inds.items():
        st = state[k]
        if st.get("release") and not st.get("market"):
            st["market"] = reaction(st["release"])
        # 해석의 근거(발표일·예상치·시장 반응)가 바뀌면 다시 쓴다
        basis = "%s|%s|%d" % (st.get("release"), st.get("consensus"), len(st.get("market") or []))
        bad_ai = str(st.get("ai", "")).startswith("{")      # 예전 버그로 저장된 객체 문자열
        if not st.get("ai") or bad_ai or st.get("ai_basis") != basis:
            todo[k] = {x: d.get(x) for x in ("title", "period", "head", "core", "value", "prev", "chg",
                                             "contrib", "detail")} | \
                {"release": st.get("release"), "consensus": st.get("consensus"), "market": st.get("market"),
                 "period_label": period_label(k, d["period"])}
    if todo:
        ai = interpret(todo)
        for k in todo:
            v = ai.get(k)
            if isinstance(v, dict):           # 항목별로 나눠 답한 경우 한 문단으로
                v = " ".join(str(x).strip() for x in v.values())
            elif isinstance(v, list):
                v = " ".join(str(x).strip() for x in v)
            if v:
                state[k]["ai"] = str(v).strip()
                state[k]["ai_basis"] = "%s|%s|%d" % (state[k].get("release"), state[k].get("consensus"),
                                                    len(state[k].get("market") or []))

    items = []
    for k in ("cpi", "ppi", "pce", "unemp", "gdp"):
        if k not in inds:
            continue
        d, st = inds[k], state[k]
        if not d.get("stale"):
            st["data"] = {x: y for x, y in d.items() if x not in ("release", "consensus", "market", "ai")}
        d.update({"release": st.get("release"), "consensus": st.get("consensus", ""),
                  "market": st.get("market", []), "ai": st.get("ai", "")})
        items.append(d)

    os.makedirs("history", exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    with open("data.json", encoding="utf-8") as f:
        payload = json.load(f)
    payload["econ"] = {"items": items, "updated": now.strftime("%Y-%m-%d %H:%M KST"),
                       "src": "FRED(BLS·BEA)"}
    day = now.strftime("%Y-%m-%d")
    for p in ("data.json", "reports/%s.json" % day):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    print("releases done:", [(x["key"], x["period"], x.get("release")) for x in items])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:           # 지표 수집 실패가 나머지 리포트를 막지 않도록
        print("releases 실패:", e)
