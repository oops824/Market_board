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
def cg_get(path):
    """무료 API 분당 호출 제한 대응: 호출 간격 + 429면 한 번 쉬고 재시도"""
    import time
    for i in range(2):
        time.sleep(2)
        try:
            return json.loads(get("https://api.coingecko.com/api/v3/" + path))
        except urllib.error.HTTPError as e:
            if e.code != 429 or i:
                raise
            time.sleep(40)


def coingecko():
    ids = ",".join(c[2] for c in COINS)
    rows = cg_get("coins/markets?vs_currency=usd"
                  "&ids=%s&sparkline=true&price_change_percentage=24h,7d,30d" % ids)
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
    j = cg_get("simple/price?ids=%s&vs_currencies=krw" % ids)
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


def rss_items(xml, lang, default_src="", cut=NEWS_CUT):
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
        if dt and now - dt > cut:
            continue
        out.append({"title": title, "src": src, "url": link,
                    "ts": dt.strftime("%Y-%m-%d %H:%M") if dt else "", "lang": lang})
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out


def gnews(q, lang):
    loc = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    return rss_items(get("https://news.google.com/rss/search?q=%s&%s" % (
        urllib.parse.quote(q + " when:3d"), loc), 20), lang)


def bing(q, lang, cut=NEWS_CUT):
    mkt = "ko-KR" if lang == "ko" else "en-US"
    return rss_items(get("https://www.bing.com/news/search?q=%s&format=rss&mkt=%s" % (
        urllib.parse.quote(q), mkt), 20), lang, cut=cut)


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
        "그리고 8개 코인 전체를 아우르는 요약 2~3문장을 overall로 작성하라.\n"
        "규칙: 매수/매도 추천 금지, 관찰된 사실과 함의만. 데이터가 없으면 없다고만. "
        "hl.funding은 시간당, okx.funding은 8시간 기준 소수값이다.\n"
        "출력은 다른 말 없이 JSON 한 개만: "
        "{\"overall\": \"...\", \"coins\": {\"BTC\": \"...\", ...}}\n\n"
        + json.dumps(slim, ensure_ascii=False)[:50000])
    return claude_json(prompt, 4000)


def claude_json(prompt, max_tokens, models=("claude-sonnet-5", "claude-haiku-4-5-20251001")):
    """프롬프트를 보내고 응답 속 JSON(객체/배열) 하나를 파싱해 반환. 키가 없으면 None"""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    for model in models:
        body = json.dumps({"model": model, "max_tokens": max_tokens,
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
            m = re.search(r"[\[{][\s\S]*[\]}]", txt)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            ERRORS.append("AI(%s): %s" % (model, str(e)[:120]))
    return None


# ---------- 영어 뉴스 제목 한글 번역 ----------
def translate_titles(items):
    """lang == 'en' 인 뉴스의 title을 한국어로 바꾸고 원문은 orig에 보관"""
    en = [n for n in items if n.get("lang") == "en" and not n.get("orig")]
    uniq = list(dict.fromkeys(n["title"] for n in en))
    if not uniq:
        return
    prompt = (
        "다음 가상자산 뉴스 제목들을 자연스러운 한국어 기사 제목으로 번역하라. "
        "코인 이름은 한국에서 통용되는 한글 표기(예: 비트코인, 이더리움, 솔라나, 체인링크, "
        "하이퍼리퀴드, 온도파이낸스, 수이, 버추얼프로토콜)를 쓰고, 티커·기관명·숫자는 유지하라.\n"
        "입력과 같은 순서·같은 개수의 JSON 문자열 배열 하나만 출력하라.\n\n"
        + json.dumps(uniq, ensure_ascii=False))
    out = claude_json(prompt, 6000, models=("claude-haiku-4-5-20251001", "claude-sonnet-5"))
    if not isinstance(out, list) or len(out) != len(uniq):
        if os.environ.get("ANTHROPIC_API_KEY"):
            ERRORS.append("뉴스 번역 실패 (영문 그대로 표시)")
        return
    ko = {e: str(k).strip() for e, k in zip(uniq, out) if str(k).strip()}
    for n in en:
        if n["title"] in ko:
            n["orig"], n["title"] = n["title"], ko[n["title"]]


# ---------- 오늘의 주목 코인 (하루 1개) ----------
PICK_PATH = "history/picks.json"
# 기관·월가 관여를 보여주는 표현 (헤드라인 매칭용)
INST = re.compile(
    r"\bETFs?\b|ETP|BlackRock|Fidelity|Grayscale|Franklin Templeton|VanEck|Bitwise|21Shares|"
    r"Invesco|WisdomTree|Canary|CoinShares|ARK Invest|Nasdaq|NYSE|\bCME\b|JPMorgan|J\.P\. Morgan|"
    r"Goldman|Morgan Stanley|Citi(group)?\b|BNY|State Street|Apollo|KKR|Hamilton Lane|"
    r"Securitize|Deutsche Bank|Standard Chartered|Visa|Mastercard|Stripe|PayPal|"
    r"institution(al|s)?|Wall Street|asset manager|S-1|19b-4|SEC (approv|fil)|"
    r"treasury (company|firm|strategy)|a16z|Andreessen|Paradigm|Pantera|Polychain|"
    r"블랙록|피델리티|그레이스케일|반에크|기관|월가|현물 ETF|자산운용|나스닥|골드만|JP모건",
    re.I)
EXCL_CATS = ("stablecoins", "wrapped-tokens", "liquid-staking-tokens", "bridged-tokens",
             "tokenized-gold", "exchange-based-tokens")
EXCL_NAME = re.compile(r"\busd|wrapped|staked|bridged|restak|\bgold\b|tokenized", re.I)


def load_picks():
    try:
        with open(PICK_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def pick_candidates(skip_ids):
    rows = cg_get("coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1"
                  "&price_change_percentage=7d,30d")
    excl = set()
    for cat in EXCL_CATS:
        excl |= {r["id"] for r in safe("CG 카테고리 " + cat, lambda c=cat: cg_get(
            "coins/markets?vs_currency=usd&category=%s&per_page=250" % c), [])}
    trend = {c["item"]["id"] for c in (safe("CG 트렌딩", lambda: cg_get("search/trending"),
                                            {}) or {}).get("coins", [])}
    out = []
    for r in rows:
        rank, mcap, vol = r.get("market_cap_rank"), num(r.get("market_cap")), num(r.get("total_volume"))
        if not rank or rank <= 10 or not mcap or r["id"] in excl or r["id"] in skip_ids:
            continue
        if EXCL_NAME.search(r.get("name", "")) or EXCL_NAME.search(r.get("symbol", "")):
            continue
        ch7 = num(r.get("price_change_percentage_7d_in_currency")) or 0
        ch30 = num(r.get("price_change_percentage_30d_in_currency")) or 0
        turn = min((vol or 0) / mcap, 1.0)
        score = max(-1, min(ch30, 150)) / 50 + max(-1, min(ch7, 60)) / 20 + turn * 3 + \
            (2 if r["id"] in trend else 0)
        out.append({"id": r["id"], "sym": r["symbol"].upper(), "name": r["name"], "rank": rank,
                    "price": num(r.get("current_price")), "mcap": mcap, "vol": vol,
                    "ch7": ch7, "ch30": ch30, "trending": r["id"] in trend,
                    "score": round(score, 3)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:12]


def inst_evidence(c):
    q = '"%s" (ETF OR BlackRock OR Grayscale OR Fidelity OR institutional OR "Wall Street")' % c["name"]
    items = safe("근거뉴스 " + c["sym"], lambda: bing(q, "en", datetime.timedelta(days=30)), [])
    items += safe("근거뉴스(ko) " + c["sym"],
                  lambda: bing("%s 기관 ETF" % c["name"], "ko", datetime.timedelta(days=30)), [])
    name_pat = re.compile(r"(?<![A-Za-z])(%s|%s)(?![A-Za-z])" % (
        re.escape(c["name"]), re.escape(c["sym"])), re.I if len(c["sym"]) > 3 else 0)
    name_ci = re.compile(r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(c["name"]), re.I)
    seen, ev = set(), []
    for n in items:
        t = n["title"]
        if not (name_ci.search(t) or name_pat.search(t)) or not INST.search(t) or JUNK.search(t):
            continue
        k = re.sub(r"\W+", "", t.lower())[:40]
        if k not in seen:
            seen.add(k)
            ev.append(n)
    return ev[:6]


def daily_pick(held_ids):
    picks = load_picks()
    today = now.strftime("%Y-%m-%d")
    if picks and picks[-1].get("date") == today:
        return picks  # 오늘은 이미 소개함
    cutoff = (now - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    recent = {p["id"] for p in picks if p.get("date", "") >= cutoff}
    cands = pick_candidates(set(held_ids) | recent)
    for c in cands:
        c["evidence"] = inst_evidence(c)
    strong = [c for c in cands if len(c["evidence"]) >= 2] or \
        [c for c in cands if c["evidence"]]
    if not strong:
        ERRORS.append("오늘의 코인: 기관 관심 근거가 확인된 후보 없음 (다음 실행에서 재시도)")
        return picks
    strong = strong[:5]
    for c in strong:
        d = safe("CG 상세 " + c["id"], lambda i=c["id"]: cg_get(
            "coins/%s?localization=false&tickers=false&market_data=false"
            "&community_data=false&developer_data=false" % i), {}) or {}
        c["desc"] = re.sub(r"<[^>]+>", "", (d.get("description") or {}).get("en") or "")[:700]
        c["cats"] = [x for x in (d.get("categories") or []) if x][:5]
    slim = [{k: c.get(k) for k in ("id", "sym", "name", "rank", "mcap", "ch7", "ch30",
                                    "trending", "desc", "cats")} |
            {"evidence": ["[%d] %s (%s, %s)" % (i, n["title"], n["src"], n["ts"][:10])
                          for i, n in enumerate(c["evidence"])]} for c in strong]
    prompt = (
        "너는 가상자산 리서치 담당이다. 아래 후보는 시총 상위 250위 안에서 최근 모멘텀이 강하고, "
        "최근 30일 뉴스 헤드라인에서 월가·기관(ETF, 자산운용사, 은행, 거래소, 벤처캐피털 등)의 "
        "관여가 확인된 코인들이다.\n"
        "이 중 '기관의 관심·투자가 가장 구체적이고 확실하게 드러난' 코인 하나를 골라 한국어로 소개하라. "
        "단순 가격 상승이나 막연한 기대보다 ETF 신청/승인, 기관 상품 출시, 기관 투자·파트너십처럼 "
        "헤드라인으로 확인되는 사실을 우선하라.\n"
        "규칙: evidence 헤드라인과 desc에 있는 사실만 쓸 것. 없는 기관명·금액을 만들지 말 것. "
        "매수/매도 추천 금지.\n"
        "출력은 다른 말 없이 JSON 하나만: {\"id\": \"후보 id\", "
        "\"headline\": \"한 줄 소개(25자 내외)\", "
        "\"intro\": \"무슨 프로젝트이고 왜 지금 떠오르는지 3문장\", "
        "\"institutions\": \"기관·월가 관심의 구체적 근거 2~3문장\", "
        "\"risks\": \"유의할 점 1~2문장\", \"evidence\": [근거로 쓴 헤드라인 번호]}\n\n"
        + json.dumps(slim, ensure_ascii=False))
    ai = claude_json(prompt, 3000) or {}
    chosen = next((c for c in strong if c["id"] == ai.get("id")), None)
    if chosen is None:  # AI 없음/실패 -> 근거 수, 점수 순
        chosen = max(strong, key=lambda c: (len(c["evidence"]), c["score"]))
        ai = {}
    idx = [i for i in ai.get("evidence", []) if isinstance(i, int) and 0 <= i < len(chosen["evidence"])]
    ev = [chosen["evidence"][i] for i in idx] or chosen["evidence"]
    picks.append({"date": today, "id": chosen["id"], "sym": chosen["sym"], "name": chosen["name"],
                  "rank": chosen["rank"], "price": chosen["price"], "mcap": chosen["mcap"],
                  "ch7": chosen["ch7"], "ch30": chosen["ch30"], "cats": chosen.get("cats", []),
                  "headline": ai.get("headline", ""), "intro": ai.get("intro", ""),
                  "institutions": ai.get("institutions", ""), "risks": ai.get("risks", ""),
                  "evidence": ev[:5]})
    return picks[-120:]


def pick_view(picks):
    """오늘 소개 + 지난 소개(소개 당시 대비 현재 수익률)"""
    if not picks:
        return None, []
    ids = ",".join(dict.fromkeys(p["id"] for p in picks[-15:]))
    cur = safe("CG 소개코인 시세", lambda: cg_get(
        "simple/price?ids=%s&vs_currencies=usd&include_24hr_change=true" % ids), {}) or {}
    past = []
    for p in reversed(picks[-15:]):
        q = cur.get(p["id"]) or {}
        px = num(q.get("usd"))
        past.append({"date": p["date"], "sym": p["sym"], "name": p["name"],
                     "headline": p.get("headline", ""), "pickPrice": p.get("price"),
                     "price": px, "since": (px / p["price"] - 1) * 100
                     if px and p.get("price") else None})
    today = dict(picks[-1])
    q = cur.get(today["id"]) or {}
    today["now"] = num(q.get("usd"))
    today["ch24"] = num(q.get("usd_24h_change"))
    return today, past[1:]


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
    picks = safe("오늘의 코인", lambda: daily_pick([c[2] for c in COINS]), load_picks())
    pick, past = pick_view(picks)
    all_news = [n for c in coins for n in c["news"]] + ((pick or {}).get("evidence") or [])
    safe("뉴스 번역", lambda: translate_titles(all_news), None)
    brief = safe("AI 브리핑", lambda: ai_brief(coins), None) or {}
    for c in coins:
        c["brief"] = (brief.get("coins") or {}).get(c["sym"], "")
    return {"updated": now.strftime("%Y-%m-%d %H:%M KST"),
            "fng": safe("공포탐욕", fear_greed, None),
            "overall": brief.get("overall", ""),
            "pick": pick, "pastPicks": past,
            "coins": coins,
            "errors": ERRORS}, picks


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
    payload, picks = build()
    with open("crypto.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    if picks:
        os.makedirs("history", exist_ok=True)
        with open(PICK_PATH, "w", encoding="utf-8") as f:
            json.dump(picks, f, ensure_ascii=False, indent=1)
    save_history(payload)
    print("crypto done · 오류 %d건" % len(ERRORS))
