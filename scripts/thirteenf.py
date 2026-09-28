"""
thirteenf.py — 13F 포트폴리오 + 인물 뉴스 수집기

thirteenf.json 을 생성한다. 13F 는 분기 1회 공시라 보유내역은 주 1회만,
뉴스는 매일 갱신하도록 --mode 로 분리했다. 한쪽만 돌려도 기존 JSON 의
나머지 절반은 그대로 보존된다.

의존성:
    pip install requests

실행:
    python scripts/thirteenf.py --mode 13f    # 보유내역만 (주 1회, 토요일)
    python scripts/thirteenf.py --mode news   # 뉴스만 (매일)
    python scripts/thirteenf.py               # 둘 다
    python scripts/thirteenf.py --verify-cik  # CIK 등록명만 출력하고 종료
"""

import argparse
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------- 설정

UA = "market-dashboard/1.0 (oops824@gmail.com)"
OUT_PATH = "thirteenf.json"
SEC_SLEEP = 0.15          # SEC 권고 10 req/s 이내
TOP_N = 15                # 카테고리별 상위 보유 종목 표시 수
CONSENSUS_MIN = 2         # 몇 명 이상 겹치면 '공통 매매'로 볼지
CONSENSUS_MAX_POS = 1500  # 보유 종목이 이보다 많으면 공통 매매 집계에서 제외
STALE_DAYS = 200          # 최신 공시가 이보다 오래되면 제출중단으로 표시

# CIK 는 2026-09-28 기준 SEC EDGAR / 13f.info 에서 등록명을 대조해 검증 완료.
# 운용사를 추가할 때는 반드시 --verify-cik 로 등록명을 먼저 확인할 것.
MANAGERS = [
    # (표시명, CIK, 카테고리, 등록명 확인 키워드)
    # 키워드가 SEC 등록명에 없으면 CIK 오류로 보고 수집하지 않는다
    ("버크셔 해서웨이 (버핏)",      "0001067983", "value", "BERKSHIRE"),
    ("아이칸 (칼 아이칸)",          "0000921669", "value", "ICAHN"),
    ("퍼싱스퀘어 (애크먼)",         "0001336528", "value", "PERSHING"),
    ("바우포스트 (클라만)",         "0001061768", "value", "BAUPOST"),
    ("그린라이트 (아인혼)",         "0001079114", "value", "GREENLIGHT"),

    ("브리지워터 (달리오)",         "0001350694", "macro", "BRIDGEWATER"),
    ("듀케인 (드러켄밀러)",         "0001536411", "macro", "DUQUESNE"),
    ("소로스 펀드 매니지먼트",      "0001029160", "macro", "SOROS"),
    ("아팔루사 (테퍼)",             "0001656456", "macro", "APPALOOSA"),
    ("튜더 (폴 튜더 존스)",         "0000923093", "macro", "TUDOR"),

    ("시타델 (켄 그리핀)",          "0001423053", "multi", "CITADEL"),
    ("밀레니엄 (잉글랜더)",         "0001273087", "multi", "MILLENNIUM"),
    ("포인트72 (스티브 코헨)",      "0001603466", "multi", "POINT72"),
    ("르네상스 테크놀로지",         "0001037389", "multi", "RENAISSANCE"),
    ("엘리엇 (폴 싱어)",            "0001791786", "hedge", "ELLIOTT"),
    ("서드포인트 (댄 로브)",        "0001040273", "hedge", "THIRD POINT"),
    ("타이거 글로벌 (체이스 콜먼)", "0001167483", "hedge", "TIGER GLOBAL"),

    ("틸 매크로 (피터 틸)",         "0001562087", "paypal", "THIEL"),
    ("알티미터 (거스트너)",         "0001541617", "paypal", "ALTIMETER"),
    ("코투 매니지먼트",             "0001135730", "paypal", "COATUE"),

    ("국민연금공단",                "0001608046", "korea", "PENSION"),
]

CATEGORIES = {
    "value":  "가치·행동주의",
    "macro":  "매크로",
    "hedge":  "대형 헤지펀드",
    "multi":  "멀티전략·퀀트",     # 보유 종목 수천 개·회전율 높음 → 공통매매 집계 제외
    "paypal": "페이팔 마피아·테크",
    "policy": "정책·연준 출신",     # 13F 미제출 — 뉴스 전용
    "korea":  "국내 (국민연금)",
}

# 뉴스 전용 인물 — 13F 제출 의무가 없거나 제출을 중단한 인물
# (표시명, 카테고리, 검색어, 제목에 반드시 있어야 하는 단어)
NEWS_ONLY = [
    ("재닛 옐런", "policy", "Janet Yellen", "Yellen"),
    ("제롬 파월", "policy", "Jerome Powell", "Powell"),
    ("래리 서머스", "policy", "Larry Summers", "Summers"),
    ("케빈 워시", "policy", "Kevin Warsh", "Warsh"),
    # 버리는 2025-11 사이언 에셋 등록말소로 13F 제출 중단 → 발언만 추적
    ("마이클 버리", "macro", "Michael Burry", "Burry"),
]

# 13F 제출자 중 뉴스도 같이 볼 인물 (표시명: (검색어, 제목 필수 단어))
NEWS_FOR_MANAGERS = {
    "버크셔 해서웨이 (버핏)": ("Warren Buffett", "Buffett|Berkshire"),
    "아이칸 (칼 아이칸)": ("Carl Icahn", "Icahn"),
    "퍼싱스퀘어 (애크먼)": ("Bill Ackman", "Ackman"),
    "바우포스트 (클라만)": ("Seth Klarman", "Klarman|Baupost"),
    "그린라이트 (아인혼)": ("David Einhorn", "Einhorn|Greenlight"),
    "브리지워터 (달리오)": ("Ray Dalio", "Dalio|Bridgewater"),
    "듀케인 (드러켄밀러)": ("Stanley Druckenmiller", "Druckenmiller"),
    "소로스 펀드 매니지먼트": ("Soros Fund Management", "Soros"),
    "아팔루사 (테퍼)": ("David Tepper", "Tepper|Appaloosa"),
    "튜더 (폴 튜더 존스)": ("Paul Tudor Jones", "Tudor Jones"),
    "시타델 (켄 그리핀)": ("Ken Griffin", "Griffin|Citadel"),
    "밀레니엄 (잉글랜더)": ("Millennium Management", "Millennium|Englander"),
    "포인트72 (스티브 코헨)": ("Steve Cohen Point72", "Cohen|Point72"),
    "르네상스 테크놀로지": ("Renaissance Technologies", "Renaissance"),
    "엘리엇 (폴 싱어)": ("Elliott Management", "Elliott|Singer"),
    "서드포인트 (댄 로브)": ("Dan Loeb", "Loeb|Third Point"),
    "타이거 글로벌 (체이스 콜먼)": ("Tiger Global", "Tiger Global|Chase Coleman"),
    "틸 매크로 (피터 틸)": ("Peter Thiel", "Thiel"),
    "알티미터 (거스트너)": ("Brad Gerstner", "Gerstner|Altimeter"),
    "코투 매니지먼트": ("Coatue Philippe Laffont", "Coatue|Laffont"),
    "국민연금공단": ("국민연금 해외투자", "국민연금"),
}

# 인터뷰·발언 위주로 검색
NEWS_KEYWORDS = ("interview OR says OR said OR warns OR sees OR expects OR bets OR "
                 "CNBC OR Bloomberg OR podcast OR letter OR stake")
NEWS_PER_PERSON = 4

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})


# ---------------------------------------------------------------- SEC

def sec_get(url, as_json=False):
    time.sleep(SEC_SLEEP)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.json() if as_json else r.text


def pad(cik):
    return str(cik).strip().lstrip("0").zfill(10)


def submissions(cik):
    return sec_get(f"https://data.sec.gov/submissions/CIK{pad(cik)}.json", as_json=True)


def latest_13f_filings(cik, count=2):
    """가장 최근 13F-HR 두 건의 (보고기준일, accession) 을 반환."""
    data = submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    rows = zip(
        recent.get("form", []),
        recent.get("accessionNumber", []),
        recent.get("reportDate", []),
        recent.get("filingDate", []),
    )
    out = []
    seen = set()
    for form, acc, period, filed in rows:
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        if period in seen:          # 정정공시는 최신본만
            continue
        seen.add(period)
        out.append({"period": period, "accession": acc, "filed": filed})
        if len(out) >= count:
            break
    return data.get("name", "?"), out


def strip_ns(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def info_table_url(cik, accession):
    """공시 폴더에서 INFORMATION TABLE xml 경로를 찾는다."""
    acc = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
    idx = sec_get(f"{base}/index.json", as_json=True)
    cands = []
    for item in idx.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if not name.lower().endswith(".xml"):
            continue
        if "primary_doc" in name.lower():
            continue
        cands.append(name)
    if not cands:
        return None
    # 정보테이블이 보통 더 크다
    cands.sort(key=lambda n: -len(n))
    return f"{base}/{cands[0]}"


def parse_info_table(xml_text):
    """{cusip: {name, value, shares, putcall}} 로 집계."""
    root = ET.fromstring(xml_text.encode("utf-8"))
    holdings = {}
    for el in root.iter():
        if strip_ns(el.tag) != "infoTable":
            continue
        rec = {}
        for child in el.iter():
            t = strip_ns(child.tag)
            if child.text and child.text.strip():
                rec[t] = child.text.strip()
        cusip = rec.get("cusip")
        if not cusip:
            continue
        putcall = rec.get("putCall", "")
        key = f"{cusip}|{putcall}" if putcall else cusip
        try:
            value = float(rec.get("value", 0))
            shares = float(rec.get("sshPrnamt", 0))
        except ValueError:
            continue
        if key in holdings:
            holdings[key]["value"] += value
            holdings[key]["shares"] += shares
        else:
            holdings[key] = {
                "cusip": cusip,
                "name": rec.get("nameOfIssuer", "?"),
                "value": value,
                "shares": shares,
                "putcall": putcall or None,
            }
    return holdings


def normalize_values(holdings):
    """2022년 이전 공시는 value 단위가 천달러. 총액으로 단위를 추정 보정."""
    total = sum(h["value"] for h in holdings.values())
    if total and total < 1_000_000 and len(holdings) > 5:
        for h in holdings.values():
            h["value"] *= 1000
    return holdings


# ---------------------------------------------------------------- 비교

def diff_quarters(cur, prev):
    """신규/청산/증가/감소 산출."""
    cur_keys, prev_keys = set(cur), set(prev)
    total_cur = sum(h["value"] for h in cur.values()) or 1

    def row(h, prev_h=None):
        d = {
            "name": h["name"],
            "cusip": h["cusip"],
            "value": round(h["value"]),
            "shares": round(h["shares"]),
            "weight": round(h["value"] / total_cur * 100, 2),
            "putcall": h["putcall"],
        }
        if prev_h:
            ps = prev_h["shares"] or 1
            d["shares_prev"] = round(prev_h["shares"])
            d["shares_chg_pct"] = round((h["shares"] - prev_h["shares"]) / ps * 100, 1)
        return d

    new_buys, sold_out, added, trimmed = [], [], [], []
    for k in cur_keys - prev_keys:
        new_buys.append(row(cur[k]))
    for k in prev_keys - cur_keys:
        h = prev[k]
        sold_out.append({
            "name": h["name"], "cusip": h["cusip"],
            "value_prev": round(h["value"]), "shares_prev": round(h["shares"]),
            "putcall": h["putcall"],
        })
    for k in cur_keys & prev_keys:
        c, p = cur[k], prev[k]
        if p["shares"] <= 0:
            continue
        chg = (c["shares"] - p["shares"]) / p["shares"] * 100
        if chg >= 10:
            added.append(row(c, p))
        elif chg <= -10:
            trimmed.append(row(c, p))

    top = sorted((row(cur[k], prev.get(k)) for k in cur_keys),
                 key=lambda r: -r["value"])[:TOP_N]

    new_buys.sort(key=lambda r: -r["value"])
    sold_out.sort(key=lambda r: -r["value_prev"])
    added.sort(key=lambda r: -r["value"])
    trimmed.sort(key=lambda r: -r["value"])

    return {
        "total_value": round(total_cur),
        "position_count": len(cur_keys),
        "top": top,
        "new_buys": new_buys[:10],
        "sold_out": sold_out[:10],
        "added": added[:10],
        "trimmed": trimmed[:10],
    }


ETF_TRUST = re.compile(r"^(ISHARES|SPDR|SELECT SECTOR|STATE STR|VANGUARD|INVESCO|PROSHARES|"
                       r"DIREXION|SCHWAB STRATEGIC|WISDOMTREE|VANECK|GLOBAL X|J P MORGAN EXCHANGE)", re.I)


def norm_name(n):
    n = re.sub(r"\b(CL(ASS)? ?[A-C]|CAP STK CL [A-C]|COM|INC|CORP(ORATION)?|CO|LTD|PLC|N ?V|HLDGS?)\b\.?", "", n.upper())
    return re.sub(r"[^A-Z0-9]", "", n)


def build_consensus(managers):
    """여러 운용사가 같은 분기에 동시에 사고/판 종목."""
    bought, sold = defaultdict(list), defaultdict(list)
    for m in managers:
        if m.get("error") or m.get("stale") or m.get("category") in ("korea", "multi"):
            continue
        if (m.get("position_count") or 0) > CONSENSUS_MAX_POS:   # 지수형·퀀트 성격의 광범위한 장부
            continue
        # 같은 회사의 다른 주식 종류(예: 알파벳 A/C)는 이름으로 합친다.
        # ETF 신탁명(ISHARES TR 등)은 서로 다른 ETF를 구분하지 못하므로 제외
        for r in m["new_buys"] + m["added"]:
            if not ETF_TRUST.search(r["name"]):
                bought[norm_name(r["name"])].append((m["name"], r["cusip"], r["name"]))
        for r in m["sold_out"] + m["trimmed"]:
            if not ETF_TRUST.search(r["name"]):
                sold[norm_name(r["name"])].append((m["name"], r["cusip"], r["name"]))

    def pack(d):
        out = []
        for _, rows in d.items():
            who = sorted({w for w, _c, _n in rows})
            if len(who) >= CONSENSUS_MIN:
                out.append({"cusip": rows[0][1], "name": rows[0][2],
                            "count": len(who), "managers": who})
        return sorted(out, key=lambda r: -r["count"])[:15]

    return {"bought": pack(bought), "sold": pack(sold)}


# ---------------------------------------------------------------- 뉴스

NEWS_WINDOW_DAYS = 30


def _rss(q, lang):
    """구글 뉴스 → 실패·빈 결과면 Bing 뉴스. crypto.py 의 RSS 파서 재사용"""
    import crypto as C
    cut = __import__("datetime").timedelta(days=NEWS_WINDOW_DAYS)
    loc = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    try:
        r = session.get("https://news.google.com/rss/search?q=%s&%s" % (
            urllib.parse.quote(q + " when:%dd" % NEWS_WINDOW_DAYS), loc), timeout=20)
        r.raise_for_status()
        items = C.rss_items(r.text, lang, cut=cut)
        if items:
            return items
    except Exception as e:
        print(f"  ! 구글 뉴스 실패 → Bing: {e}")
    try:
        return C.bing(q, lang, cut)
    except Exception as e:
        print(f"  ! Bing 뉴스 실패: {e}")
        return []


def fetch_news(query, must, limit=NEWS_PER_PERSON):
    """인물 발언·인터뷰 기사. 제목에 must(정규식) 가 있는 기사만"""
    lang = "ko" if re.search(r"[가-힣]", query) else "en"
    q = query if lang == "ko" else f'"{query}" ({NEWS_KEYWORDS})'
    pat = re.compile(must, re.I)
    out, seen = [], set()
    for n in _rss(q, lang):
        if not pat.search(n["title"]):
            continue
        key = re.sub(r"\W+", "", n["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        pub = ""
        if n.get("ts"):
            pub = n["ts"].replace(" ", "T") + ":00+09:00"
        out.append({"title": n["title"], "url": n["url"], "source": n.get("src", ""),
                    "published": pub, "lang": lang})
        if len(out) >= limit:
            break
    return out


def summarize_views(news):
    """인물별 최근 헤드라인 → 발언·견해 요지 (한국어 1~2문장). 헤드라인에 있는 사실만"""
    import crypto as C
    import calendar_ctx
    by = defaultdict(list)
    for a in news:
        by[a["person"]].append("%s (%s)" % (a["title"], (a.get("published") or "")[:10]))
    if not by:
        return {}
    kst_today = datetime.now(timezone.utc).astimezone(
        __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))).date()
    prompt = (
        "아래는 유명 투자자·헤지펀드 매니저·정책 인사별 최근 30일 뉴스 헤드라인이다.\n"
        + calendar_ctx.macro_context(kst_today) + "\n"
        "인물마다 그 사람이 시장·경제·투자에 대해 한 발언이나 견해, 또는 최근 투자 행보의 요지를 "
        "한국어 1~2문장으로 정리하라. 인터뷰·발언이 헤드라인에 없으면 "
        "'직접 발언 보도 없음'으로 시작하고 관련 이슈만 한 줄로 적어라.\n"
        "규칙:\n- 헤드라인에 있는 내용만 쓸 것. 수치·종목·시점을 지어내지 말 것\n"
        "- 매수/매도 추천 금지\n" + calendar_ctx.RULE +
        "출력은 다른 말 없이 JSON 하나: {\"인물 표시명\": \"요지\", ...}\n\n"
        + json.dumps(by, ensure_ascii=False)[:40000])
    out = C.claude_json(prompt, 4000)
    return out if isinstance(out, dict) else {}


# ---------------------------------------------------------------- 가격·신호

FIGI_CACHE = "history/cusip_ticker.json"
YH_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SHOW_N = {"top": TOP_N, "new_buys": 8, "sold_out": 8, "added": 8, "trimmed": 8}
PRICE_MAX_AGE = 400       # 기준일이 이보다 오래된 공시(제출 중단)는 비교하지 않음


def _figi(jobs):
    """OpenFIGI 매핑 요청 1회 (최대 10건). 실패 시 None"""
    for _ in range(3):
        try:
            r = requests.post("https://api.openfigi.com/v3/mapping", json=jobs, timeout=30)
            if r.status_code == 429:
                time.sleep(30)
                continue
            r.raise_for_status()
            time.sleep(2.6)                    # 키 없이 분당 25회 제한
            out = []
            for res in r.json():
                data = res.get("data") or []
                eq = [x for x in data if x.get("marketSector") == "Equity"] or data
                out.append((eq[0].get("ticker") or "") if eq else "")
            return out
        except Exception as e:
            print(f"  ! OpenFIGI 실패: {e}")
            time.sleep(5)
    return None


def figi_tickers(cusips):
    """CUSIP -> 미국 티커 (OpenFIGI, 키 없이 분당 25회·요청당 10건). 결과는 캐시.
    1차: CUSIP + 미국 거래소. 실패분 2차: 해외 법인(첫 글자가 영문인 CINS)은 ID_CINS,
    나머지는 거래소 조건 없이. 2차도 실패하면 '-' 로 저장해 다시 묻지 않는다."""
    try:
        with open(FIGI_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    todo = sorted(c for c in cusips if cache.get(c, "") == "")
    print(f"[티커] 캐시 {len(cache)} · 조회 {len(todo)}")
    for i in range(0, len(todo), 10):
        part = todo[i:i + 10]
        res = _figi([{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in part])
        if res is None:
            continue
        miss = []
        for c, t in zip(part, res):
            if t:
                cache[c] = t
            else:
                miss.append(c)
        if miss:
            res2 = _figi([{"idType": "ID_CINS" if c[:1].isalpha() else "ID_CUSIP",
                           "idValue": c} for c in miss])
            for c, t in zip(miss, res2 or [""] * len(miss)):
                cache[c] = t or ("-" if res2 is not None else "")
    os.makedirs(os.path.dirname(FIGI_CACHE), exist_ok=True)
    with open(FIGI_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)
    return {c: t for c, t in cache.items() if t and t != "-"}


def yahoo_daily(ticker):
    """1년 일봉 -> (날짜, 종가, 고가, 저가, 거래량, 현재가)"""
    sym = ticker.replace("/", "-").replace(" ", "-")
    for host in ("query1", "query2"):
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/"
                             f"{urllib.parse.quote(sym)}?range=1y&interval=1d",
                             headers=YH_UA, timeout=20)
            if r.status_code == 429:
                time.sleep(3)
                continue
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [(datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), c, h, l, v)
                    for t, c, h, l, v in zip(res["timestamp"], q["close"], q["high"],
                                             q["low"], q["volume"]) if c is not None]
            if len(rows) < 5:
                return None
            d, c, h, l, v = (list(x) for x in zip(*rows))
            now_px = res.get("meta", {}).get("regularMarketPrice") or c[-1]
            return d, c, h, l, v, float(now_px)
        except Exception:
            continue
    return None


def enrich_prices(payload):
    """표시되는 보유 종목마다 티커·기준일 대비 현재 등락·기술적 신호를 붙인다"""
    import signals
    from concurrent.futures import ThreadPoolExecutor
    managers = payload.get("managers") or []
    cons = payload.get("consensus") or {}
    rows = []                                   # (row dict, 기준일)
    for m in managers:
        if m.get("error") or not m.get("period"):
            continue
        for k, n in SHOW_N.items():
            for r in (m.get(k) or [])[:n]:
                rows.append((r, m["period"]))
    latest = payload.get("latest_period")
    for k in ("bought", "sold"):
        for r in (cons.get(k) or [])[:8]:
            rows.append((r, latest))

    tick = figi_tickers({r["cusip"] for r, _ in rows if r.get("cusip")})
    uniq = sorted({tick.get(r["cusip"]) for r, _ in rows if tick.get(r.get("cusip"))})
    print(f"[가격] 티커 {len(uniq)}개 조회")
    with ThreadPoolExecutor(max_workers=4) as ex:
        series = dict(zip(uniq, ex.map(yahoo_daily, uniq)))
    ok = sum(1 for v in series.values() if v)
    print(f"  -> 가격 {ok}/{len(uniq)}")

    today = datetime.now(timezone.utc).date()
    tag_cache = {}
    for r, period in rows:
        t = tick.get(r.get("cusip") or "")
        for f in ("ticker", "chg_since", "px_now", "px_period", "tags"):
            r.pop(f, None)
        if not t:
            continue
        r["ticker"] = t
        s = series.get(t)
        if not s:
            continue
        d, c, h, l, v, now_px = s
        r["px_now"] = round(now_px, 4)
        try:
            pdate = datetime.strptime(period, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            pdate = None
        if pdate and (today - pdate).days <= PRICE_MAX_AGE:
            base = [x for x, dd in zip(c, d) if dd <= period]
            if base and d[0] <= period:
                r["px_period"] = round(base[-1], 4)
                r["chg_since"] = round((now_px / base[-1] - 1) * 100, 1)
        if t not in tag_cache:
            tag_cache[t] = signals.top(signals.price_signals(c, h, l, v), 3)
        r["tags"] = tag_cache[t]
    payload["prices_updated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


# ---------------------------------------------------------------- 메인

def verify_ciks():
    print("CIK 검증 — 등록명이 의도한 운용사와 맞는지 확인하세요.\n")
    for name, cik, _, kw in MANAGERS:
        try:
            registered, filings = latest_13f_filings(cik, 1)
            ok = "OK" if kw.upper() in registered.upper() else "!! 키워드 불일치"
            period = filings[0]["period"] if filings else "13F 없음"
            print(f"  {name:28s} {cik}  ->  {registered}  (최근 {period})  {ok}")
        except Exception as e:
            print(f"  {name:28s} {cik}  ->  조회 실패: {e}")


def load_existing():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def collect_13f():
    results, periods = [], []

    for name, cik, category, kw in MANAGERS:
        print(f"[13F] {name}")
        entry = {"name": name, "cik": cik,
                 "category": category, "category_label": CATEGORIES[category]}
        try:
            registered, filings = latest_13f_filings(cik, 2)
            entry["registered_name"] = registered
            print(f"  등록명: {registered}")
            if kw.upper() not in registered.upper():
                raise RuntimeError(f"CIK 등록명 불일치 ({registered})")
            if len(filings) < 2:
                raise RuntimeError("13F 공시가 2건 미만")

            cur_url = info_table_url(cik, filings[0]["accession"])
            prev_url = info_table_url(cik, filings[1]["accession"])
            if not cur_url or not prev_url:
                raise RuntimeError("정보테이블 XML 을 찾지 못함")

            cur = normalize_values(parse_info_table(sec_get(cur_url)))
            prev = normalize_values(parse_info_table(sec_get(prev_url)))

            entry.update(diff_quarters(cur, prev))
            entry["period"] = filings[0]["period"]
            entry["period_prev"] = filings[1]["period"]
            entry["filed"] = filings[0]["filed"]

            # 등록말소·제출중단 감지: 최신 공시가 200일 넘게 묵었으면 표시
            try:
                age = (datetime.now(timezone.utc).date()
                       - datetime.strptime(filings[0]["period"], "%Y-%m-%d").date()).days
                entry["period_age_days"] = age
                entry["stale"] = age > STALE_DAYS
            except ValueError:
                entry["stale"] = False

            periods.append(filings[0]["period"])
        except Exception as e:
            print(f"  ! 실패: {e}")
            entry["error"] = str(e)
            entry.update({"top": [], "new_buys": [], "sold_out": [],
                          "added": [], "trimmed": []})
        results.append(entry)

    ok = sum(1 for r in results if not r.get("error"))
    print(f"  -> 운용사 {ok}/{len(results)}")
    return {
        "latest_period": max(periods) if periods else None,
        "managers": results,
        "consensus": build_consensus(results),
        "holdings_updated_at": datetime.now(timezone.utc).isoformat(),
    }


def collect_news():
    import crypto as C
    print("[뉴스]")
    news = []
    people = [(disp, next((c for n, _, c, _k in MANAGERS if n == disp), "value"), q, must)
              for disp, (q, must) in NEWS_FOR_MANAGERS.items()]
    people += [(disp, cat, q, must) for disp, cat, q, must in NEWS_ONLY]
    for disp, cat, q, must in people:
        got = fetch_news(q, must)
        print(f"  {disp}: {len(got)}건")
        for a in got:
            a.update({"person": disp, "category": cat,
                      "category_label": CATEGORIES[cat]})
            news.append(a)
    C.translate_titles(news)          # 영문 제목 → 한국어 (원문은 orig)
    import articles                   # 영문 기사 본문 → 한국어 번역 요약
    try:
        articles.enrich(news, "history/article_ko_13f.json")
    except Exception as e:
        print("  ! 기사 번역 실패:", e)
    views = summarize_views(news)
    print(f"  -> 뉴스 {len(news)}건, 발언 요지 {len(views)}명")
    return {"news": news, "views": views,
            "news_updated_at": datetime.now(timezone.utc).isoformat()}


def main(mode):
    payload = load_existing()
    payload.setdefault("managers", [])
    payload.setdefault("news", [])

    if mode in ("all", "13f"):
        payload.update(collect_13f())
    if mode in ("all", "news"):
        payload.update(collect_news())
    if mode in ("all", "13f", "prices"):
        enrich_prices(payload)

    payload["categories"] = CATEGORIES
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["note"] = ("13F 는 분기말 후 45일 이내 공시되므로 최대 45일 시차가 있습니다. "
                       "파생·공매도·해외주식은 13F 에 포함되지 않습니다.")

    d = os.path.dirname(OUT_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n완료({mode}): {OUT_PATH}  "
          f"(운용사 {len(payload['managers'])}, 뉴스 {len(payload['news'])}건)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-cik", action="store_true")
    ap.add_argument("--mode", choices=["all", "13f", "news", "prices"], default="all",
                    help="13f=보유내역(+가격), news=뉴스만, prices=가격·신호만, all=전부 (기본)")
    args = ap.parse_args()
    verify_ciks() if args.verify_cik else main(args.mode)
