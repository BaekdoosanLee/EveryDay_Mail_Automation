# 메일 자동화 파이프라인 사용 설명서

Gmail / 카카오메일을 하루 2회 자동으로 확인해서, 중요한 메일은 카카오톡으로 알려주고, Obsidian 대시보드와 위키에 기록을 남기는 시스템입니다.

---

## 1. 전체 동작 개요

```
[Windows 작업 스케줄러: 07:00 / 17:00]
        │
        ▼
scripts\run_pipeline.ps1  실행
        │
        ▼
claude -p "prompts\daily_mail_pipeline.md 지시 내용"
        │
        ├─ Gmail 조회 (Gmail MCP)
        ├─ 카카오메일 조회 (scripts\collect_kakao_mail.py)
        ├─ 규칙 필터 (scripts\classify_mail.py)
        ├─ 최종 중요도 판단 + 요약 (Claude가 직접 판단)
        ├─ 중요 메일 → 카카오톡 "나에게 보내기" 발송 (scripts\send_kakao_talk.py)
        ├─ 중요/보류 메일 → Obsidian Mail_Log 노트 생성 (scripts\log_mail_note.py)
        └─ 장기 보관 가치 있는 메일 → LLM_wiki 영구 노트 생성 (wiki-ingest 스킬)
        │
        ▼
실행 종료 후 5분간 PC 사용 없으면 자동 절전 모드 복귀
```

---

## 2. 평소에 확인할 것

### 카카오톡
중요하다고 판단된 메일은 **카카오톡 "나에게 보내기"** 채팅방으로 다이제스트 형태 알림이 옵니다. 하루 최대 2번(07:00, 17:00 실행 시점) 옵니다.

### Obsidian 대시보드
볼트(`C:\Users\GreatMT\workspace\LLM_Wiki`)에서 **`Mail_Dashboard.base`** 파일을 엽니다.

| 탭 | 내용 |
|---|---|
| 전체 | 수집된 모든 메일 로그 |
| 중요 메일 | `importance: important`로 분류된 것만 |
| 미확인 | `status: unread`인 것만 |

메일을 확인했으면 해당 노트(`0_Inbox\Mail_Log\*.md`)를 열어 frontmatter의 `status`를 `"unread"` → `"read"`로 직접 바꿔주세요. **자동으로 바뀌지 않는 수동 관리 포인트**입니다.

### LLM_wiki 영구 노트
계약/의사결정처럼 두고두고 참고할 가치가 있다고 판단된 메일만 별도로 LLM_wiki 본문 위치에 지식 노트로 생성됩니다. 단순 알림성 메일은 여기엔 안 쌓이고 `Mail_Log`에만 남습니다.

---

## 3. 설정 파일

### `config\importance_rules.yaml`
중요 메일을 판별하는 1차 필터 규칙입니다.

```yaml
vip_senders:
  - "bdslee72@gmail.com"
  - "sanduslee@kakao.com"

keywords:
  - "긴급"
  - "마감"
  - "계약"
  - "결제"
  - "송금"
  - "승인"

gmail_exclude_labels:
  - "CATEGORY_PROMOTIONS"
  - "CATEGORY_SOCIAL"
```

- `vip_senders`: 발신자 주소/이름에 이 문자열이 **포함**되면 무조건 중요 후보로 통과 (부분 일치, 대소문자 무시)
- `keywords`: 제목/본문에 이 단어가 있으면 중요 후보로 통과
- `gmail_exclude_labels`: Gmail에서 애초에 조회 대상에서 제외할 카테고리

**주의**: YAML 리스트 항목은 반드시 `- "값"` 형식으로 작성해야 합니다. `-` 없이 쓰면 리스트가 아니라 문자열 하나로 합쳐져서 오작동합니다.

규칙을 통과한 메일도 최종 중요도(important/hold/ignore)는 Claude가 내용을 보고 다시 판단하므로, 이 파일은 "1차로 거를 후보"만 정하는 느슨한 필터입니다.

### `.env`
민감한 자격증명을 담는 파일입니다. **절대 외부에 공유하거나 커밋하지 마세요** (`.gitignore`에 이미 제외 처리되어 있음).

| 항목 | 설명 |
|---|---|
| `KAKAO_MAIL_ADDRESS` | 카카오메일 주소 |
| `KAKAO_MAIL_APP_PASSWORD` | 카카오메일 **앱 비밀번호** (일반 로그인 비밀번호 아님 — 2단계 인증 활성화 후 별도 발급) |
| `KAKAO_REST_API_KEY` | Kakao Developers 앱의 REST API 키 |
| `KAKAO_CLIENT_SECRET` | 앱 보안 설정에서 Client Secret을 켠 경우에만 필요 |
| `KAKAO_ACCESS_TOKEN` / `KAKAO_REFRESH_TOKEN` | 인증 스크립트가 자동으로 채워줌 (직접 입력 안 함) |
| `OBSIDIAN_VAULT_PATH` | LLM_wiki 볼트 경로 |

---

## 4. 스케줄 관리

### 실행 시간 확인
```powershell
Get-ScheduledTask -TaskName "MailAutomationPipeline"
schtasks /Query /TN "MailAutomationPipeline" /V /FO LIST
```

### 일시 중지 / 재개
```powershell
Disable-ScheduledTask -TaskName "MailAutomationPipeline"
Enable-ScheduledTask -TaskName "MailAutomationPipeline"
```

### 완전 삭제
```powershell
Unregister-ScheduledTask -TaskName "MailAutomationPipeline"
```

### 수동으로 지금 바로 실행해보기
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\GreatMT\workspace\develope\mail_work\scripts\run_pipeline.ps1"
```

### 절전모드 관련
- 작업에 `WakeToRun` 옵션이 설정되어 있어, PC가 **절전(잠자기)** 상태면 07:00/17:00에 자동으로 깨어나 실행합니다.
- **완전히 전원이 꺼진 상태**에서는 깨어나지 않습니다. 이 경우 다음에 PC를 켜면 놓친 실행을 한 번 뒤늦게 수행합니다 (`StartWhenAvailable` 옵션).
- 파이프라인 실행이 끝난 뒤 5분간 키보드/마우스 입력이 없으면 자동으로 다시 절전모드에 들어갑니다. 그 사이 PC를 사용 중이면 절전에 들어가지 않습니다.

---

## 5. 문제가 생겼을 때

### 어디서 로그를 보나
`logs\YYYY-MM-DD.log` — 그날 실행된 전체 과정과 에러가 기록됩니다.

### 카카오톡이 안 와요
1. 로그에서 `SKIP` 메시지 확인 — 토큰 미설정/만료 시 발송 단계만 건너뛰고 나머지는 정상 진행됩니다
2. **Refresh Token은 약 2개월 뒤 만료**됩니다. 만료되면 재인증 필요:
   ```powershell
   python scripts\kakao_oauth_bootstrap.py
   ```
   브라우저로 로그인 URL을 열고, 리다이렉트된 `localhost:5000/oauth?code=...` 주소에서 `code=` 뒤 값을 복사해 터미널에 입력하면 토큰이 `.env`에 자동 갱신됩니다.

### 카카오메일 수집이 안 돼요 (`LOGIN failed`)
- 카카오메일 환경설정 → POP3/IMAP/SMTP 설정에서 "사용함"으로 되어 있는지 확인
- `KAKAO_MAIL_APP_PASSWORD`가 일반 로그인 비밀번호가 아니라 **앱 비밀번호**(2단계 인증 활성화 후 별도 생성)인지 확인

### 중요한 메일을 놓쳤어요 / 너무 많이 옵니다
`config\importance_rules.yaml`의 `vip_senders`, `keywords`를 조정하세요. 너무 넓게 잡으면(예: 흔한 도메인 전체) 노이즈가 늘어납니다.

### 수동으로 개별 단계 테스트
```powershell
# 카카오메일만 수집
python scripts\collect_kakao_mail.py

# 규칙 필터만 테스트 (표준입력으로 JSON 전달)
Get-Content kakao_test.json | python scripts\classify_mail.py

# 카카오톡 발송만 테스트
"테스트 메시지" | python scripts\send_kakao_talk.py
```

---

## 6. 파일 구조

```
mail_work\
├── .env                          # 자격증명 (비공개)
├── .env.example                  # 자격증명 양식
├── .claude\settings.json         # 무인 실행용 권한 허용 목록
├── config\importance_rules.yaml  # 중요 메일 판별 규칙
├── state\last_check.json         # 마지막 메일 체크 시각 (자동 갱신)
├── logs\YYYY-MM-DD.log           # 일별 실행 로그
├── prompts\daily_mail_pipeline.md # 전체 파이프라인 실행 지시문
└── scripts\
    ├── collect_kakao_mail.py      # 카카오메일 IMAP 수집
    ├── classify_mail.py           # 규칙 기반 1차 필터
    ├── log_mail_note.py           # Obsidian 로그 노트 생성
    ├── send_kakao_talk.py         # 카카오톡 발송
    ├── kakao_oauth_bootstrap.py   # 카카오 최초/재인증 (수동 실행 전용)
    └── run_pipeline.ps1           # 전체 실행 + 절전 복귀 로직
```

관련 Obsidian 파일: `LLM_Wiki\Mail_Dashboard.base`, `LLM_Wiki\0_Inbox\Mail_Log\*.md`
