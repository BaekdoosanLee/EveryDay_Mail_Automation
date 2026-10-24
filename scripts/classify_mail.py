#!/usr/bin/env python3
"""표준 메일 문서를 받아 VIP/키워드 규칙에 걸리는 것만 통과시킨다.

이 단계는 1차 필터일 뿐이며, 최종 중요도(important/hold/ignore)와
요약은 이 스크립트를 실행하는 에이전트(LLM)가 통과된 메일을 보고 결정한다.
"""
import json
import sys
from pathlib import Path

import yaml

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "config" / "importance_rules.yaml"


def load_rules():
    rules = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    return {
        "vip_senders": [s.lower() for s in (rules.get("vip_senders") or [])],
        "keywords": [k.lower() for k in (rules.get("keywords") or [])],
    }


def matches(mail, rules):
    sender = (mail.get("from") or "").lower()
    subject = (mail.get("subject") or "").lower()
    body = (mail.get("body") or mail.get("snippet") or "").lower()

    if any(vip in sender for vip in rules["vip_senders"]):
        return True, "vip_sender"
    for kw in rules["keywords"]:
        if kw in subject or kw in body:
            return True, f"keyword:{kw}"
    return False, None


def read_input():
    if "--input" in sys.argv:
        return Path(sys.argv[sys.argv.index("--input") + 1]).read_text(encoding="utf-8-sig")
    return sys.stdin.read()


def main():
    raw = read_input()
    mails = json.loads(raw) if raw.strip() else []
    rules = load_rules()

    matched = []
    for mail in mails:
        hit, reason = matches(mail, rules)
        if hit:
            mail["match_reason"] = reason
            matched.append(mail)

    print(json.dumps(matched, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
