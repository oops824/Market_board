"""야후 일봉 응답 보정

미국장 마감 몇 시간 뒤(한국 오전)에도 야후 일봉의 마지막 날 종가가 비어 있거나 전날 값으로 남아 있는 경우가 있다.
마지막 봉과 정규장 마지막 거래(meta.regularMarketTime)가 거래소 현지 기준 같은 날이면
그 봉의 종가를 meta.regularMarketPrice 로 채운다(고가·저가도 그 가격을 넘지 않게 맞춤).
"""
import datetime


def fix_last(r):
    """r: chart.result[0]. 고친 r 을 그대로 돌려준다"""
    try:
        m, ts = r.get("meta") or {}, r.get("timestamp") or []
        q = r["indicators"]["quote"][0]
        px, t, off = m.get("regularMarketPrice"), m.get("regularMarketTime"), m.get("gmtoffset") or 0
        if not (px and t and ts and q.get("close")):
            return r
        day = lambda x: datetime.datetime.utcfromtimestamp(x + off).date()
        if day(ts[-1]) != day(t):
            return r
        q["close"][-1] = px
        for k, f in (("high", max), ("low", min)):
            if q.get(k):
                q[k][-1] = px if q[k][-1] is None else f(q[k][-1], px)
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return r
