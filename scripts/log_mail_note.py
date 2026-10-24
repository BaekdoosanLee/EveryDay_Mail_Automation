#!/usr/bin/env python3
"""분류된 메일을 Obsidian 볼트의 Mail_Log 폴더에 frontmatter 노트로 기록한다.
대시보드(Base)는 이 폴더를 쿼리해서 구성한다.
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    env_path = ROOT / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def slugify(text, max_len=40):
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"[\s]+", "-", text)
    return text[:max_len] if text else "untitled"


def yaml_escape(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def make_preview(text, max_len=80):
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[:max_len].rstrip() + "..."


def write_note(mail, vault_path):
    log_dir = Path(vault_path) / "Areas" / "Mail_Log"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = (mail.get("date") or datetime.now().isoformat())[:10]
    slug = slugify(mail.get("subject") or "untitled")
    hash_key = mail.get("source", "") + "|" + (mail.get("id") or mail.get("subject") or "")
    short_hash = hashlib.sha1(hash_key.encode("utf-8")).hexdigest()[:6]
    filename = f"{date_str}_{slug}_{short_hash}.md"
    note_path = log_dir / filename

    if note_path.exists():
        return note_path, False

    summary = mail.get("summary") or ""
    body = mail.get("body") or mail.get("snippet") or ""

    frontmatter = {
        "type": "mail-log",
        "source": mail.get("source", ""),
        "from": mail.get("from", ""),
        "subject": mail.get("subject", ""),
        "date": mail.get("date", ""),
        "importance": mail.get("importance", "hold"),
        "status": "unread",
        "link": mail.get("link", ""),
        "preview": make_preview(summary or body),
    }

    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f'{key}: "{yaml_escape(value)}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# {mail.get('subject', '(제목 없음)')}")
    lines.append("")
    if summary:
        lines.append("## 요약")
        lines.append(summary)
        lines.append("")
    lines.append("## 원문")
    lines.append(body[:3000] if body else "(원문 없음)")

    note_path.write_text("\n".join(lines), encoding="utf-8")
    return note_path, True


def read_input():
    if "--input" in sys.argv:
        return Path(sys.argv[sys.argv.index("--input") + 1]).read_text(encoding="utf-8-sig")
    return sys.stdin.read()


def main():
    env = load_env()
    vault_path = env.get("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        print("ERROR: .env에 OBSIDIAN_VAULT_PATH를 설정하세요.", file=sys.stderr)
        sys.exit(1)

    raw = read_input()
    mails = json.loads(raw) if raw.strip() else []

    written = []
    for mail in mails:
        path, created = write_note(mail, vault_path)
        written.append({"path": str(path), "created": created})

    print(json.dumps(written, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
