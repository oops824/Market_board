import json, os, urllib.request, urllib.error, datetime

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

def call(model):
    body = json.dumps({"model": model, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"content-type": "application/json",
                                          "x-api-key": key,
                                          "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read().decode("utf-8", "replace")[:600]}
    except Exception as e:
        return {"_err": str(e)[:300]}

summary = ""
for model in ("claude-sonnet-5", "claude-haiku-4-5-20251001"):
    res = call(model)
    print("=== %s ===" % model)
    print(json.dumps(res, ensure_ascii=False)[:2500])
    if "_http" in res:
        summary = "분석 실패 (HTTP %s): %s" % (res["_http"], res["_body"])
        continue
    if "_err" in res:
        summary = "분석 실패: " + res["_err"]
        continue
    txt = "\n".join(b["text"] for b in res.get("content", [])
                    if isinstance(b, dict) and b.get("text"))
    if txt.strip():
        summary = txt.strip()
        break
    summary = "응답이 비었음. 모델=%s / stop=%s / 블록타입=%s" % (
        res.get("model"), res.get("stop_reason"),
        [b.get("type") for b in res.get("content", []) if isinstance(b, dict)])

payload["summary"] = summary or "분석 결과 없음"

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
