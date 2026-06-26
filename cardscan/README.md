# 통신/렌탈 제휴카드 할인 수집기 (패밀리 A + B)

패밀리 A `partner.*/user/sub5014`(다온홈시스, 8개) + 패밀리 B `/shop/card.php`(bilrigo, 5개: 세스코·BS렌탈·이니렌탈·렌타나·캐리어)의 제휴카드 **실적별 청구할인(기본·프로모션)**을 수집.
서버렌더 HTML이라 `requests`만으로 동작 (Playwright 불필요).

## 빠른 시작 (로컬, 키 없이 CSV만)
```bash
pip install requests beautifulsoup4 lxml
python3 collect.py
# → card_long_YYYY-MM-DD.csv (행 단위), card_grid_YYYY-MM-DD.csv (30~200만 그리드)
```

## Supabase 적재 (선택)
1. Supabase SQL 편집기에 `schema.sql` 실행 → `card_benefit` 테이블 생성
2. 환경변수 설정 후 실행:
```bash
export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_KEY="<service_role 또는 anon key>"
python3 collect.py
```

## 매일 자동 (GitHub Actions)
1. 이 폴더를 레포에 push
2. 레포 Settings → Secrets → `SUPABASE_URL`, `SUPABASE_KEY` 등록
3. `.github/workflows/daily-card-scan.yml` 가 매일 07:00 KST 실행 (Actions 탭에서 수동 실행도 가능)
4. CSV는 `history/` 에 날짜별로 쌓이고, Supabase에도 적재됨

## 워치리스트 추가/수정
`collect.py` 상단 `WATCHLIST_A` 딕셔너리에 브랜드:URL 추가.

## 한계 / 점검 포인트 (정직하게)
- **검증된 건 코웨이 1개.** 나머지 7개(SK매직·쿠쿠·LG전자·청호·교원·현대큐밍·루헨스)는 같은 솔루션이라 구조가 같을 확률이 높지만, **첫 실행 로그에서 `[FAIL]` 뜨는 브랜드는 개별 점검** 필요.
- **프로모션 행 인식**은 사이트가 `..._프로모션` 라벨을 쓸 때만 자동 분리됨(코웨이 방식). 다른 표기를 쓰면 그 브랜드만 보정 필요.
- 일부 사이트가 봇 차단/다른 인코딩이면 그 브랜드만 예외 처리 추가.
- **대리점 비공식 리펀딩(Layer B)은 여기 안 잡힘** — 게시 안 되는 정보라 수기 입력 영역.
- 패밀리 B(`/shop/card.php`)·단발 사이트는 파서가 다름 → 다음 단계.


## 수집 범위 (2026-06 기준)
- 패밀리 A (다온홈시스, card_Wrap) 8: 코웨이·SK매직·쿠쿠·LG전자·청호나이스·교원웰스·현대큐밍·루헨스 — 검증 완료
- 패밀리 B (bilrigo, tbl_CardInfo) 5: 세스코·BS렌탈·이니렌탈·렌타나·캐리어 — 검증 완료
- 단발(C) 3: LG헬로비전·렌탈페이·스마트렌탈 — 검증 완료 (스마트렌탈은 카드 2장이 1장으로 합쳐지는 미세결함 있음, 보정 예정)
- **자동수집 불가(이미지/클릭형 → 수기 또는 추후 비전OCR)**: 유버스, 세라젬, 바디프랜드 (카피렌탈=페이지 없음)
- 대리점 비공식 리펀딩(Layer B)도 수기 영역(게시 안 됨)
