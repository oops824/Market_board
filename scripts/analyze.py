import copy, json, os, urllib.request, urllib.error, datetime
import calendar_ctx

SUMMARY_DAYS = 2                                    # 지표 탭 요약은 이 간격으로만 다시 쓴다(그 사이에는 직전 요약 유지)

# 요약에 쓰지 않는 블록은 보내지 않는다(실적은 미국주식 탭과 종합의견이 전담, summary 는 이 파일의 직전 출력)
DROP_KEYS = ("earnings", "summary")
DROP_SECS = ("실적 발표",)


def brief(p):
    """요약 7개 항목에 필요한 만큼만 남긴 데이터"""
    d = {k: v for k, v in p.items() if k not in DROP_KEYS}
    secs = []
    for s in d.get("sections", []):
        if s["title"].startswith(DROP_SECS):
            continue
        s = copy.deepcopy(s)
        if s["title"].startswith("섹터 ETF"):              # '…종가 · 반도체 대장주' 같은 상투구 제거
            for i in s["items"]:
                i.pop("comment", None)
        secs.append(s)
    d["sections"] = secs
    if d.get("econ", {}).get("items"):                     # 'ai' 해석은 수치를 다시 풀어쓴 것이라 앞부분만
        d["econ"] = copy.deepcopy(d["econ"])
        for i in d["econ"]["items"]:
            if i.get("ai"):
                i["ai"] = i["ai"][:200]
    return d

key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
with open("data.json", encoding="utf-8") as f:
    payload = json.load(f)

if not key:
    print("키 없음 - 분석 건너뜀")
    raise SystemExit(0)

now_kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
try:
    _age = (now_kst - datetime.datetime.fromisoformat(payload.get("summary_at") or "")).days
except (ValueError, TypeError):
    _age = None
if payload.get("summary") and _age is not None and _age < SUMMARY_DAYS \
        and os.environ.get("SUMMARY_FORCE") != "1":
    print("요약 재사용 - %s 작성(%d일 전), %d일마다 갱신" % (payload["summary_at"][:10], _age, SUMMARY_DAYS))
    raise SystemExit(0)

prompt = (
    "너는 시장 데이터 정리 담당이다. 아래 JSON은 오늘 자동 수집된 원자료다.\n"
    + calendar_ctx.macro_context(datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).date()) + "\n"
    "아래 형식을 정확히 지켜 한국어로 작성하라. 각 항목 사이에 빈 줄을 반드시 넣어라.\n\n"
    "econ(미국 경제지표 발표·발표일 시장 반응)이 있으면 가장 최근 발표 결과가 금리·달러·위험자산 "
    "움직임과 어떻게 연결되는지 [매크로·유동성] 항목에서 반드시 언급하라.\n\n"
    "[종합]\n"
    "개조식 3~4줄. 오늘 시장의 큰 그림과 가장 눈에 띄는 신호 하나.\n\n"
    "[매크로·유동성]\n"
    "2줄. 금리, 달러, VIX, 위험선호(HYG/TLT), 시장 폭, 유가(WTI·브렌트)·금 중심.\n\n"
    "[섹터]\n"
    "2줄. 섹터 ETF 등락, 반도체 주도력(SMH/SPY), 섹터 로테이션(SPY 대비 상대강도)에서 주도·돌아서는 섹터와 조기 신호·과열 표시 중심.\n\n"
    "[COT 포지셔닝]\n"
    "2줄. 방향 예측이 아니라 포지션 과밀도와 취약성 관점으로만.\n\n"
    "[암호화폐]\n"
    "2줄. 스테이블코인 발행량, 코인베이스 프리미엄, 디파이 프로토콜 수익 중심.\n\n"
    "[체크포인트]\n"
    "다음 며칠 확인할 것 2~3개를 '- '로 시작하는 줄로.\n\n"
    "규칙:\n"
    "- '수집 실패' 항목은 해석하지 말고 실패했다고만 적을 것\n"
    "- 매수/매도 추천 금지. 관찰된 사실과 그 함의만 서술\n"
    "- 지표끼리 신호가 엇갈리면 반드시 그 지점을 지적할 것\n"
    "- 하이일드 HYG/TLT는 1년 백분위 80% 이상이면 위험선호 과열, 20% 이하면 경계로 표현\n"
    "- 스테이블코인 발행량이 느는데 가격이 안 오르면 대기자금 축적, 줄면 이탈로 해석\n"
    + calendar_ctx.RULE + calendar_ctx.STYLE +
    "- 코인베이스 프리미엄은 절대값이 작으므로 부호와 추세만 언급, 과대해석 금지\n"
    "- 티커를 쓸 때는 반드시 한글 설명을 괄호로 병기할 것. 예: HYG(하이일드 회사채), "
    "TLT(장기 국채), TIP(물가연동채), RSP(S&P500 동일가중), SPY(S&P500 시총가중), "
    "SMH(반도체), XLK(기술), IGV(소프트웨어), ITA(방산), ARKX(우주), LIT(배터리), GRID(전력망·인프라), XLU(유틸리티), NVDA(엔비디아), TSM(TSMC), ETN(이튼), PWR(콰나서비스), CEG(콘스텔레이션에너지), XLF(금융), XLV(헬스케어), XLE(에너지), XLI(산업재), XLY(경기소비재), "
    "XLP(필수소비재), XLC(커뮤니케이션), IWM(소형주), BLOK(크립토 관련주)\n"
    "- 핵심만 ==강조할 말== 처럼 등호 두 개로 감싼다. 각 항목에서 꼭 봐야 할 수치나 결론 1~2곳만. "
    "항목별 강조 글자 비율 12%를 넘기지 않는다\n"
    "- 머리말이나 마무리 인사 없이 위 형식만 출력\n\n"
    + json.dumps(brief(payload), ensure_ascii=False)[:45000]
)

def call(model):
    body = json.dumps({"model": model, "max_tokens": 8000,
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
        if res.get("stop_reason") == "max_tokens":
            summary += "\n\n(글자 수 한도로 잘렸습니다)"
        break
    summary = "응답이 비었음. 모델=%s / stop=%s / 블록타입=%s" % (
        res.get("model"), res.get("stop_reason"),
        [b.get("type") for b in res.get("content", []) if isinstance(b, dict)])

payload["summary"] = summary or "분석 결과 없음"
if summary and not summary.startswith(("분석 실패", "응답이 비었음")):   # 실패는 기록하지 않아 다음 실행에서 다시 쓴다
    payload["summary_at"] = now_kst.isoformat(timespec="minutes")

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
