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
STALE_DAYS = 200          # 최신 공시가 이보다 오래되면 제출중단으로 표시

# CIK 는 2026-09-28 기준 SEC EDGAR / 13f.info 에서 등록명을 대조해 검증 완료.
# 운용사를 추가할 때는 반드시 --verify-cik 로 등록명을 먼저 확인할 것.
MANAGERS = [
    # (표시명, CIK, 카테고리)
    ("버크셔 해서웨이 (버핏)",      "0001067983", "value"),
    ("아이칸 (칼 아이칸)",          "0000921669", "value"),
    ("퍼싱스퀘어 (애크먼)",         "0001336528", "value"),

    ("브리지워터 (달리오)",         "0001350694", "macro"),
    ("듀케인 (드러켄밀러)",         "0001536411", "macro"),
    ("소로스 펀드 매니지먼트",      "0001029160", "macro"),
    ("아팔루사 (테퍼)",             "0001656456", "macro"),

    ("틸 매크로 (피터 틸)",         "0001562087", "paypal"),
    ("알티미터 (거스트너)",         "0001541617", "paypal"),
    ("코투 매니지먼트",             "0001135730", "paypal"),

    ("국민연금공단",                "0001608046", "korea"),
]

CATEGORIES = {
    "value":  "가치·행동주의",
    "macro":  "매크로·헤지펀드",
    "paypal": "페이팔 마피아·테크",
    "policy": "정책·연준 출신",     # 13F 미제출 — 뉴스 전용
    "korea":  "국내 (국민연금)",
}

# 뉴스 전용 인물 — 13F 제출 의무가 없거나 제출을 중단한 인물
NEWS_ONLY = [
    ("재닛 옐런", "policy", "Janet Yellen"),
    ("제롬 파월", "policy", "Jerome Powell"),
    ("래리 서머스", "policy", "Larry Summers"),
    ("케빈 워시", "policy", "Kevin Warsh"),
    # 버리는 2025-11 사이언 에셋 등록말소로 13F 제출 중단 → 발언만 추적
    ("마이클 버리", "macro", "Michael Burry"),
]

# 13F 제출자 중 뉴스도 같이 볼 인물 (표시명: 영문 검색어)
NEWS_FOR_MANAGERS = {
    "버크셔 해서웨이 (버핏)": "Warren Buffett",
    "아이칸 (칼 아이칸)": "Carl Icahn",
    "퍼싱스퀘어 (애크먼)": "Bill Ackman",
    "브리지워터 (달리오)": "Ray Dalio",
    "듀케인 (드러켄밀러)": "Stanley Druckenmiller",
    "소로스 펀드 매니지먼트": "George Soros fund",
    "아팔루사 (테퍼)": "David Tepper",
    "틸 매크로 (피터 틸)": "Peter Thiel",
    "알티미터 (거스트너)": "Brad Gerstner",
    "코투 매니지먼트": "Coatue Philippe Laffont",
    "국민연금공단": "국민연금 해외투자",
}

NEWS_KEYWORDS = "macro OR economy OR markets OR Fed OR inflation"
NEWS_PER_PERSON = 3

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


def build_consensus(managers):
    """여러 운용사가 같은 분기에 동시에 사고/판 종목."""
    bought, sold = defaultdict(list), defaultdict(list)
    for m in managers:
        if m.get("error") or m.get("stale") or m.get("category") == "korea":
            continue
        for r in m["new_buys"] + m["added"]:
            bought[(r["cusip"], r["name"])].append(m["name"])
        for r in m["sold_out"] + m["trimmed"]:
            sold[(r["cusip"], r["name"])].append(m["name"])

    def pack(d):
        out = []
        for (cusip, name), who in d.items():
            who = sorted(set(who))
            if len(who) >= CONSENSUS_MIN:
                out.append({"cusip": cusip, "name": name,
                            "count": len(who), "managers": who})
        return sorted(out, key=lambda r: -r["count"])[:15]

    return {"bought": pack(bought), "sold": pack(sold)}


# ---------------------------------------------------------------- 뉴스

def fetch_news(person_en, limit=NEWS_PER_PERSON):
    q = urllib.parse.quote(f'"{person_en}" ({NEWS_KEYWORDS})')
    url = f"https://news.google.com/rss/search?q={q}+when:30d&hl=en-US&gl=US&ceid=US:en"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  ! 뉴스 실패 {person_en}: {e}")
        return []
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src_el = it.find("source")
        source = src_el.text.strip() if src_el is not None and src_el.text else ""
        if not title:
            continue
        title = re.sub(r"\s+-\s+[^-]+$", "", title)   # 꼬리 매체명 제거
        items.append({"title": title, "url": link, "source": source, "published": pub})
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------- 메인

def verify_ciks():
    print("CIK 검증 — 등록명이 의도한 운용사와 맞는지 확인하세요.\n")
    for name, cik, _ in MANAGERS:
        try:
            registered, filings = latest_13f_filings(cik, 1)
            period = filings[0]["period"] if filings else "13F 없음"
            print(f"  {name:28s} {cik}  ->  {registered}  (최근 {period})")
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

    for name, cik, category in MANAGERS:
        print(f"[13F] {name}")
        entry = {"name": name, "cik": cik,
                 "category": category, "category_label": CATEGORIES[category]}
        try:
            registered, filings = latest_13f_filings(cik, 2)
            entry["registered_name"] = registered
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
    print("[뉴스]")
    news = []
    for disp, en in NEWS_FOR_MANAGERS.items():
        cat = next((c for n, _, c in MANAGERS if n == disp), "value")
        for a in fetch_news(en):
            a.update({"person": disp, "category": cat,
                      "category_label": CATEGORIES[cat]})
            news.append(a)
    for disp, cat, en in NEWS_ONLY:
        for a in fetch_news(en):
            a.update({"person": disp, "category": cat,
                      "category_label": CATEGORIES[cat]})
            news.append(a)
    print(f"  -> 뉴스 {len(news)}건")
    return {"news": news, "news_updated_at": datetime.now(timezone.utc).isoformat()}


def main(mode):
    payload = load_existing()
    payload.setdefault("managers", [])
    payload.setdefault("news", [])

    if mode in ("all", "13f"):
        payload.update(collect_13f())
    if mode in ("all", "news"):
        payload.update(collect_news())

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
    ap.add_argument("--mode", choices=["all", "13f", "news"], default="all",
                    help="13f=보유내역만, news=뉴스만, all=둘 다 (기본)")
    args = ap.parse_args()
    verify_ciks() if args.verify_cik else main(args.mode)
