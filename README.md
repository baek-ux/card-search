# 통신·렌탈 제휴카드 할인 수집기

경쟁사 제휴카드의 **전월실적 구간별 청구할인액**(기본/프로모션)을 매일 자동 수집해서
CSV + (옵션)Supabase에 적재합니다. 통신 7개 통신사 + 렌탈 16개 사이트.

## 실행
```
pip install requests beautifulsoup4 lxml
python3 collect.py
```
- 환경변수 `SUPABASE_URL`/`SUPABASE_KEY` 있으면 Supabase 적재, 없으면 **CSV만** 생성.
- 출력: `card_long_<날짜>.csv`(long format), `card_grid_<날짜>.csv`(30~200만 그리드 보기용).

## 실행하면 뜨는 리포트 보는 법
```
✅ [통신] SKB              3장  OK              ← 정상 수집
⚠️  [통신] HCN             0장  0건(selector확인)  ← fetch는 됐는데 파싱 0건 = selector 점검 필요
❌ [통신] LGU+             0장  FAIL: ...        ← 요청 자체 실패(URL/네트워크)
```
- **한 사이트가 죽어도 나머지는 끝까지 수집**(실패 격리). 어디가 몇 장인지 한눈에.

## 수집 대상 (통신 7 + 렌탈 16)
| 통신사 | 방식 | 비고 |
|---|---|---|
| SKB | 정적 | 자기 페이지에 구간 있음 |
| LG헬로비전(홈) | 정적 | 기본+프로모션 분해 |
| HCN | 정적 | HCN/skylife 카드 혼재(carrier 자동분기), 국내/해외 트랙 분리 |
| 딜라이브 | 정적+2페이지 | 에디터 자유텍스트 정규식 파싱 |
| 유모바일 | 정적 | 목록+팝업테이블 join, 삼성카드 구간은 상세필요 |
| SKT | 제외 | 페이지 범위값이 카드사 실제 구간과 불일치 → 수기 영역 |
| KT | savedream API | 정형표 자동(KT Plus 등), 복합·다단표는 수기플래그. uuid는 KT_PRODIDS에 등록 |
| LGU+ 본체 | JSON API | 구간 테이블 포함. URL이 막히면 F12 Request URL로 교체 |

## 보류(Tier2, 후속 작업)
- **스카이라이프 4탭**(KB/롯데/하나/BC): SPA 클라이언트 렌더 → Playwright 또는 탭별 API 필요. 신한 탭만 일부 확보.
- **KT savedream 허브 12장**: 카드 상세가 허브에 있음 → 허브 파서 별도 필요.
- **유모바일 삼성카드 구간**, **SKT 카드사 상세**(삼성 __NUXT__ 등).

## 컬럼(card_long)
`date, category(통신/통신-할부형/렌탈), carrier(통신사·가맹점), carrier2, issuer(카드사), card_name, tel, fee(연회비), spend_tier(실적만원), type(기본/프로모션/할부이용/...), discount(원), disc_type(청구할인/캐시백/결제대금차감), apply_url, note`

## Supabase
`schema_v2.sql`을 SQL Editor에서 실행 → 테이블 `card_benefit2` 생성(기존 렌탈 테이블 `card_benefit`은 안 건드림). 이후 환경변수 설정하면 자동 적재.

## 자동 실행
`.github/workflows/daily-card-scan.yml` — 매일 07:00 KST. Settings>Secrets에 `SUPABASE_URL`/`SUPABASE_KEY` 등록.
