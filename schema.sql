-- ════════════════════════════════════════════════════════════
-- Supabase 통합 스키마 v2 : 통신 + 렌탈 제휴카드 (long format, 날짜별 이력)
-- 기존 card_benefit(렌탈 전용)을 건드리지 않도록 새 테이블 card_benefit2 사용.
-- CSV(card_long_*.csv) 헤더와 컬럼이 1:1 일치.
-- ════════════════════════════════════════════════════════════
create table if not exists card_benefit2 (
  id          bigint generated always as identity primary key,
  date        date    not null,          -- 수집일(스냅샷)
  category    text,                       -- 통신 / 통신-할부형 / 렌탈
  carrier     text,                       -- 통신사 또는 렌탈가맹점 (SKB/LGU+/코웨이...)
  carrier2    text,                       -- 보조 통신사 라벨(통신만; 렌탈은 빈값)
  issuer      text,                       -- 카드사(롯데/신한/삼성/KB국민/하나/우리/현대/NH농협/BC바로)
  card_name   text    not null,           -- 카드명
  tel         text,                       -- 상담전화(렌탈 일부)
  fee         text,                       -- 연회비(원문)
  spend_tier  int,                        -- 전월실적 구간(만원), 범위형은 NULL
  type        text,                       -- 기본/프로모션/할부이용/할부미이용/25개월후/범위
  discount    int,                        -- 할인액(원), 범위형은 NULL
  disc_type   text,                       -- 청구할인/캐시백/결제대금차감/아이폰전용
  apply_url   text,                       -- 발급링크(또는 유모바일 gubun)
  note        text,                       -- 비고(범위만/구간미상/카드타입 등)
  created_at  timestamptz default now()
);
create index if not exists idx_cb2_date    on card_benefit2(date);
create index if not exists idx_cb2_carrier on card_benefit2(carrier);
create index if not exists idx_cb2_cat     on card_benefit2(category);

-- ── 어제 대비 변동(diff) 보기 ──────────────────────────────
-- select category, carrier, card_name, spend_tier, type, discount
-- from card_benefit2 where date = current_date
-- except
-- select category, carrier, card_name, spend_tier, type, discount
-- from card_benefit2 where date = current_date - 1;

-- ── 통신사별 최신 스냅샷 카드 수 ───────────────────────────
-- select carrier, count(distinct card_name) as 카드수
-- from card_benefit2 where date = (select max(date) from card_benefit2)
-- group by carrier order by 카드수 desc;
