#!/usr/bin/env python3
import imaplib
import email
import email.utils
from email.header import decode_header
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "last_check.json"
ENV_PATH = ROOT / ".env"


def load_env():
    if not ENV_PATH.exists():
        print(f"ERROR: {ENV_PATH} not found. .env.example을 복사해 값을 채워주세요.", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def decode_mime_words(s):
    if not s:
        return ""
    decoded = ""
    for text, enc in decode_header(s):
        if isinstance(text, bytes):
            decoded += text.decode(enc or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="replace") if payload else ""
        for part in msg.walk():
            if part.get_content_type() == "text/html" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="replace") if payload else ""
        return ""
    charset = msg.get_content_charset() or "utf-8"
    payload = msg.get_payload(decode=True)
    return payload.decode(charset, errors="replace") if payload else ""


def fetch_since(address, app_password, since_dt):
    imap = imaplib.IMAP4_SSL("imap.kakao.com", 993)
    imap.login(address, app_password)
    imap.select("INBOX")

    since_str = since_dt.strftime("%d-%b-%Y") if since_dt else "01-Jan-2000"
    status, data = imap.search(None, f'(SINCE "{since_str}")')
    if status != "OK":
        imap.logout()
        raise RuntimeError("IMAP search failed")

    results = []
    for num in data[0].split():
        status, msg_data = imap.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        received = email.utils.parsedate_to_datetime(msg.get("Date"))
        if since_dt and received and received <= since_dt:
            continue
        results.append({
            "source": "kakao_mail",
            "id": msg.get("Message-ID", ""),
            "from": decode_mime_words(msg.get("From", "")),
            "subject": decode_mime_words(msg.get("Subject", "")),
            "date": received.isoformat() if received else None,
            "body": get_body(msg)[:5000],
        })

    imap.logout()
    return results


def main():
    env = load_env()
    address = env.get("KAKAO_MAIL_ADDRESS")
    app_password = env.get("KAKAO_MAIL_APP_PASSWORD")
    if not address or not app_password:
        print("ERROR: .env에 KAKAO_MAIL_ADDRESS / KAKAO_MAIL_APP_PASSWORD를 설정하세요.", file=sys.stderr)
        sys.exit(1)

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    last_checked = state.get("kakao_mail_last_checked")
    since_dt = datetime.fromisoformat(last_checked) if last_checked else None

    mails = fetch_since(address, app_password, since_dt)

    state["kakao_mail_last_checked"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(mails, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
