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
import signals
import calendar_ctx

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


def quiet(fn):
    try:
        return fn()
    except Exception as e:
        print("[없음]", e)
        return None


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
        time.sleep(4)
        try:
            return json.loads(get("https://api.coingecko.com/api/v3/" + path))
        except urllib.error.HTTPError as e:
            if e.code != 429 or i:
                raise
            time.sleep(65)


def coingecko():
    ids = ",".join(c[2] for c in COINS)
    rows = cg_get("coins/markets?vs_currency=usd"
                  "&ids=%s&sparkline=true&price_change_percentage=24h,7d,30d" % ids)
    out = {}
    for r in rows:
        spark = (r.get("sparkline_in_7d") or {}).get("price") or []
        step = 2  # 168개(1시간봉) -> 84개(2시간 간격)로 축소
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
            # 7일 차트: 마지막 점이 수집 시각, 점 간격 step시간
            "spark": [round(p, 6) for p in spark[::-1][::step][::-1] if p is not None],
            "sparkEnd": int(now.timestamp() * 1000), "sparkStepH": step,
        }
    return out


def coingecko_krw():
    ids = ",".join(c[2] for c in COINS)
    j = cg_get("simple/price?ids=%s&vs_currencies=krw" % ids)
    return {k: num(v.get("krw")) for k, v in j.items()}


# ---------- CoinGecko 대체: CoinPaprika (+ OKX 2시간봉, 원/달러 환율) ----------
# 2026-09-29 부터 CoinGecko 무료 API 가 GitHub Actions 요청에 403 을 반환 → 실패 시 사용
_PAP = None
STABLE_SYMS = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "USDD", "PYUSD", "USDS", "USD1",
               "RLUSD", "USDTB", "FRAX", "USDG", "BUIDL", "USDF", "USD0", "GHO", "CRVUSD",
               "XAUT", "PAXG"}


def paprika_all():
    global _PAP
    if _PAP is None:
        _PAP = [r for r in json.loads(get("https://api.coinpaprika.com/v1/tickers?quotes=USD", 60))
                if r.get("rank")]
        _PAP.sort(key=lambda r: r["rank"])
    return _PAP


def paprika_by_sym(sym):
    for r in paprika_all():                       # 순위순 → 같은 심볼이면 시총 큰 것
        if r["symbol"].upper() == sym.upper():
            return r
    return None


def okx_spark(ccy):
    """7일 차트용 2시간봉 종가 84개 (과거->최신)"""
    rows = json.loads(get("%s/market/candles?instId=%s-USDT-SWAP&bar=2H&limit=84"
                          % (OKX, ccy))).get("data") or []
    return [round(float(r[4]), 6) for r in rows[::-1]]


def usdkrw():
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?range=5d&interval=1d"))
    return float(j["chart"]["result"][0]["meta"]["regularMarketPrice"])


def market_paprika():
    rate = quiet(usdkrw)
    out = {}
    for sym, _ko, cg_id, _hl, okx_ccy, _q1, _q2 in COINS:
        r = paprika_by_sym(sym)
        if not r:
            continue
        q = r["quotes"]["USD"]
        px = num(q.get("price"))
        out[cg_id] = {
            "price": px, "mcap": num(q.get("market_cap")), "rank": r.get("rank"),
            "vol": num(q.get("volume_24h")), "high24": None, "low24": None,
            "ch24": num(q.get("percent_change_24h")), "ch7": num(q.get("percent_change_7d")),
            "ch30": num(q.get("percent_change_30d")), "ath": num(q.get("ath_price")),
            "athPct": num(q.get("percent_from_price_ath")),
            "spark": quiet(lambda c=okx_ccy: okx_spark(c)) or [],
            "sparkEnd": int(now.timestamp() * 1000), "sparkStepH": 2,
            "krw": px * rate if px and rate else None, "src": "CoinPaprika",
        }
    if not out:
        raise ValueError("CoinPaprika 데이터 없음")
    return out


def market_data():
    """CoinGecko 우선, 막히면 CoinPaprika. 둘 다 실패할 때만 오류로 기록"""
    try:
        cg = coingecko()
        krw = quiet(coingecko_krw) or {}
        for k, m in cg.items():
            m["krw"] = krw.get(k)
        return cg
    except Exception as e:
        print("[CoinGecko 실패 → CoinPaprika]", e)
    return market_paprika()


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
    try:  # 미결제약정 24시간 변화 (1시간 간격, 최신이 앞)
        oh = json.loads(get("%s/rubik/stat/contracts/open-interest-volume"
                            "?ccy=%s&period=1H" % (OKX, ccy))).get("data") or []
        if len(oh) > 24 and num(oh[24][1]):
            out["oiChg24"] = (num(oh[0][1]) / num(oh[24][1]) - 1) * 100
    except Exception:
        pass
    if not out:
        raise ValueError("OKX 응답 없음")
    return out


def okx_daily(ccy):
    """무기한 선물 일봉 120개 -> (종가, 고가, 저가, 거래대금, 시각). 과거->최신"""
    rows = json.loads(get("%s/market/candles?instId=%s-USDT-SWAP&bar=1D&limit=120"
                          % (OKX, ccy))).get("data") or []
    rows = rows[::-1]
    done = [r for r in rows if str(r[8]) == "1"]  # 마감된 봉
    cur = [r for r in rows if str(r[8]) != "1"]
    closes = [float(r[4]) for r in done + cur]
    highs = [float(r[2]) for r in done + cur]
    lows = [float(r[3]) for r in done + cur]
    vols = [float(r[7]) for r in done]  # 거래량은 마감된 봉만 비교
    ts = [int(r[0]) for r in done + cur]  # 봉 시작 시각(ms)
    return closes, highs, lows, vols, ts


_USDT_USD = None


def cb_premium(ccy):
    """코인베이스(USD) 가격 / OKX 현물(USDT, 달러 환산) - 1, %"""
    global _USDT_USD
    if _USDT_USD is None:
        _USDT_USD = num(json.loads(get("https://api.exchange.coinbase.com/products/"
                                       "USDT-USD/ticker")).get("price")) or 1.0
    cb = num(json.loads(get("https://api.exchange.coinbase.com/products/%s-USD/ticker"
                            % ccy)).get("price"))
    ok = num((json.loads(get("%s/market/ticker?instId=%s-USDT" % (OKX, ccy)))
              .get("data") or [{}])[0].get("last"))
    if not cb or not ok:
        raise ValueError("시세 없음")
    return (cb / (ok * _USDT_USD) - 1) * 100


def deriv_signals(c):
    """펀딩비·미결제약정·롱숏비율·코인베이스 프리미엄·맥스페인 -> 신호"""
    T = signals.tag
    m, hl, ok, op = c.get("market") or {}, c.get("hl") or {}, c.get("okx") or {}, c.get("options")
    out = []
    f8 = [x for x in ((hl.get("funding") or 0) * 800 if hl.get("funding") is not None else None,
                      (ok.get("funding") or 0) * 100 if ok.get("funding") is not None else None)
          if x is not None]
    f8 = sum(f8) / len(f8) if f8 else None
    ch24 = m.get("ch24")
    if f8 is not None:
        if f8 >= 0.03:
            out.append(T("펀딩 과열", "warn", 6))
        elif f8 < 0 and (ch24 or 0) > 0:
            out.append(T("숏 스퀴즈 주의", "warn", 8))
        elif f8 < 0:
            out.append(T("숏 우세 펀딩", "dn", 4))
    oc = ok.get("oiChg24")
    if oc is not None and ch24 is not None:
        if oc >= 8:
            out.append(T("신규 롱 유입", "up", 6) if ch24 >= 0 else T("신규 숏 유입", "dn", 6))
        elif oc <= -8:
            out.append(T("숏 커버링", "up", 5) if ch24 >= 0 else T("롱 청산", "dn", 5))
    ls = ok.get("lsRatio")
    if ls is not None:
        if ls >= 2:
            out.append(T("롱 쏠림 %.1f" % ls, "warn", 4))
        elif ls <= 0.8:
            out.append(T("숏 쏠림 %.1f" % ls, "warn", 4))
    ef = c.get("etf")
    if ef and not ef.get("stale"):
        st = ef.get("streak") or 0
        if ef["sum5"] > 0 and st >= 2:
            out.append(T("ETF %d일 연속 순유입" % st, "up", 7))
        elif ef["sum5"] < 0 and st <= -2:
            out.append(T("ETF %d일 연속 순유출" % -st, "dn", 7))
        elif ef["sum5"] > 0:
            out.append(T("ETF 주간 순유입", "up", 5))
        elif ef["sum5"] < 0:
            out.append(T("ETF 주간 순유출", "dn", 5))
    pr = c.get("cbPrem")
    if pr is not None and abs(pr) >= 0.05:
        out.append(T("미국 매수 우위", "up", 6) if pr > 0 else T("미국 매도 우위", "dn", 6))
    if op and m.get("price"):
        d = (op["major"]["maxPain"] / m["price"] - 1) * 100
        if abs(d) >= 8:
            out.append(T("맥스페인 괴리 %+.0f%%" % d, "na", 3))
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
                    {"news": [n["title"] for n in c.get("news", [])][:6],
                     "signals": [t["t"] for t in c.get("tags", [])]})
    for s in slim:
        if s.get("market"):
            s["market"] = {k: v for k, v in s["market"].items() if k != "spark"}
        if s.get("options"):
            s["options"] = {k: v for k, v in s["options"].items() if k != "expiries"}
    prompt = (
        "너는 가상자산 데이터 정리 담당이다. 아래 JSON은 관심 코인별로 방금 수집한 "
        "가격·선물(펀딩비, 미결제약정, 롱숏비율)·옵션(맥스페인, 풋콜비율)·뉴스 제목이다.\n"
        "코인마다 한국어 2문장으로 요약하라: 1문장은 뉴스의 핵심 이슈, "
        "1문장은 선물·옵션 포지셔닝이 말하는 것(과열/중립/위축, 맥스페인과 현재가 거리).\n"
        "그리고 8개 코인 전체를 아우르는 요약 2~3문장을 overall로 작성하라.\n"
        + calendar_ctx.macro_context(now.date()) + "\n"
        "규칙: 매수/매도 추천 금지, 관찰된 사실과 함의만. 데이터가 없으면 없다고만. "
        "hl.funding은 시간당, okx.funding은 8시간 기준 소수값이다.\n"
        + calendar_ctx.RULE +
        "출력은 다른 말 없이 JSON 한 개만: "
        "{\"overall\": \"...\", \"coins\": {\"BTC\": \"...\", ...}}\n\n"
        + json.dumps(slim, ensure_ascii=False)[:50000])
    return claude_json(prompt, 4000)


def claude_json(prompt, max_tokens, models=("claude-sonnet-5", "claude-haiku-4-5-20251001")):
    """프롬프트를 보내고 응답 속 JSON(객체/배열) 하나를 파싱해 반환. 키가 없으면 None"""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    fails = []
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
            fails.append("%s: %s" % (model, str(e)[:100]))
            print("[AI 실패 → 다음 모델]", fails[-1])
    if fails:                                  # 모든 모델이 실패했을 때만 화면 오류로
        ERRORS.append("AI 실패 — " + " / ".join(fails))
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


def pick_candidates(skip_ids, skip_syms=()):
    try:
        return pick_candidates_cg(skip_ids, skip_syms)
    except Exception as e:
        print("[후보: CoinGecko 실패 → CoinPaprika]", e)
    out = []
    for r in paprika_all()[:250]:
        q, rank, sym = r["quotes"]["USD"], r["rank"], r["symbol"].upper()
        mcap, vol = num(q.get("market_cap")), num(q.get("volume_24h"))
        if rank <= 10 or not mcap or sym in STABLE_SYMS or sym in skip_syms or r["id"] in skip_ids:
            continue
        if EXCL_NAME.search(r.get("name", "")) or EXCL_NAME.search(sym):
            continue
        ch7 = num(q.get("percent_change_7d")) or 0
        ch30 = num(q.get("percent_change_30d")) or 0
        turn = min((vol or 0) / mcap, 1.0)
        score = max(-1, min(ch30, 150)) / 50 + max(-1, min(ch7, 60)) / 20 + turn * 3
        out.append({"id": r["id"], "sym": sym, "name": r["name"], "rank": rank,
                    "price": num(q.get("price")), "mcap": mcap, "vol": vol, "ch7": ch7,
                    "ch30": ch30, "trending": False, "score": round(score, 3), "src": "paprika"})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:20]


def pick_candidates_cg(skip_ids, skip_syms=()):
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
        if not rank or rank <= 10 or not mcap or r["id"] in excl or r["id"] in skip_ids \
                or r["symbol"].upper() in skip_syms:
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
    return out[:20]


def news_search(q, lang, days):
    """구글 뉴스(기간 지정) → 실패·빈 결과면 Bing. 둘 다 실패하면 빈 목록"""
    cut = datetime.timedelta(days=days)
    loc = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    try:
        items = rss_items(get("https://news.google.com/rss/search?q=%s&%s" % (
            urllib.parse.quote("%s when:%dd" % (q, days)), loc), 20), lang, cut=cut)
        if items:
            return items
    except Exception as e:
        print("[구글 뉴스 실패 → Bing]", str(e)[:80])
    return quiet(lambda: bing(q, lang, cut)) or []


def inst_evidence(c):
    q = '"%s" (ETF OR BlackRock OR Grayscale OR Fidelity OR institutional OR "Wall Street")' % c["name"]
    items = news_search(q, "en", 30) + news_search("%s 기관 ETF" % c["name"], "ko", 30)
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
    recent_syms = {p["sym"] for p in picks if p.get("date", "") >= cutoff}
    cands = pick_candidates(set(held_ids) | recent, recent_syms | {c[0] for c in COINS})
    for c in cands:
        c["evidence"] = inst_evidence(c)
    # 기관 관여 기사가 2건 이상인 후보만. 없으면 억지로 고르지 않고 다음 실행에서 재시도
    strong = sorted([c for c in cands if len(c["evidence"]) >= 2],
                    key=lambda c: (len(c["evidence"]), c["score"]), reverse=True)
    if not strong:
        print("오늘의 코인: 기관 관여 기사 2건 이상인 후보 없음 (다음 실행에서 재시도)")
        return picks
    strong = strong[:5]
    for c in strong:
        if c.get("src") == "paprika":
            d = quiet(lambda i=c["id"]: json.loads(get("https://api.coinpaprika.com/v1/coins/" + i))) or {}
            c["desc"] = (d.get("description") or "")[:700]
            c["cats"] = [t.get("name") for t in (d.get("tags") or []) if t.get("name")][:5]
            continue
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
    cur = quiet(lambda: cg_get(
        "simple/price?ids=%s&vs_currencies=usd&include_24hr_change=true" % ids)) or {}
    for p in picks[-15:]:                 # CoinGecko 실패분은 CoinPaprika(심볼)로
        if p["id"] not in cur:
            r = quiet(lambda s_=p["sym"]: paprika_by_sym(s_))
            if r:
                q = r["quotes"]["USD"]
                cur[p["id"]] = {"usd": q.get("price"), "usd_24h_change": q.get("percent_change_24h")}
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


# ---------- 현물 ETF 자금 흐름 (Farside Investors) ----------
# 자산별 후보 주소 (앞에서부터 시도). LINK 는 Farside 페이지가 확인되지 않아 추정 주소 + 홈페이지 링크 탐색
ETF_URL = {"BTC": ["https://farside.co.uk/bitcoin-etf-flow-all-data/"],
           "ETH": ["https://farside.co.uk/ethereum-etf-flow-all-data/"],
           "SOL": ["https://farside.co.uk/sol/", "https://farside.co.uk/solana-etf-flow-all-data/"],
           "HYPE": ["https://farside.co.uk/hyp/", "https://farside.co.uk/hyperliquid-etf-flow-all-data/"],
           "LINK": ["https://farside.co.uk/link/", "https://farside.co.uk/chainlink/",
                    "https://farside.co.uk/chainlink-etf-flow-all-data/"]}
ETF_HOME_KEY = {"SOL": "sol", "HYPE": "hyp|hyperliquid", "LINK": "link|chainlink"}
ETF_CACHE = "history/etf_flows.json"


def _html_rows(html):
    """HTML 표의 모든 행을 [셀 텍스트, ...] 목록으로 (표준 라이브러리만 사용)"""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows, self.row, self.cell = [], None, None

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = []

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.row is not None and self.cell is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
                self.cell = None
            elif tag == "tr" and self.row is not None:
                if self.row:
                    self.rows.append(self.row)
                self.row = None

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)

    p = P()
    p.feed(html)
    return p.rows


def _flow_num(t):
    """'123.4' / '(56.7)' = -56.7 / '-' 또는 빈칸 = 0 / 숫자 아님 = None  (단위: 백만 달러)"""
    t = (t or "").replace(",", "").replace("$", "").strip()
    if t in ("", "-", "–", "—"):
        return 0.0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def parse_farside(html):
    """Farside 표 -> [{"d": 날짜, "total": 합계, "by": {티커: 값}}] (과거->최신)"""
    rows = _html_rows(html)
    head = None
    for r in rows:   # 티커 행: 대문자 티커(2~6자)가 2개 이상인 마지막 머리글 행
        tick = [x.strip() for x in r if re.fullmatch(r"[A-Z][A-Z0-9]{1,5}", x.strip())
                and x.strip() != "TOTAL"]
        if len(tick) >= 2 and not re.match(r"\d{1,2} [A-Z][a-z]{2} \d{4}", r[0].strip()):
            head = tick
    print("[ETF] 머리글 티커:", head)
    out = []
    for r in rows:
        try:
            d = datetime.datetime.strptime(r[0].strip(), "%d %b %Y").date()
        except (ValueError, IndexError):
            continue
        vals = [_flow_num(x) for x in r[1:]]
        if not vals or vals[-1] is None or \
                all(x.strip() in ("", "-", "–", "—") for x in r[1:-1]):
            continue                       # 아직 집계 전인 날 (ETF별 칸이 전부 '-' 또는 빈칸)
        by = {}
        etf_vals = vals[:-1]                # 마지막 칸은 합계
        if head and len(head) <= len(etf_vals):
            # 앞쪽에 수수료·기타 칸이 끼어 있어도 오른쪽(합계 바로 앞) 기준으로 맞춘다
            for k, v in zip(head, etf_vals[len(etf_vals) - len(head):]):
                if v:
                    by[k] = round(v, 1)
        out.append({"d": d.isoformat(), "total": round(vals[-1], 1), "by": by})
    out.sort(key=lambda x: x["d"])
    return out


def etf_fetch(url):
    import requests
    h = {"User-Agent": UA["User-Agent"], "Accept": "text/html,application/xhtml+xml",
         "Accept-Language": "en-US,en;q=0.9", "Referer": "https://farside.co.uk/"}
    r = requests.get(url, headers=h, timeout=30)
    if r.status_code in (403, 503):        # 클라우드플레어 차단 시 우회 클라이언트
        try:
            import cloudscraper
            r = cloudscraper.create_scraper().get(url, timeout=30)
        except ImportError:
            pass
    r.raise_for_status()
    return r.text


def etf_flows():
    """BTC·ETH 현물 ETF 일별 순유입(백만 달러). 실패하면 마지막 성공값을 재사용"""
    try:
        with open(ETF_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    out = {}
    home = None
    for a, urls in ETF_URL.items():
        urls = list(urls)
        if a in ETF_HOME_KEY:              # 홈페이지 메뉴에서 해당 자산 페이지 링크 찾기
            if home is None:
                home = quiet(lambda: etf_fetch("https://farside.co.uk/")) or ""
            for h in re.findall(r'href="(https://farside\.co\.uk/[^"#?]+)"', home):
                if re.search(r"/(%s)[-/]" % ETF_HOME_KEY[a], h, re.I) and h not in urls:
                    urls.append(h)
        err = None
        for url in urls:
            try:
                days = parse_farside(etf_fetch(url))
                if len(days) < 3:
                    raise ValueError("표 파싱 결과 %d일" % len(days))
                cache[a] = {"days": days[-30:], "at": now.isoformat(), "url": url}
                err = None
                break
            except Exception as e:
                err = e
        if err is not None:
            if a in ("BTC", "ETH") or a in cache:   # 원래 되던 자산만 오류로 표시
                ERRORS.append("ETF 흐름 %s: %s" % (a, str(err)[:80]))
            else:
                print("[ETF] %s 흐름 페이지 없음: %s" % (a, err))
        c = cache.get(a)
        if not c:
            continue
        days = c["days"]
        if len(days) < 3:
            continue
        last7 = days[-7:]
        out[a] = {"days": last7,
                  "last": days[-1],
                  "sum5": round(sum(x["total"] for x in days[-5:]), 1),
                  "sum7": round(sum(x["total"] for x in last7), 1),
                  "streak": _streak(days),
                  "fetched": c["at"][:16].replace("T", " "),
                  "stale": c["at"][:10] != now.date().isoformat() and
                           (now - datetime.datetime.fromisoformat(c["at"])).days >= 2,
                  "src": "Farside Investors"}
    os.makedirs("history", exist_ok=True)
    with open(ETF_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return out


def _streak(days):
    """최근 연속 순유입(+)/순유출(-) 일수"""
    n, sign = 0, 0
    for x in reversed(days):
        s_ = 1 if x["total"] > 0 else -1 if x["total"] < 0 else 0
        if s_ == 0 or (sign and s_ != sign):
            break
        sign, n = s_, n + 1
    return n * sign


# ---------- 비트코인 도미넌스 · TOTAL2 ----------
DOM_PATH = "history/dominance.json"


def _find(o, pat):
    """중첩 dict 에서 이름이 pat(정규식)에 맞는 첫 숫자 값"""
    if isinstance(o, dict):
        for k, v in o.items():
            if re.fullmatch(pat, k, re.I) and num(v) is not None:
                return num(v)
        for v in o.values():
            r = _find(v, pat)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find(v, pat)
            if r is not None:
                return r
    return None


def cmc_global_history(days=100):
    """CoinMarketCap 공개 차트 API: 일별 총 시총·BTC 도미넌스"""
    end = int(now.timestamp())
    j = json.loads(get("https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/historical"
                       "?format=chart&interval=1d&timeStart=%d&timeEnd=%d" % (end - days * 86400, end)))
    out = {}
    for q in (j.get("data") or {}).get("quotes") or []:
        ts = q.get("timestamp") or _find(q, "timestamp")
        dom = _find(q, "btcDominance")
        tot = _find(q, "totalMarketCap")
        if not ts or dom is None or not tot:
            continue
        d = str(ts)[:10]
        out[d] = {"d": d, "dom": round(dom, 3), "total": tot, "total2": tot * (1 - dom / 100)}
    if len(out) < 10:
        raise ValueError("CMC 응답 %d일" % len(out))
    return out


def global_now():
    """현재 총 시총·도미넌스 (CoinPaprika → CoinGecko)"""
    try:
        g = json.loads(get("https://api.coinpaprika.com/v1/global"))
        tot, dom = num(g.get("market_cap_usd")), num(g.get("bitcoin_dominance_percentage"))
    except Exception:
        g = cg_get("global")["data"]
        tot, dom = num(g["total_market_cap"]["usd"]), num(g["market_cap_percentage"]["btc"])
    if not tot or dom is None:
        raise ValueError("글로벌 시총 없음")
    return {"d": now.date().isoformat(), "dom": round(dom, 3), "total": tot,
            "total2": tot * (1 - dom / 100)}


def dominance():
    """일별 도미넌스·TOTAL2. 공급처마다 총 시총 집계 범위가 달라 섞으면 가짜 급변이 생기므로
    점마다 출처(src)를 저장하고, 차트는 한 출처의 점만 쓴다 (CMC 우선)"""
    try:
        with open(DOM_PATH, encoding="utf-8") as f:
            stored = json.load(f)
    except Exception:
        stored = []
    hist = {(h.get("src", "cmc"), h["d"]): h for h in stored}
    cmc = quiet(cmc_global_history)
    for d, h in (cmc or {}).items():
        hist[("cmc", d)] = dict(h, src="cmc")
    cur = quiet(global_now)
    if cur:
        hist[("pap", cur["d"])] = dict(cur, src="pap")      # 대체용 일별 기록
    rows = sorted(hist.values(), key=lambda h: (h["src"], h["d"]))
    cut = (now.date() - datetime.timedelta(days=400)).isoformat()
    rows = [h for h in rows if h["d"] >= cut]
    os.makedirs("history", exist_ok=True)
    with open(DOM_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    recent = (now.date() - datetime.timedelta(days=3)).isoformat()
    for src, label in (("cmc", "CoinMarketCap"), ("pap", "CoinPaprika 일별 기록")):
        sel = [h for h in rows if h["src"] == src]
        if sel and sel[-1]["d"] >= recent:
            sel = sel[-90:]
            return {"t": [h["d"] for h in sel], "dom": [h["dom"] for h in sel],
                    "total2": [round(h["total2"] / 1e9, 1) for h in sel],   # 십억 달러
                    "src": label}
    if not cur:
        ERRORS.append("도미넌스: CoinMarketCap·CoinPaprika 모두 실패")
    return None


# ---------- 조립 ----------
def build():
    cg = safe("시세(CoinGecko/CoinPaprika)", market_data, {})
    hl = safe("Hyperliquid", hyperliquid, {})
    etf = safe("ETF 흐름", etf_flows, {})
    dom = safe("도미넌스", dominance, None)
    opts = deribit()
    coins = []
    for sym, ko, cg_id, hl_name, okx_ccy, ko_q, en_q in COINS:
        m = cg.get(cg_id)
        coins.append({
            "sym": sym, "name": ko, "cg": cg_id,
            "market": m,
            "hl": hl.get(hl_name),
            "okx": safe("OKX " + okx_ccy, lambda c=okx_ccy: okx_coin(c), None),
            "options": opts.get(sym),
            "news": news(sym, ko_q, en_q),
            "cbPrem": quiet(lambda c=okx_ccy: cb_premium(c)),  # 코인베이스 미상장이면 None
            "etf": etf.get(sym),
        })
        cc = coins[-1]
        daily = safe("OKX 일봉 " + okx_ccy, lambda c=okx_ccy: okx_daily(c), None)
        tags = (signals.price_signals(*daily[:4]) if daily else []) + deriv_signals(cc)
        if daily and daily[4]:  # 30·90일 차트용 일봉 종가
            cc["daily"] = {"t": daily[4][-90:], "c": [round(x, 6) for x in daily[0][-90:]]}
        cc["tags"] = sorted(tags, key=lambda x: -x["p"])
    if not any(c["news"] for c in coins) and NEWS_FAIL:
        ERRORS.append("뉴스 수집 실패: " + " / ".join("%s %s" % kv for kv in NEWS_FAIL.items()))
    picks = safe("오늘의 코인", lambda: daily_pick([c[2] for c in COINS]), load_picks())
    pick, past = pick_view(picks)
    all_news = [n for c in coins for n in c["news"]] + ((pick or {}).get("evidence") or [])
    safe("뉴스 번역", lambda: translate_titles(all_news), None)
    import articles  # 영문 기사 본문 → 한국어 번역 요약
    safe("기사 번역", lambda: articles.enrich(all_news, "history/article_ko_crypto.json"), 0)
    brief = safe("AI 브리핑", lambda: ai_brief(coins), None) or {}
    for c in coins:
        c["brief"] = (brief.get("coins") or {}).get(c["sym"], "")
    return {"updated": now.strftime("%Y-%m-%d %H:%M KST"),
            "fng": safe("공포탐욕", fear_greed, None),
            "overall": brief.get("overall", ""),
            "pick": pick, "pastPicks": past,
            "etf": etf, "dom": dom,
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
