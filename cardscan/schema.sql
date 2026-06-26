-- Supabase: 제휴카드 실적별 할인 적재 테이블 (long format, 날짜별 이력)
create table if not exists card_benefit (
  id          bigint generated always as identity primary key,
  date        date         not null,           -- 수집일 (스냅샷)
  family      text,                             -- 플랫폼 패밀리 (A/B/단발)
  brand       text         not null,            -- 가맹점 (코웨이 등)
  card_name   text         not null,            -- 카드명
  tel         text,
  fee         text,                             -- 연회비(원문)
  spend_tier  int,                              -- 전월실적 구간(만원)
  type        text,                             -- 기본 / 프로모션
  discount    int,                              -- 청구할인액(원)
  apply_url   text,
  created_at  timestamptz  default now()
);
create index if not exists idx_cb_date  on card_benefit(date);
create index if not exists idx_cb_brand on card_benefit(brand);

-- 어제 대비 변동(diff) 보기 예시
-- select brand, card_name, spend_tier, type, discount
-- from card_benefit where date = current_date
-- except
-- select brand, card_name, spend_tier, type, discount
-- from card_benefit where date = current_date - 1;
