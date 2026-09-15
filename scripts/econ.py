import json, os, urllib.request, urllib.error, datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CACHE = "history/econ.json"

def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save(items, updated, note):
    os.makedirs("history", exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump({"updated": updated, "items": items}, f, ensure_ascii=False)
    with open("data.json", encoding="utf-8") as f:
        payload = json.load(f)
    payload["sections"].insert(1, {"title": "미국 경제지표",
                                   "note": note, "items": items})
    day = now.strftime("%Y-%m-%d")
    for p in ("data.json", "reports/%s.json" % day):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

cache = load_cache()
# 월요일(0), 목요일(3)에만 검색. 그 외에는 캐시 사용
if now.weekday() not in (0, 3) or not key:
    items = cache.get("items")
    if items:
        save(items, cache.get("updated", "-"),
             "캐시 · 마지막 검색 %s" % cache.get("updated", "-"))
        print("캐시 사용")
    else:
        print("캐시 없음, 건너뜀")
    raise SystemExit(0)

prompt = (
    "오늘은 %s이다. 미국 경제지표 6개의 가장 최근 발표 결과를 웹에서 확인하라.\n"
    "대상: CPI(소비자물가), PPI(생산자물가), PCE(개인소비지출 물가), "
    "비농업고용+실업률, FOMC 금리결정, ISM 제조업 PMI\n\n"
    "각 지표마다 아래 JSON 형식으로만 답하라. 설명이나 마크다운 없이 배열만 출력한다.\n"
    '[{"name":"CPI 소비자물가","value":"전년비 2.8%%","change":"예상 2.9%%",'
    '"comment":"2026-09-11 발표 · 전월 3.0%% · 예상 하회"}]\n\n'
    "규칙:\n"
    "- name은 한글 지표명\n"
    "- value는 핵심 수치 한 개\n"
    "- change는 시장 예상치. 없으면 빈 문자열\n"
    "- comment는 '발표일 · 전월치 · 예상 대비' 순으로 40자 내외\n"
    "- 확인 못한 지표는 value를 '확인 실패'로 하고 comment에 이유\n"
    "- 다음 발표 예정일을 아는 경우 comment 끝에 '차기 MM-DD' 추가\n"
    "- 추측 금지. 검색으로 확인한 숫자만 쓴다\n"
) % now.strftime("%Y년 %m월 %d일")

body = json.dumps({
    "model": "claude-sonnet-5",
    "max_tokens": 3000,
    "messages": [{"role": "user", "content": prompt}],
    "tools": [{"type": "web_search_20250305", "name": "web_search",
               "max_uses": 6,
               "allowed_domains": ["bls.gov", "bea.gov", "federalreserve.gov",
                                   "ismworld.org", "reuters.com", "investing.com",
                                   "tradingeconomics.com"]}],
}).encode()

req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                             headers={"content-type": "application/json",
                                      "x-api-key": key,
                                      "anthropic-version": "2023-06-01"})
items = None
try:
    with urllib.request.urlopen(req, timeout=420) as r:
        res = json.loads(r.read().decode())
    txt = "\n".join(b.get("text", "") for b in res.get("content", [])
                    if isinstance(b, dict) and b.get("type") == "text")
    s, e = txt.find("["), txt.rfind("]")
    if s < 0 or e < 0:
        raise ValueError("JSON 없음: " + txt[:120])
    items = json.loads(txt[s:e + 1])
    for it in items:
        it.setdefault("change", "")
        it.setdefault("comment", "")
except urllib.error.HTTPError as ex:
    print("HTTP", ex.code, ex.read().decode("utf-8", "replace")[:300])
except Exception as ex:
    print("실패:", str(ex)[:300])

if items:
    save(items, now.strftime("%Y-%m-%d"), "웹 검색 기준 · 수치는 원문 확인 권장")
    print("econ done", len(items), "건")
else:
    old = cache.get("items")
    if old:
        save(old, cache.get("updated", "-"), "검색 실패 · 이전 결과 표시")
        print("검색 실패, 캐시 사용")
