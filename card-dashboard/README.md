# 통신·렌탈 할인카드 비교

`card_benefit2`(long-format) → 카드당 1행 비교표로 보여주는 뷰어.

- **대시보드(React):** 자동수집된 카드만 표시. 25개월후·혜택기간 컬럼 없음(데이터로 못 채우는 칸).
- **구글시트(Apps Script):** 같은 컬럼 + 미수집 카드도 공란 행으로 표시. 준실시간 새로고침.
- **스크래퍼 repo(key)와는 별도 repo + 별도 Vercel.** Supabase는 같은 프로젝트의 `card_benefit2`를 anon 키로 읽기만.

## 파일 구조
```
.
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── .env.example
├── .gitignore
├── Code.gs            ← 구글시트용(레포 아님, Apps Script에 붙여넣기)
└── src
    ├── main.jsx
    ├── index.css
    └── App.jsx
```
GitHub 웹 업로드 시 `main.jsx / index.css / App.jsx`는 `src/` 폴더 안에. `Code.gs`는 repo에 같이 둬도 되고 안 둬도 됨(빌드와 무관).

## 컬럼 (통신/렌탈 공통)
통신사·가맹점 | 카드사 | 카드명 | 연회비 | 전월실적(최소) | 기존회원(기본할인) | 신규회원(프로모션) | 전월실적(최대) | 기존회원(최대) | 신규회원(최대)

## 1) 대시보드 배포 (Vercel)
1. 이 폴더를 **새 GitHub repo**에 올림(스크래퍼 repo 아님).
2. Supabase에 anon read RLS 정책 확인:
   ```sql
   alter table card_benefit2 enable row level security;
   create policy "anon read" on card_benefit2 for select to anon using (true);
   ```
3. Vercel에서 repo import → Vite 자동 인식.
4. Vercel 환경변수 2개(.env.example 참고):
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`  ← anon public 키만. service_role 금지.
5. Deploy.

## 2) 구글시트 동기화 (Code.gs)
1. 시트 > 확장 프로그램 > Apps Script 에 `Code.gs` 붙여넣기.
2. 프로젝트 설정 > 스크립트 속성:
   - `SUPABASE_URL` = https://xxxx.supabase.co
   - `SUPABASE_ANON_KEY` = anon 키
3. `installHourlyTrigger` 1회 실행 → 매시간 자동.
4. 시트 재오픈 시 상단 `[할인카드]` 메뉴 → 수동 새로고침. 시트 열 때도 자동.
5. `통신` / `렌탈` 시트가 자동 생성됨. 미수집 카드는 공란 행으로 남음.

### 공란 행(MASTER) 정확도
`Code.gs`의 `MASTER_TEL / MASTER_RENTAL`은 업로드한 엑셀 이미지를 손으로 옮긴 것 → **오타·누락 가능(검증 필요).**
더 정확히 하려면 시트에 `마스터_통신` / `마스터_렌탈` 탭을 만들고 A=통신사, B=카드사, C=카드명으로 엑셀에서 그대로 복붙. 그 탭이 있으면 코드 내 배열보다 우선함.
매칭은 "공백 무시 후 정확히 일치". 카드명이 Supabase `card_name`과 다르면 그 행은 공란으로 남음(중복행은 안 생김).

## 확인 필요한 가정 (src/App.jsx & Code.gs 상단 CFG)
- `type` 값이 `기본 / 프로모션 / 할부이용`과 정확히 일치하는지. 다르면 CFG에서 수정.
- `할부이용`은 기존회원(기본) 칸에 합침(`INSTALL_AS_BASE`).
- `discount` / `fee`가 원 단위라는 전제. 천원 단위면 보정 필요.
- `spend_tier`는 만원 단위(표시 시 "N만원").
