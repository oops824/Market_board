"""영문 기사 본문 -> 한국어 번역 요약 (+ 원문 주소 복원)

뉴스 항목(dict: title, url, lang ...)에 다음을 채운다.
  real : 원문 기사 주소 (구글 뉴스 리다이렉트 주소를 풀어낸 것)
  ko   : {"sum": 한국어 번역 요약 4~6문장, "quotes": [직접 인용 번역, ...]}
전문은 저작권 문제로 저장하지 않는다. 화면에서 구글 번역 페이지 링크로 연결한다.

결과는 cache_path 에 기사 주소별로 저장해 같은 기사를 다시 처리하지 않는다.
의존성: requests, trafilatura (없으면 조용히 건너뜀)
"""
import base64, datetime, json, os, re, time, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
KEEP_DAYS = 21          # 캐시 보관 기간
RETRY_FAIL_H = 24       # 실패한 기사는 이 시간 뒤에 다시 시도
MIN_BODY = 600          # 이보다 짧으면 본문 추출 실패(유료벽 등)로 본다
BATCH = 5               # AI 한 번에 보낼 기사 수
MAX_NEW = 60            # 한 번 실행에서 새로 처리할 최대 기사 수
VERSION = 2             # 번역 규칙을 바꾸면 올린다 → 이전 번역은 다시 처리


def _session():
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


# ---------- 구글 뉴스 리다이렉트 -> 원문 주소 ----------
def decode_gnews(S, url):
    if "news.google.com" not in url:
        return url
    m = re.search(r"/articles/([^?/]+)", url)
    if not m:
        return None
    aid = m.group(1)
    # 예전 형식: id 를 base64 로 풀면 주소가 그대로 들어 있음
    try:
        raw = base64.urlsafe_b64decode(aid + "=" * (-len(aid) % 4))
        mm = re.search(rb"https?://[\x21-\x7e]+", raw)
        if mm and b"AU_yqL" not in raw[:12]:
            return mm.group(0).decode()
    except Exception:
        pass
    # 새 형식: 기사 페이지의 서명·시각으로 batchexecute 호출
    sg = ts = None
    for base in ("https://news.google.com/articles/", "https://news.google.com/rss/articles/"):
        try:
            page = S.get(base + aid, timeout=15).text
        except Exception:
            continue
        a = re.search(r'data-n-a-sg="([^"]+)"', page)
        b = re.search(r'data-n-a-ts="([^"]+)"', page)
        if a and b:
            sg, ts = a.group(1), b.group(1)
            break
    if not sg:
        return None
    req = ["Fbv4je",
           '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,'
           'null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]' % (aid, ts, sg)]
    r = S.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
               data="f.req=" + urllib.parse.quote(json.dumps([[req]])),
               headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8"},
               timeout=15)
    body = json.loads(r.text.split("\n\n")[1])[:-2]
    real = json.loads(body[0][2])[1]
    return real if str(real).startswith("http") else None


# ---------- 본문 추출 ----------
def fetch_body(S, url):
    import trafilatura
    r = S.get(url, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError("HTTP %d" % r.status_code)
    txt = trafilatura.extract(r.text, include_comments=False, include_tables=False,
                              favor_precision=True) or ""
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


# ---------- AI 번역 요약 ----------
def translate_batch(batch):
    """batch: [(id, title, body)] -> {id: {"sum", "quotes"}}"""
    import crypto as C
    arts = [{"id": i, "title": t, "body": b[:5000]} for i, t, b in batch]
    prompt = (
        "다음 영문 기사 본문들을 한국어 독자가 읽을 수 있도록 옮겨라.\n"
        "기사마다:\n"
        "- sum: 기사 핵심 내용을 자연스러운 한국어 4~6문장으로 번역·요약 "
        "(누가, 무엇을, 왜, 수치 포함)\n"
        "- quotes: 기사 속 인물의 직접 인용이 있으면 가장 중요한 1~2개를 한국어로 번역 "
        "(\"발언\" — 발언자 형식). 없으면 빈 배열\n"
        "규칙:\n"
        "- 본문에 없는 내용·해석을 더하지 말 것\n"
        "- 금액·수치는 원문 표기 그대로 쓸 것 (예: $2.4B, $87,300, 12%). "
        "억·조 같은 한국식 단위로 환산하지 말 것\n"
        "- quotes 는 반드시 한국어로 번역할 것. 영어 원문을 그대로 두지 말 것\n"
        "- 인명·기관명·티커는 원문 표기 유지 가능\n"
        "출력은 다른 말 없이 JSON 하나: {\"기사id\": {\"sum\": \"...\", \"quotes\": [\"...\"]}, ...}\n\n"
        + json.dumps(arts, ensure_ascii=False))
    out = C.claude_json(prompt, 6000)
    return out if isinstance(out, dict) else {}


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def enrich(items, cache_path):
    """영문 기사(lang == 'en')에 real/ko 를 채운다. 반환: 새로 처리한 수"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[기사 번역] API 키 없음 — 건너뜀")
        return 0
    try:
        S = _session()
        import trafilatura  # noqa: F401
    except ImportError as e:
        print("[기사 번역] 의존성 없음 — 건너뜀:", e)
        return 0
    now = datetime.datetime.now(datetime.timezone.utc)
    cache = _load(cache_path)
    todo, seen = [], set()
    for n in items:
        if n.get("lang") != "en" or n["url"] in seen:
            continue
        seen.add(n["url"])
        c = cache.get(n["url"])
        if c:
            if c.get("status") == "ok":
                if c.get("v") == VERSION:
                    continue                  # 현재 규칙으로 번역 완료
            elif now - datetime.datetime.fromisoformat(c["t"]) < \
                    datetime.timedelta(hours=RETRY_FAIL_H):
                continue                      # 최근 실패 — 나중에 재시도
        todo.append(n)
    todo = todo[:MAX_NEW]
    print("[기사 번역] 새 기사 %d건 처리" % len(todo))

    ready = []
    for n in todo:
        key, rec = n["url"], {"t": now.isoformat()}
        try:
            real = decode_gnews(S, key)
            if real:
                rec["real"] = real
            body = fetch_body(S, real) if real else ""
            if len(body) >= MIN_BODY:
                ready.append((key, n.get("orig") or n["title"], body))
                rec["status"] = "pending"
            else:
                rec["status"] = "nobody"      # 유료벽·차단 등 — 번역 링크만 제공
        except Exception as e:
            rec["status"] = "fail"
            print("  ! %s: %s" % (key[:60], str(e)[:80]))
        cache[key] = rec
        time.sleep(0.4)

    for i in range(0, len(ready), BATCH):
        part = ready[i:i + BATCH]
        ids = {"a%d" % j: key for j, (key, _t, _b) in enumerate(part)}
        res = translate_batch([(aid, t, b) for aid, (key, t, b) in zip(ids, part)])
        for aid, key in ids.items():
            r = res.get(aid) or {}
            if r.get("sum"):
                # 번역되지 않은(한글 없는) 인용은 버린다
                qs = [str(q).strip() for q in (r.get("quotes") or [])
                      if re.search(r"[가-힣]", str(q))][:2]
                cache[key].update({"status": "ok", "v": VERSION,
                                   "sum": str(r["sum"]).strip(), "quotes": qs})
            else:
                cache[key]["status"] = "fail"

    # 오래된 항목 정리 후 저장
    cut = now - datetime.timedelta(days=KEEP_DAYS)
    cache = {k: v for k, v in cache.items() if datetime.datetime.fromisoformat(v["t"]) >= cut}
    d = os.path.dirname(cache_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    # 뉴스 항목에 반영
    for n in items:
        c = cache.get(n.get("url"))
        if not c:
            continue
        if c.get("real"):
            n["real"] = c["real"]
        if c.get("status") == "ok":
            n["ko"] = {"sum": c["sum"], "quotes": c.get("quotes", [])}
    ok = sum(1 for v in cache.values() if v.get("status") == "ok")
    print("[기사 번역] 캐시 %d건 (번역 완료 %d)" % (len(cache), ok))
    return len(todo)
