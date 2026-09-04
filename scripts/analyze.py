import json, os, urllib.request, datetime

key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
with open("data.json", encoding="utf-8") as f:
    payload = json.load(f)

if not key:
    print("키 없음 - 분석 건너뜀")
    raise SystemExit(0)

prompt = (
    "너는 시장 데이터 정리 담당이다. 아래 JSON은 오늘 자동 수집된 원자료다.\n"
    "한국어로 8~12줄 요약을 써라. 규칙:\n"
    "1) 섹터 자금 흐름, COT 포지셔닝, 온체인/펀딩비 세 축을 각각 짚을 것\n"
    "2) COT는 3일 지연 데이터이므로 방향 예측이 아니라 '포지션 과밀도/취약성' 관점으로만 해석\n"
    "3) 실시간 펀딩비·미결제약정과 COT가 엇갈리는 지점이 있으면 반드시 언급\n"
    "4) '수집 실패'로 표시된 항목은 해석하지 말고 실패했다고만 적을 것\n"
    "5) 매수/매도 추천은 하지 말고 관찰된 사실과 그 함의만 서술\n"
    "6) 머리말 없이 본문만 출력\n\n"
    + json.dumps(payload, ensure_ascii=False)[:60000]
)

body = json.dumps({"model": "claude-sonnet-5", "max_tokens": 1200,
                   "messages": [{"role": "user", "content": prompt}]}).encode()
req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                             headers={"content-type": "application/json",
                                      "x-api-key": key,
                                      "anthropic-version": "2023-06-01"})
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read().decode())
    txt = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
    payload["summary"] = txt.strip() or "분석 결과가 비어 있습니다."
except Exception as e:
    payload["summary"] = "분석 실패: %s" % str(e)[:200]

KST = datetime.timezone(datetime.timedelta(hours=9))
day = datetime.datetime.now(KST).strftime("%Y-%m-%d")
for p in ("data.json", "reports/%s.json" % day):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
files = sorted([f for f in os.listdir("reports")
                if f.endswith(".json") and f != "list.json"], reverse=True)
with open("reports/list.json", "w", encoding="utf-8") as f:
    json.dump(files, f)
print("analyze done")
