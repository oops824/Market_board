"""가격 시계열 -> 핵심 신호 키워드 (코인·주식 공용)

반환: [{"t": 라벨, "c": up|dn|warn|na, "p": 우선순위(클수록 중요)}]
c: up=상승 신호, dn=하락 신호, warn=과열·주의, na=중립 정보
"""


def ema(xs, n):
    k, out = 2 / (n + 1), []
    for x in xs:
        out.append(x if not out else out[-1] + k * (x - out[-1]))
    return out


def rsi(xs, n=14):
    if len(xs) <= n:
        return None
    gains = [max(xs[i] - xs[i - 1], 0) for i in range(1, len(xs))]
    losses = [max(xs[i - 1] - xs[i], 0) for i in range(1, len(xs))]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):  # 와일더 평활
        ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def tag(t, c, p):
    return {"t": t, "c": c, "p": p}


def price_signals(closes, highs=None, lows=None, vols=None):
    """일봉 종가(과거->최신) 기반 기술적 신호"""
    c = [x for x in closes if x is not None]
    out = []
    if len(c) < 30:
        return out
    last = c[-1]
    e20, e50 = ema(c, 20), ema(c, 50)
    long_ok = len(c) >= 55
    # 추세
    if long_ok and last > e20[-1] > e50[-1] and e20[-1] > e20[-5]:
        out.append(tag("추세 상승", "up", 5))
    elif long_ok and last < e20[-1] < e50[-1] and e20[-1] < e20[-5]:
        out.append(tag("추세 하락", "dn", 5))
    # 이동평균 교차 (최근 5봉 이내)
    if long_ok:
        for i in range(1, 6):
            before = e20[-i - 1] - e50[-i - 1]
            after = e20[-i] - e50[-i]
            if before <= 0 < after:
                out.append(tag("골든크로스", "up", 8))
                break
            if before >= 0 > after:
                out.append(tag("데드크로스", "dn", 8))
                break
    # RSI
    r = rsi(c)
    if r is not None:
        if r >= 70:
            out.append(tag("RSI 과매수 %d" % r, "warn", 7))
        elif r <= 30:
            out.append(tag("RSI 과매도 %d" % r, "warn", 7))
    # MACD 히스토그램 부호 전환 (최근 3봉 이내)
    macd = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    hist = [m - s for m, s in zip(macd, ema(macd, 9))]
    for i in range(1, 4):
        if hist[-i - 1] <= 0 < hist[-i]:
            out.append(tag("모멘텀 상승 전환", "up", 6))
            break
        if hist[-i - 1] >= 0 > hist[-i]:
            out.append(tag("모멘텀 약화", "dn", 6))
            break
    # 20일 신고가·신저가
    hs = [h for h in (highs or c) if h is not None]
    ls = [l for l in (lows or c) if l is not None]
    if len(hs) > 21 and last >= max(hs[-21:-1]):
        out.append(tag("20일 신고가", "up", 7))
    elif len(ls) > 21 and last <= min(ls[-21:-1]):
        out.append(tag("20일 신저가", "dn", 7))
    # 거래량 급증
    v = [x for x in (vols or []) if x]
    if len(v) > 21:
        avg = sum(v[-21:-1]) / 20
        if avg and v[-1] >= 2 * avg:
            out.append(tag("거래량 급증 %.1f배" % (v[-1] / avg), "warn", 7))
    return out


def top(tags, n=3):
    return sorted(tags, key=lambda x: -x["p"])[:n]
