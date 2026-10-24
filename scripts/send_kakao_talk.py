#!/usr/bin/env python3
"""카카오톡 '나에게 보내기'로 다이제스트 메시지를 발송한다.
토큰이 설정되지 않은 경우 에러 없이 건너뛴다(exit 0) - Phase 3 준비 전에도
전체 파이프라인이 끊기지 않도록 하기 위함.

표준 입력으로 다이제스트 텍스트(plain text)를 받는다.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
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


def refresh_access_token(rest_api_key, refresh_token):
    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "client_id": rest_api_key,
                "refresh_token": refresh_token,
            }
        ).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    updates = {"KAKAO_ACCESS_TOKEN": data["access_token"]}
    if "refresh_token" in data:
        updates["KAKAO_REFRESH_TOKEN"] = data["refresh_token"]
    update_env(updates)
    return data["access_token"]


def send_memo(access_token, text):
    template_object = json.dumps(
        {
            "object_type": "text",
            "text": text[:200],
            "link": {"web_url": "", "mobile_web_url": ""},
        },
        ensure_ascii=False,
    )
    req = urllib.request.Request(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        data=urllib.parse.urlencode({"template_object": template_object}).encode("utf-8"),
        headers={"Authorization": f"Bearer {access_token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    env = load_env()
    rest_api_key = env.get("KAKAO_REST_API_KEY")
    access_token = env.get("KAKAO_ACCESS_TOKEN")
    refresh_token = env.get("KAKAO_REFRESH_TOKEN")

    if not rest_api_key or not refresh_token:
        print("SKIP: 카카오 REST API 키/리프레시 토큰이 아직 설정되지 않았습니다. "
              "scripts/kakao_oauth_bootstrap.py를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(0)

    text = sys.stdin.read().strip()
    if not text:
        print("SKIP: 발송할 내용이 없습니다.", file=sys.stderr)
        sys.exit(0)

    try:
        result = send_memo(access_token, text)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            access_token = refresh_access_token(rest_api_key, refresh_token)
            try:
                result = send_memo(access_token, text)
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
