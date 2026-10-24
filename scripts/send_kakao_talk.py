#!/usr/bin/env python3
"""카카오톡 '나에게 보내기'로 다이제스트 메시지를 발송한다.
토큰이 설정되지 않은 경우 에러 없이 건너뛴다(exit 0) - Phase 3 준비 전에도
전체 파이프라인이 끊기지 않도록 하기 위함.

표준 입력으로 받는 내용에 따라 세 가지 모드로 동작한다:

0) 제목 목록 모드 (신규 메일 전체 제목을 번호 매겨 표시, 운영 파이프라인 기본):
   {"header_prefix": "📋 신규메일 20건 · 중요 6건 (10/24 21:00)", "titles": ["⭐제목1", "제목2", ...]}
   text 템플릿 200자 제한에 맞춰 여러 메시지로 자동 분할하고 헤더에 (1/N)을 붙인다.

1) JSON 모드 (건수 + 항목별 제목/요약을 보여주는 list 카드):
   {"header_title": "...", "header_link": "...", "items": [{"title": "...", "description": "...", "link": "..."}]}
   카카오 list 템플릿 제약상 items가 2~3개면 list 카드로, 1개면 자동으로 text로 전송된다
   (list는 최소 2개 필요 - 카카오 API 자체 제약). 4개 이상 넘기면 앞의 3개만 사용된다.
   link가 없는 항목은 기본 메일함 URL로 대체된다.

2) plain text 모드 (기존 방식, 하위 호환용 수동 테스트에 사용):
   echo "메시지" | python send_kakao_talk.py ["<link>"]
   카카오 기본 텍스트 템플릿은 최대 200자 제한이 있다 - 넘으면 자른다.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8-sig")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def update_env(updates):
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    keys_written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                keys_written.add(key)
                continue
        new_lines.append(line)
    for key, value in updates.items():
        if key not in keys_written:
            new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def refresh_access_token(rest_api_key, refresh_token, client_secret=None):
    params = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        params["client_secret"] = client_secret
    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=urllib.parse.urlencode(params).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    updates = {"KAKAO_ACCESS_TOKEN": data["access_token"]}
    if "refresh_token" in data:
        updates["KAKAO_REFRESH_TOKEN"] = data["refresh_token"]
    update_env(updates)
    return data["access_token"]


MAX_TEXT_LEN = 200
MIN_LIST_ITEMS = 2
MAX_LIST_ITEMS = 3
MAX_ITEM_TITLE_LEN = 40
MAX_ITEM_DESC_LEN = 60
MAX_TITLE_LEN = 20
PAGE_SUFFIX_RESERVE = len(" (99/99)")
DEFAULT_LINK = "https://mail.google.com/mail/u/0/#inbox"


def truncate_text(text, max_len=MAX_TEXT_LEN):
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def build_title_pages(header_prefix, titles):
    lines = [f"{i}.{truncate_text(t, MAX_TITLE_LEN)}" for i, t in enumerate(titles, 1)]
    budget = MAX_TEXT_LEN - len(header_prefix) - PAGE_SUFFIX_RESERVE
    chunks, current, used = [], [], 0
    for line in lines:
        cost = len(line) + 1
        if current and used + cost > budget:
            chunks.append(current)
            current, used = [], 0
        current.append(line)
        used += cost
    if current:
        chunks.append(current)

    total = len(chunks)
    pages = []
    for i, chunk in enumerate(chunks, 1):
        header = header_prefix if total == 1 else f"{header_prefix} ({i}/{total})"
        pages.append(header + "\n" + "\n".join(chunk))
    return pages


def _send_template(access_token, template_object):
    req = urllib.request.Request(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        data=urllib.parse.urlencode(
            {"template_object": json.dumps(template_object, ensure_ascii=False)}
        ).encode("utf-8"),
        headers={"Authorization": f"Bearer {access_token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_memo(access_token, text, link_url=""):
    return _send_template(
        access_token,
        {
            "object_type": "text",
            "text": truncate_text(text),
            "link": {"web_url": link_url, "mobile_web_url": link_url},
        },
    )


def send_list(access_token, header_title, items, header_link=""):
    if len(items) < MIN_LIST_ITEMS:
        raise ValueError(
            f"list 템플릿은 항목이 최소 {MIN_LIST_ITEMS}개 필요합니다(카카오 API 제약). "
            f"항목이 1개면 send_memo()를 사용하세요."
        )
    header_link = header_link or (items[0].get("link") if items else "") or DEFAULT_LINK
    kakao_items = []
    for item in items[:MAX_LIST_ITEMS]:
        link_url = item.get("link") or DEFAULT_LINK
        kakao_items.append(
            {
                "title": truncate_text(item.get("title", ""), MAX_ITEM_TITLE_LEN),
                "description": truncate_text(item.get("description", ""), MAX_ITEM_DESC_LEN),
                "link": {"web_url": link_url, "mobile_web_url": link_url},
            }
        )
    return _send_template(
        access_token,
        {
            "object_type": "list",
            "header_title": truncate_text(header_title, MAX_TEXT_LEN),
            "header_link": {"web_url": header_link, "mobile_web_url": header_link},
            "contents": kakao_items,
        },
    )


def main():
    env = load_env()
    rest_api_key = env.get("KAKAO_REST_API_KEY")
    client_secret = env.get("KAKAO_CLIENT_SECRET")
    access_token = env.get("KAKAO_ACCESS_TOKEN")
    refresh_token = env.get("KAKAO_REFRESH_TOKEN")

    if not rest_api_key or not refresh_token:
        print("SKIP: 카카오 REST API 키/리프레시 토큰이 아직 설정되지 않았습니다. "
              "scripts/kakao_oauth_bootstrap.py를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(0)

    raw = sys.stdin.read().strip()
    if not raw:
        print("SKIP: 발송할 내용이 없습니다.", file=sys.stderr)
        sys.exit(0)

    payload = None
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if "items" in parsed or "titles" in parsed:
                payload = parsed
        except json.JSONDecodeError:
            payload = None

    if payload is not None and "titles" in payload:
        pages = build_title_pages(payload.get("header_prefix", "📋 신규 메일"), payload["titles"])
        if not pages:
            print("SKIP: 발송할 제목이 없습니다.", file=sys.stderr)
            sys.exit(0)
        page_link = payload.get("link") or DEFAULT_LINK
        sent = []

        # 토큰 갱신 후 재시도 시 이미 보낸 페이지는 건너뛴다(중복 발송 방지)
        def do_send(token):
            for page in pages[len(sent):]:
                sent.append(send_memo(token, page, page_link))
            return sent
    elif payload is not None and len(payload["items"]) >= MIN_LIST_ITEMS:
        def do_send(token):
            return send_list(token, payload.get("header_title", ""), payload["items"], payload.get("header_link", ""))
    elif payload is not None and len(payload["items"]) == 1:
        # list 템플릿은 최소 2개가 필요하므로(카카오 API 제약), 1건은 text로 전송
        item = payload["items"][0]
        text = f"📬 {item.get('title', '')}\n{item.get('description', '')}"
        link_url = item.get("link", "")

        def do_send(token):
            return send_memo(token, text, link_url)
    elif payload is not None:
        print("SKIP: 발송할 항목이 없습니다.", file=sys.stderr)
        sys.exit(0)
    else:
        link_url = sys.argv[1] if len(sys.argv) > 1 else ""

        def do_send(token):
            return send_memo(token, raw, link_url)

    try:
        result = do_send(access_token)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            access_token = refresh_access_token(rest_api_key, refresh_token, client_secret)
            try:
                result = do_send(access_token)
            except urllib.error.HTTPError as e2:
                body = e2.read().decode("utf-8", errors="replace")
                print(f"ERROR: 발송 실패 (HTTP {e2.code})\n{body}", file=sys.stderr)
                sys.exit(1)
        else:
            body = e.read().decode("utf-8", errors="replace")
            print(f"ERROR: 발송 실패 (HTTP {e.code})\n{body}", file=sys.stderr)
            sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
