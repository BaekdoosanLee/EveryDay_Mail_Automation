#!/usr/bin/env python3
"""카카오톡 '나에게 보내기' 최초 1회 인증용 스크립트.

사용법:
  1. Kakao Developers(https://developers.kakao.com)에서 앱 생성
     - 플랫폼: Web, 사이트 도메인: http://localhost:5000 (임의 값으로 충분)
     - 카카오 로그인 활성화, Redirect URI: http://localhost:5000/oauth
     - 동의항목에서 "카카오톡 메시지 전송(talk_message)" 활성화
     - .env의 KAKAO_REST_API_KEY에 "REST API 키" 입력
  2. 아래 명령 실행:
     python scripts/kakao_oauth_bootstrap.py
  3. 출력된 URL을 브라우저에서 열고 로그인/동의 후,
     리다이렉트된 주소의 "code=..." 부분 값을 복사해 터미널에 입력
  4. 발급된 access_token / refresh_token이 .env에 자동 저장됨
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
REDIRECT_URI = "http://localhost:5000/oauth"


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


def main():
    env = load_env()
    rest_api_key = env.get("KAKAO_REST_API_KEY")
    if not rest_api_key:
        print("ERROR: .env에 KAKAO_REST_API_KEY를 먼저 설정하세요.", file=sys.stderr)
        sys.exit(1)

    auth_url = (
        "https://kauth.kakao.com/oauth/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": rest_api_key,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": "talk_message",
            }
        )
    )
    print("1) 아래 URL을 브라우저에서 열어 로그인/동의하세요:\n")
    print(auth_url)
    print("\n2) 리다이렉트된 주소(http://localhost:5000/oauth?code=...)에서 code 값만 복사해 입력하세요.")
    code = input("\ncode: ").strip()
    if not code:
        print("code가 비어있습니다. 종료합니다.", file=sys.stderr)
        sys.exit(1)

    client_secret = env.get("KAKAO_CLIENT_SECRET")
    token_params = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    if client_secret:
        token_params["client_secret"] = client_secret

    token_req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=urllib.parse.urlencode(token_params).encode("utf-8"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_req) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: 토큰 요청 실패 (HTTP {e.code})\n{body}", file=sys.stderr)
        sys.exit(1)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token or not refresh_token:
        print(f"ERROR: 토큰 발급 실패: {token_data}", file=sys.stderr)
        sys.exit(1)

    update_env({"KAKAO_ACCESS_TOKEN": access_token, "KAKAO_REFRESH_TOKEN": refresh_token})
    print("\n저장 완료: KAKAO_ACCESS_TOKEN / KAKAO_REFRESH_TOKEN이 .env에 기록되었습니다.")


if __name__ == "__main__":
    main()
