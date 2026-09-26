"""보유 가상자산 종합 대시보드 데이터 수집 -> crypto.json, history/crypto.json

소스 (모두 키 없이 사용 가능, GitHub Actions(미국 IP)에서 접근 가능한 곳 위주)
- CoinGecko   : 가격, 시총, 24h/7d/30d 변화, 7일 스파크라인, 원화 가격
- Hyperliquid : 무기한 선물 펀딩비(시간당), 미결제약정, 마크/오라클 가격
- OKX         : USDT 무기한 펀딩비(8시간), 미결제약정, 롱/숏 계정 비율
- Deribit     : 옵션 미결제약정 -> 맥스페인, 풋/콜 비율 (BTC, ETH, SOL 등 상장 코인만)
- Google News : 코인별 최신 뉴스 (한국어 + 영어 RSS)
- alternative.me : 공포·탐욕 지수
- Anthropic   : (ANTHROPIC_API_KEY가 있으면) 코인별 한 줄 브리핑
"""
import json, os, re, datetime, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "*/*"}

# (심볼, 한글명, CoinGecko id, 하이퍼리퀴드 이름, OKX 기초자산, 뉴스 검색어(한), 뉴스 검색어(영))
COINS = [
    ("BTC", "비트코인", "bitcoin", "BTC", "BTC", "비트코인", "Bitcoin"),
    ("ETH", "이더리움", "ethereum", "ETH", "ETH", "이더리움", "Ethereum"),
    ("SOL", "솔라나", "solana", "SOL", "SOL", "솔라나", "Solana crypto"),
    ("HYPE", "하이퍼리퀴드", "hyperliquid", "HYPE", "HYPE", "하이퍼리퀴드", "Hyperliquid HYPE"),
    ("LINK", "체인링크", "chainlink", "LINK", "LINK", "체인링크", "Chainlink LINK"),
    ("ONDO", "온도파이낸스", "ondo-finance", "ONDO", "ONDO", "온도파이낸스", "Ondo Finance"),
    ("SUI", "수이", "sui", "SUI", "SUI", "수이 코인", "Sui blockchain SUI"),
    ("VIRTUAL", "버추얼프로토콜", "virtual-protocol", "VIRTUAL", "VIRTUAL",
     "버추얼 프로토콜", "Virtuals Protocol"),
]


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def post(url, data, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "market-board"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


ERRORS = []


def safe(label, fn, default):
    try:
        return fn()
    except Exception as e:
        ERRORS.append("%s: %s" % (label, str(e)[:120]))
        print("[실패]", label, e)
        return default


# ---------- CoinGecko ----------
def coingecko():
    ids = ",".join(c[2] for c in COINS)
    rows = json.loads(get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                          "&ids=%s&sparkline=true&price_change_percentage=24h,7d,30d" % ids))
    out = {}
    for r in rows:
        spark = (r.get("sparkline_in_7d") or {}).get("price") or []
        step = max(1, len(spark) // 56)  # 168개(1시간봉) -> 약 56개로 축소
        out[r["id"]] = {
            "price": num(r.get("current_price")),
            "mcap": num(r.get("market_cap")),
            "rank": r.get("market_cap_rank"),
            "vol": num(r.get("total_volume")),
            "high24": num(r.get("high_24h")),
            "low24": num(r.get("low_24h")),
            "ch24": num(r.get("price_change_percentage_24h_in_currency")),
            "ch7": num(r.get("price_change_percentage_7d_in_currency")),
            "ch30": num(r.get("price_change_percentage_30d_in_currency")),
            "ath": num(r.get("ath")),
            "athPct": num(r.get("ath_change_percentage")),
            "spark": [round(p, 6) for p in spark[::step] if p is not None],
        }
    return out


def coingecko_krw():
    ids = ",".join(c[2] for c in COINS)
    j = json.loads(get("https://api.coingecko.com/api/v3/simple/price?ids=%s"
                       "&vs_currencies=krw" % ids))
    return {k: num(v.get("krw")) for k, v in j.items()}


# ---------- Hyperliquid ----------
def hyperliquid():
    raw = json.loads(post("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"}))
    meta, ctxs = raw[0]["universe"], raw[1]
    out = {}
    for m, c in zip(meta, ctxs):
        px = num(c.get("markPx")) or 0
        fr = num(c.get("funding"))
        oi = num(c.get("openInterest"))
        orc = num(c.get("oraclePx"))
        out[m["name"]] = {
            "funding": fr,                                  # 시간당(소수)
            "fundingApr": fr * 24 * 365 * 100 if fr is not None else None,
            "oiUsd": oi * px if oi is not None else None,
            "mark": px,
            "basis": (px / orc - 1) * 100 if orc else None,  # 마크-오라클 괴리 %
            "vol24": num(c.get("dayNtlVlm")),
        }
    return out


# ---------- OKX ----------
OKX = "https://www.okx.com/api/v5"


def okx_coin(ccy):
    inst = "%s-USDT-SWAP" % ccy
    out = {}
    fr = json.loads(get("%s/public/funding-rate?instId=%s" % (OKX, inst)))
    if fr.get("data"):
        d = fr["data"][0]
        out["funding"] = num(d.get("fundingRate"))       # 8시간(소수)
        out["nextFunding"] = num(d.get("nextFundingRate"))
    oi = json.loads(get("%s/public/open-interest?instType=SWAP&instId=%s" % (OKX, inst)))
    if oi.get("data"):
        d = oi["data"][0]
        out["oiUsd"] = num(d.get("oiUsd"))
        out["oiCcy"] = num(d.get("oiCcy"))
    try:
        ls = json.loads(get("%s/rubik/stat/contracts/long-short-account-ratio"
                            "?ccy=%s&period=1H" % (OKX, ccy)))
        if ls.get("data"):
            out["lsRatio"] = num(ls["data"][0][1])
    except Exception:
        pass
    if not out:
        raise ValueError("OKX 응답 없음")
    return out


# ---------- Deribit 옵션 -> 맥스페인 ----------
def parse_opt(name):
    # BTC-27SEP26-60000-C  /  SOL_USDC-27SEP26-150-C  /  BTC-27SEP26-62d5-C (소수 행사가)
    p = name.split("-")
    if len(p) != 4 or p[3] not in ("C", "P"):
        return None
    base = p[0].split("_")[0]
    try:
        exp = datetime.datetime.strptime(p[1], "%d%b%y").replace(
            hour=8, tzinfo=datetime.timezone.utc)
        strike = float(p[2].replace("d", "."))
    except ValueError:
        return None
    return base, exp, strike, p[3]


def max_pain(chain):
    """chain: {strike: [call_oi, put_oi]} -> (맥스페인 행사가, 콜 OI, 풋 OI)"""
    strikes = sorted(chain)
    best, best_pay = None, None
    for s in strikes:
        pay = 0.0
        for k in strikes:
            c, p = chain[k]
            if s > k:
                pay += c * (s - k)
            elif s < k:
                pay += p * (k - s)
        if best_pay is None or pay < best_pay:
            best, best_pay = s, pay
    calls = sum(v[0] for v in chain.values())
    puts = sum(v[1] for v in chain.values())
    return best, calls, puts


def deribit_rows(currency):
    j = json.loads(get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
                       "?currency=%s&kind=option" % currency))
    return j.get("result") or []


def deribit():
    want = {c[0] for c in COINS}
    rows = safe("Deribit BTC", lambda: deribit_rows("BTC"), []) + \
        safe("Deribit ETH", lambda: deribit_rows("ETH"), []) + \
        safe("Deribit USDC", lambda: deribit_rows("USDC"), [])
    # base -> expiry -> strike -> [call, put]
    book, under = {}, {}
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    for r in rows:
        name = r.get("instrument_name") or ""
        pr = parse_opt(name)
        if not pr:
            continue
        base, exp, strike, cp = pr
        # 인버스(BTC-...)와 USDC 선형(BTC_USDC-...)이 겹치면 인버스만 사용
        if base in ("BTC", "ETH") and "_USDC" in name.split("-")[0]:
            continue
        if base not in want or exp <= utc_now:
            continue
        oi = num(r.get("open_interest")) or 0
        if oi <= 0:
            continue
        slot = book.setdefault(base, {}).setdefault(exp, {}).setdefault(strike, [0.0, 0.0])
        slot[0 if cp == "C" else 1] += oi
        u = num(r.get("underlying_price"))
        if u:
            under[base] = u
    out = {}
    for base, exps in book.items():
        items = []
        tot_c = tot_p = 0.0
        for exp, chain in sorted(exps.items()):
            mp, c, p = max_pain(chain)
            tot_c += c
            tot_p += p
            items.append({"exp": exp.strftime("%Y-%m-%d"),
                          "days": round((exp - utc_now).total_seconds() / 86400, 1),
                          "maxPain": mp, "callOi": round(c, 2), "putOi": round(p, 2),
                          "pcr": round(p / c, 2) if c else None})
        if not items:
            continue
        nearest = items[0]
        # 30일 이내 만기 중 OI 최대 = 시장이 가장 주목하는 만기(보통 월물)
        near_month = [i for i in items if i["days"] <= 35] or items
        major = max(near_month, key=lambda i: i["callOi"] + i["putOi"])
        out[base] = {"nearest": nearest, "major": major,
                     "pcr": round(tot_p / tot_c, 2) if tot_c else None,
                     "underlying": under.get(base),
                     "expiries": items[:6]}
    return out


# ---------- 뉴스 ----------
# Google News는 GitHub Actions IP를 자주 막으므로(503) Bing 뉴스 RSS, 코인 매체 RSS 순으로 보완
NEWS_CUT = datetime.timedelta(days=3)

# 매체 RSS 제목 매칭용: (대소문자 무시 이름, 대소문자 구분 티커)
KW = {
    "BTC": (["bitcoin", "비트코인"], ["BTC"]),
    "ETH": (["ethereum", "ether", "이더리움"], ["ETH"]),
    "SOL": (["solana", "솔라나"], ["SOL"]),
    "HYPE": (["hyperliquid", "하이퍼리퀴드"], ["HYPE"]),
    "LINK": (["chainlink", "체인링크"], ["LINK"]),
    "ONDO": (["ondo finance", "온도파이낸스", "온도 파이낸스"], ["ONDO", "Ondo"]),
    "SUI": (["sui network", "sui blockchain", "sui price", "수이"], ["SUI", "Sui"]),
    "VIRTUAL": (["virtuals", "virtual protocol", "버추얼"], ["VIRTUAL"]),
}
FEEDS = [
    ("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk", "en"),
    ("https://cointelegraph.com/rss", "Cointelegraph", "en"),
    ("https://decrypt.co/feed", "Decrypt", "en"),
    ("https://www.theblock.co/rss.xml", "The Block", "en"),
    ("https://www.blockmedia.co.kr/feed", "블록미디어", "ko"),
    ("https://www.tokenpost.kr/rss", "토큰포스트", "ko"),
]


def rss_items(xml, lang, default_src=""):
    root = ET.fromstring(xml)
    out = []
    for it in root.iter("item"):
        title = re.sub(r"\s+", " ", it.findtext("title") or "").strip()
        src = ""
        for ch in it:  # <source>, <News:Source> 등
            if ch.tag.split("}")[-1].lower() == "source" and (ch.text or "").strip():
                src = ch.text.strip()
        src = src or default_src
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3].strip()
        link = (it.findtext("link") or "").strip()
        if "bing.com/news/apiclick" in link:  # Bing 리다이렉트 -> 원문 주소
            real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url")
            if real:
                link = real[0]
        if not title or not link.startswith("http"):
            continue
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone(KST)
        except Exception:
            dt = None
        if dt and now - dt > NEWS_CUT:
            continue
        out.append({"title": title, "src": src, "url": link,
                    "ts": dt.strftime("%Y-%m-%d %H:%M") if dt else "", "lang": lang})
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out


def gnews(q, lang):
    loc = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    return rss_items(get("https://news.google.com/rss/search?q=%s&%s" % (
        urllib.parse.quote(q + " when:3d"), loc), 20), lang)


def bing(q, lang):
    mkt = "ko-KR" if lang == "ko" else "en-US"
    return rss_items(get("https://www.bing.com/news/search?q=%s&format=rss&mkt=%s" % (
        urllib.parse.quote(q), mkt), 20), lang)


_FEED_CACHE = None


def feed_pool():
    global _FEED_CACHE
    if _FEED_CACHE is None:
        _FEED_CACHE = []
        for url, name, lang in FEEDS:
            try:
                _FEED_CACHE += rss_items(get(url, 20), lang, name)
            except Exception as e:
                print("[피드 실패]", name, e)
    return _FEED_CACHE


def coin_pats(sym):
    names, tickers = KW.get(sym, ([], []))
    pats = []
    for n in names:
        if re.search(r"[가-힣]", n):  # 한글: 앞뒤가 다른 한글 단어에 붙어 있으면 제외(조사는 허용)
            pats.append(re.compile(r"(?<![가-힣])%s(?![가-힣]|$)|(?<![가-힣])%s(?=[은는이가을를의와과도로에]|$)"
                                   % (re.escape(n), re.escape(n))))
        else:
            pats.append(re.compile(r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(n), re.I))
    pats += [re.compile(r"(?<![A-Za-z$])\$?%s(?![A-Za-z])" % re.escape(t)) for t in tickers]
    return pats


JUNK = re.compile(r"^\s*convert\s+[\d.,]+\s|\bto\s+[A-Z]{3}\s*$|price (?:today|chart|index)|환율 계산", re.I)


def relevant(sym, n):
    if JUNK.search(n["title"]):  # 환전 계산기·시세 페이지 등 기사가 아닌 결과
        return False
    return any(p.search(n["title"]) for p in coin_pats(sym))


def feed_match(sym):
    return [n for n in feed_pool() if relevant(sym, n)]


NEWS_FAIL = {}


def fetch_lang(sym, q, lang):
    for label, fn in (("Google", gnews), ("Bing", bing)):
        try:
            items = [n for n in fn(q, lang) if relevant(sym, n)]
            if items:
                return items[:4]
        except Exception as e:
            NEWS_FAIL[label] = str(e)[:60]
    return []


def news(sym, ko_q, en_q):
    items = fetch_lang(sym, ko_q, "ko") + fetch_lang(sym, en_q, "en")
    if len(items) < 6:
        items += feed_match(sym)
    seen, out = set(), []
    for n in items:
        key = re.sub(r"\W+", "", n["title"].lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out[:8]


# ---------- 공포·탐욕 ----------
def fear_greed():
    j = json.loads(get("https://api.alternative.me/fng/?limit=8"))
    d = j["data"]
    return {"value": int(d[0]["value"]), "label": d[0]["value_classification"],
            "week": int(d[-1]["value"]) if len(d) > 7 else None}


# ---------- AI 브리핑 ----------
def ai_brief(coins):
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    slim = []
    for c in coins:
        slim.append({k: c.get(k) for k in ("sym", "name", "market", "hl", "okx", "options")} |
                    {"news": [n["title"] for n in c.get("news", [])][:6]})
    for s in slim:
        if s.get("market"):
            s["market"] = {k: v for k, v in s["market"].items() if k != "spark"}
        if s.get("options"):
            s["options"] = {k: v for k, v in s["options"].items() if k != "expiries"}
    prompt = (
        "너는 가상자산 데이터 정리 담당이다. 아래 JSON은 보유 코인별로 방금 수집한 "
        "가격·선물(펀딩비, 미결제약정, 롱숏비율)·옵션(맥스페인, 풋콜비율)·뉴스 제목이다.\n"
        "코인마다 한국어 2문장으로 요약하라: 1문장은 뉴스의 핵심 이슈, "
        "1문장은 선물·옵션 포지셔닝이 말하는 것(과열/중립/위축, 맥스페인과 현재가 거리).\n"
        "그리고 전체 포트폴리오 관점 요약 2~3문장을 overall로 작성하라.\n"
        "규칙: 매수/매도 추천 금지, 관찰된 사실과 함의만. 데이터가 없으면 없다고만. "
        "hl.funding은 시간당, okx.funding은 8시간 기준 소수값이다.\n"
        "출력은 다른 말 없이 JSON 한 개만: "
        "{\"overall\": \"...\", \"coins\": {\"BTC\": \"...\", ...}}\n\n"
        + json.dumps(slim, ensure_ascii=False)[:50000])
    for model in ("claude-sonnet-5", "claude-haiku-4-5-20251001"):
        body = json.dumps({"model": model, "max_tokens": 4000,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                     headers={"content-type": "application/json",
                                              "x-api-key": key,
                                              "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                res = json.loads(r.read().decode())
            txt = "".join(b.get("text", "") for b in res.get("content", [])
                          if isinstance(b, dict))
            m = re.search(r"\{[\s\S]*\}", txt)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            ERRORS.append("AI(%s): %s" % (model, str(e)[:120]))
    return None


# ---------- 조립 ----------
def build():
    cg = safe("CoinGecko", coingecko, {})
    krw = safe("CoinGecko KRW", coingecko_krw, {})
    hl = safe("Hyperliquid", hyperliquid, {})
    opts = deribit()
    coins = []
    for sym, ko, cg_id, hl_name, okx_ccy, ko_q, en_q in COINS:
        m = cg.get(cg_id)
        if m is not None:
            m["krw"] = krw.get(cg_id)
        coins.append({
            "sym": sym, "name": ko, "cg": cg_id,
            "market": m,
            "hl": hl.get(hl_name),
            "okx": safe("OKX " + okx_ccy, lambda c=okx_ccy: okx_coin(c), None),
            "options": opts.get(sym),
            "news": news(sym, ko_q, en_q),
        })
    if not any(c["news"] for c in coins) and NEWS_FAIL:
        ERRORS.append("뉴스 수집 실패: " + " / ".join("%s %s" % kv for kv in NEWS_FAIL.items()))
    brief = safe("AI 브리핑", lambda: ai_brief(coins), None) or {}
    for c in coins:
        c["brief"] = (brief.get("coins") or {}).get(c["sym"], "")
    return {"updated": now.strftime("%Y-%m-%d %H:%M KST"),
            "fng": safe("공포탐욕", fear_greed, None),
            "overall": brief.get("overall", ""),
            "coins": coins,
            "errors": ERRORS}


def save_history(payload):
    path = "history/crypto.json"
    try:
        with open(path, encoding="utf-8") as f:
            hist = json.load(f)
    except Exception:
        hist = []
    day = now.strftime("%Y-%m-%d")
    snap = {"date": day}
    for c in payload["coins"]:
        s = {}
        if c["market"] and c["market"].get("price") is not None:
            s["px"] = c["market"]["price"]
        if c["hl"] and c["hl"].get("funding") is not None:
            s["hlF"] = round(c["hl"]["funding"] * 100, 5)
        if c["hl"] and c["hl"].get("oiUsd") is not None:
            s["hlOi"] = round(c["hl"]["oiUsd"] / 1e6, 2)
        if c["okx"] and c["okx"].get("funding") is not None:
            s["okF"] = round(c["okx"]["funding"] * 100, 5)
        if c["options"]:
            s["mp"] = c["options"]["major"]["maxPain"]
        if s:
            snap[c["sym"]] = s
    hist = [h for h in hist if h.get("date") != day] + [snap]
    hist = hist[-180:]
    os.makedirs("history", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)


if __name__ == "__main__":
    payload = build()
    with open("crypto.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    save_history(payload)
    print("crypto done · 오류 %d건" % len(ERRORS))
