"""AI 요약에 넘길 '오늘 날짜 + 연준(FOMC) 일정' 사실 정보

AI가 뉴스 제목만 보고 '금리결정을 앞두고' 같은 시점을 지어내지 않도록
실제 일정을 함께 준다. 결정 발표일(회의 둘째 날) 기준.
출처: federalreserve.gov FOMC 캘린더. 매년 말 다음 해 일정을 추가할 것.
"""
import datetime

FOMC_DECISIONS = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def macro_context(today):
    """today: date -> 한국어 한 문단"""
    ds = [datetime.date.fromisoformat(d) for d in FOMC_DECISIONS]
    past = [d for d in ds if d <= today]
    nxt = [d for d in ds if d > today]
    s = "오늘은 %s이다. " % today.isoformat()
    if past:
        s += "직전 FOMC 금리결정: %s (%d일 전). " % (past[-1], (today - past[-1]).days)
    s += ("다음 FOMC 금리결정: %s (%d일 후)." % (nxt[0], (nxt[0] - today).days)
          if nxt else "다음 FOMC 일정: 미확인.")
    return s


RULE = ("- 시점·일정 표현은 위 날짜 정보와 제공된 뉴스 제목에 명시된 것만 쓸 것. "
        "FOMC를 '앞두고'라는 표현은 다음 FOMC가 7일 이내일 때만 허용. "
        "뉴스의 '금리' 언급을 연준 회의 임박으로 확대 해석하지 말 것\n")
