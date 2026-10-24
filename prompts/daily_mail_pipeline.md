# 메일 자동 처리 파이프라인 (하루 2회 실행)

이 프롬프트는 `claude -p`로 무인 실행된다. 아래 순서를 그대로 따를 것. 각 단계가 실패해도
다음 단계로 넘어갈 수 있으면 넘어가고(SKIP), 전체를 중단하지 말 것.

작업 디렉터리: `C:\Users\GreatMT\workspace\develope\mail_work`

## 1. 상태 로드
- `state/last_check.json`을 읽어 `gmail_last_checked`, `kakao_mail_last_checked` 확인
- 둘 다 null이면 최근 1일만 조회 대상으로 삼음

## 2. Gmail 수집
- `config/importance_rules.yaml`의 `gmail_exclude_labels`를 제외 조건으로 사용
- `mcp__claude_ai_Gmail__search_threads` 호출
  - query 예: `after:<gmail_last_checked 날짜> -category:promotions -category:social`
  - 날짜는 day 단위만 지원하므로, 반환된 메시지의 정확한 `date`가
    `gmail_last_checked` 시각보다 늦은 것만 이후 단계에서 사용
- 매칭된 각 스레드에 대해 공통 포맷으로 정리:
  `{source: "gmail", id, from: sender, subject, date, body: snippet, link: viewUrl}`

## 3. 카카오메일 수집
- 실행: `python scripts/collect_kakao_mail.py`
- stdout의 JSON 배열을 Gmail 결과와 합쳐 하나의 리스트로 만듦
- `.env`에 `KAKAO_MAIL_APP_PASSWORD`가 비어있어 실패하면 SKIP하고 다음 단계로 진행

## 4. 규칙 기반 1차 필터
- 2+3에서 만든 합친 리스트(JSON)를 `python scripts/classify_mail.py`에 표준입력으로 전달
- 통과한 메일만 다음 단계로

## 5. 최종 중요도 판정 + 요약 (LLM 판단)
- 4를 통과한 메일 중 `source: "gmail"`인 것은 `mcp__claude_ai_Gmail__get_thread`로 전체 본문을 가져와
  `body` 필드를 snippet에서 전체 본문으로 교체 (카카오메일은 이미 전체 본문 수집됨)
- 각 메일의 제목+전체 본문을 보고 직접 판단:
  - `importance`: `important`(즉시 알림 필요) / `hold`(참고용, 알림 불필요) / `ignore`(노이즈)
  - `summary`: 한국어 1~2문장 요약
- 각 메일 객체에 `importance`, `summary` 필드를 추가 (`body`는 전체 본문 그대로 유지 — 7단계에서 노트 원문으로 저장됨)

## 6. 카카오톡 다이제스트 발송
**신규 메일 전체 제목**을 번호 매긴 텍스트로 발송한다. 카카오 텍스트 템플릿은 200자 제한이 있어
스크립트가 자동으로 여러 메시지로 나누고 헤더에 `(1/N)`을 붙인다(제목은 20자에서 잘림).
(list 카드는 카카오 API 제약상 최대 3건만 보여줄 수 있어 전체 목록용으로 쓰지 않음)

- 대상: 2+3단계에서 수집한 메일 **전체**(4단계 필터 통과 여부와 무관). 0건이면 발송하지 않음
- 순서: `important`(제목 앞에 `⭐`) → `hold` → 나머지(ignore 및 필터 미통과)
- 제목에는 메일 제목(subject)만 넣음(출처 태그는 글자 수 때문에 생략)
- JSON을 표준입력으로 전달:
  ```json
  {
    "header_prefix": "📋 신규메일 <전체건수>건 · 중요 <important건수>건 (MM/DD HH:mm)",
    "titles": ["⭐중요메일제목", "참고메일제목", "기타메일제목"]
  }
  ```
  실행: `echo '<위 JSON>' | python scripts/send_kakao_talk.py`
- 토큰 미설정/만료로 SKIP 또는 ERROR가 나오면 정상 — 다음 단계로 진행

## 7. 대시보드 로그 기록
- `importance`가 `important` 또는 `hold`인 메일 전체를 JSON으로 만들어
  `python scripts/log_mail_note.py`에 표준입력으로 전달
- Obsidian `Areas/Mail_Log/`에 frontmatter 노트 생성됨

## 8. LLM_wiki 장기 보관
- `importance: important`이면서 재참조 가치가 있다고 판단되는 메일(계약/의사결정/지속 프로젝트 관련)만
  `wiki-ingest` 스킬로 LLM_wiki 영구 노트 생성
- 단순 알림성 메일은 7단계 로그만 남기고 위키에는 적재하지 않음

## 9. 상태 저장
- `state/last_check.json`의 `gmail_last_checked`를 이번 실행 시작 시각(UTC ISO)으로 갱신
- (`kakao_mail_last_checked`는 `collect_kakao_mail.py`가 자동 갱신함)

## 10. 실행 로그
- 각 단계 결과(수집 건수, 분류 건수, 발송 여부, 생성된 노트 경로)를
  `logs/YYYY-MM-DD.log`에 한 줄씩 append
