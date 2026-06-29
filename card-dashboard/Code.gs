/**
 * Supabase card_benefit2 → 구글시트 통신/렌탈 비교표
 * - 대시보드(React)와 같은 컬럼 / 같은 피벗 로직
 * - 단, 시트에는 미수집·보류 카드도 "공란 행"으로 표시 (MASTER 목록 기반)
 *
 * ── 설치 ──────────────────────────────────────────────
 * 1) 확장 프로그램 > Apps Script 에 이 파일 붙여넣기
 * 2) 프로젝트 설정 > 스크립트 속성에 추가:
 *      SUPABASE_URL       = https://xxxx.supabase.co
 *      SUPABASE_ANON_KEY  = (anon public 키. service_role 금지)
 *    ※ card_benefit2 에 anon read RLS 정책 필요.
 * 3) 함수 installHourlyTrigger 1회 실행 → 매시간 자동 새로고침
 * 4) 시트 새로고침/재오픈하면 상단에 [할인카드] 메뉴 생김 → 수동 새로고침 가능
 *
 * ── "실시간" 관련 솔직한 한계 ──────────────────────────
 *  시트는 Supabase를 실시간 구독 못 함. 여기선 (a)시트 열 때 (b)메뉴 버튼
 *  (c)매시간 트리거 로 새로고침함 = 준실시간. 진짜 실시간은 React 대시보드 쪽.
 */

const CFG = {
  TABLE: 'card_benefit2',
  TYPE_BASE: '기본',          // 기존회원(기본할인)
  TYPE_PROMO: '프로모션',     // 신규회원(프로모션)
  TYPE_INSTALL: '할부이용',   // 가정: 기본 칸에 합침
  INSTALL_AS_BASE: true,
  TEL_CATS: ['통신', '통신-할부형'],
  RENTAL_CATS: ['렌탈'],
};

const HEADERS = [
  '카드사', '카드명', '연회비', '전월실적(최소)',
  '기존회원(기본할인)', '신규회원(프로모션)',
  '전월실적(최대)', '기존회원(최대)', '신규회원(최대)',
];

/**
 * MASTER 목록 = 시트에 "행으로 떠야 하는" 모든 카드.
 * [통신사/가맹점, 카드사, 카드명]
 * ※ 아래는 네가 올린 엑셀 이미지에서 옮겨적은 것 → 오타·누락 있을 수 있음(검증 필요).
 * ※ 더 정확히 하려면: 시트에 '마스터_통신' / '마스터_렌탈' 탭을 만들고
 *    A:통신사 B:카드사 C:카드명 으로 붙여넣으면 그 탭이 아래 배열보다 우선함.
 * ※ 카드명이 Supabase card_name 과 (공백 무시) 일치해야 값이 채워짐.
 *    안 맞으면 그 행은 공란으로 남음(중복행은 안 생김).
 */
const MASTER_TEL = [
  ['SKT', '삼성', 'T나는혜택 삼성카드'],
  ['SKT', '하나', '아정당 하나카드'],
  ['SKT', '국민', 'T-economy KB국민카드'],
  ['SKT', '롯데', '롯데카드 TELLO SE'],
  ['SKT', '하나', 'CLUB SK카드'],
  ['SKT', '현대', 'SKT-현대카드M Edition3(통신할인형2.0)'],
  ['KT', '신한', 'KT 가족만족 DC'],
  ['KT', '삼성', 'KT 삼성카드'],
  ['KT', '하나', '아정당 하나카드'],
  ['KT', 'BC', 'KT DC PLUS'],
  ['KT', '현대', 'kt-현대카드M Edition3(청구할인형)'],
  ['KT', '하나', 'KT DC PLUS 더 심플'],
  ['KT', '기업', 'olleh Super DC'],
  ['KT', '국민', 'KT DC Plus'],
  ['KT', '롯데', 'KT DC PLUS'],
  ['KT', '우리', 'KT Plus'],
  ['KT', 'BC', 'KT SUPER DC'],
  ['KT', '우리', 'KT 36 Plus 우리카드'],
  ['KT', '농협', 'KT할부 Plus'],
  ['KT', '신한', 'KT으랏차차'],
  ['KT', '현대', 'kt-현대카드M Edition3(통신할인형 2.0)'],
  ['KT', '현대', 'kt-현대카드M Edition3(청구할인형 2.0)'],
  ['LGU+', '롯데', 'LG U+ X LOCA'],
  ['LGU+', '농협', 'NH올원 LGU+카드'],
  ['LGU+', '삼성', 'LG U+ 삼성카드'],
  ['LGU+', '하나', '아정당 하나카드'],
  ['LGU+', '하나', '더 심플'],
  ['LGU+', '신한', 'LG U+ 스마트플랜 Plus'],
  ['LGU+', '국민', 'LG U+ KB 심플라이트2 카드'],
  ['LGU+', '하나', 'U+Family 하나카드'],
  ['LGU+', '우리', 'LG U+ X 우리카드'],
  ['LGU+', '신한', 'LG U+ Bora Big Plus'],
  ['LGU+', '현대', 'LG U+-현대카드M Edition3(통신할인형2.0)'],
  ['LGU+', '신한', 'LG U+ 사장님 통할인카드'],
  ['SKB', '삼성', 'T나는혜택 삼성카드'],
  ['SKB', '하나', '아정당 하나카드'],
  ['SKB', '하나', '더 심플'],
];

const MASTER_RENTAL = [
  ['아정당렌탈', '하나', '아정당 하나카드'],
  ['아정당렌탈', '우리', '아정당 우리카드'],
  ['교원웰스', '우리', '웰스 우리카드'],
  ['교원웰스', '롯데', '웰스 롯데카드'],
  ['유버스', '우리', '현대렌탈서비스 우리카드'],
  ['현대큐밍', '우리', '현대큐밍 우리카드Ⅱ'],
  ['현대큐밍', '롯데', '현대큐밍 x LOCA(롯데카드)'],
  ['코웨이', '신한', '코웨이 신한카드'],
  ['코웨이', '우리', '코웨이 우리카드 Ⅱ'],
  ['쿠쿠', '국민', '쿠쿠 렌탈Ⅱ 국민카드'],
  ['쿠쿠', '우리', '쿠쿠 우리카드'],
  ['쿠쿠', '롯데', '쿠쿠 X LOCA'],
  ['청호나이스', '국민', '청호 KB국민카드 Ⅱ'],
  ['청호나이스', '우리', '청호 우리카드 Ⅱ'],
  ['청호나이스', '신한', '청호나이스 신한카드'],
  ['세라젬', '국민', '세라젬 KB국민카드'],
  ['세라젬', '롯데', 'LOCA X 세라젬 카드'],
  ['세라젬', '우리', '세라젬 구독 우리카드'],
  ['SK인텔릭스', '국민', 'SK인텔릭스 KB국민 올림카드'],
  ['SK인텔릭스', '우리', 'SK인텔릭스 우리카드'],
  ['SK인텔릭스', '신한', 'SK인텔릭스 신한카드'],
  ['LG헬로비전', '우리', 'LG헬로비전 우리집엔 우리카드'],
  ['LG전자', '신한', 'The 구독케어 신한카드'],
  ['LG전자', '우리', 'LG전자 우리카드'],
  ['바디프렌드', '롯데', '바디프랜드 X LOCA'],
  ['바디프렌드', '우리', '바디프랜드 우리카드 Ⅱ'],
  ['세스코', '삼성', '세스코 삼성카드'],
  ['세스코', '롯데', 'LOCA X Special SE 카드'],
  ['BS온', '하나', 'BS렌탈 플러스 하나카드'],
  ['BS온', '롯데', 'LOCA X BS RENTAL 롯데카드'],
  ['스마트렌탈', '롯데', 'LOCA X Special SE 카드'],
  ['캐리어', '롯데', 'LOCA X Special SE 롯데카드'],
];

/* ───────────────────────── 메뉴 / 트리거 ───────────────────────── */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('할인카드')
    .addItem('Supabase 새로고침', 'refreshAll')
    .addToUi();
  refreshAll(); // 열 때 자동 1회
}

function installHourlyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'refreshAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('refreshAll').timeBased().everyHours(1).create();
}

/* ───────────────────────── 메인 ───────────────────────── */
function refreshAll() {
  const all = fetchRows_();
  const dates = all.map(function (r) { return r.date; }).filter(Boolean).sort();
  const newest = dates.length ? dates[dates.length - 1] : null;
  const rows = newest ? all.filter(function (r) { return r.date === newest; }) : all;

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  writeTab_(ss, '통신', '통신사',
    pivot_(rows.filter(function (r) { return CFG.TEL_CATS.indexOf(r.category) >= 0; })),
    getMaster_(ss, '마스터_통신', MASTER_TEL), newest);
  writeTab_(ss, '렌탈', '가맹점',
    pivot_(rows.filter(function (r) { return CFG.RENTAL_CATS.indexOf(r.category) >= 0; })),
    getMaster_(ss, '마스터_렌탈', MASTER_RENTAL), newest);
}

function fetchRows_() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('SUPABASE_URL');
  const key = props.getProperty('SUPABASE_ANON_KEY');
  if (!url || !key) throw new Error('스크립트 속성에 SUPABASE_URL, SUPABASE_ANON_KEY 를 설정하세요.');
  const endpoint = url.replace(/\/+$/, '') + '/rest/v1/' + CFG.TABLE + '?select=*&limit=5000';
  const res = UrlFetchApp.fetch(endpoint, {
    method: 'get',
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() >= 300) {
    throw new Error('Supabase ' + res.getResponseCode() + ': ' + res.getContentText().slice(0, 300));
  }
  return JSON.parse(res.getContentText());
}

/* long → wide 피벗 (25개월후/혜택기간 제외) */
function pivot_(rows) {
  const groups = {};
  rows.forEach(function (r) {
    const k = [r.carrier, r.issuer, r.card_name].join('||');
    (groups[k] = groups[k] || []).push(r);
  });

  const out = {};
  Object.keys(groups).forEach(function (k) {
    const g = groups[k];
    const base = g[0];
    const tiers = g.map(function (r) { return r.spend_tier; })
      .filter(function (v) { return v != null; }).map(Number);
    const minT = tiers.length ? Math.min.apply(null, tiers) : null;
    const maxT = tiers.length ? Math.max.apply(null, tiers) : null;

    function pick(t, type) {
      const hit = g.filter(function (r) { return Number(r.spend_tier) === t && r.type === type; })[0];
      if (hit) return hit.discount;
      if (type === CFG.TYPE_BASE && CFG.INSTALL_AS_BASE) {
        const inst = g.filter(function (r) { return Number(r.spend_tier) === t && r.type === CFG.TYPE_INSTALL; })[0];
        if (inst) return inst.discount;
      }
      return null;
    }
    function feeOf() {
      const f = g.filter(function (r) { return r.fee != null; })[0];
      return f ? f.fee : null;
    }

    out[normKey_(base.carrier, base.issuer, base.card_name)] = {
      carrier: base.carrier, issuer: base.issuer, card_name: base.card_name,
      fee: feeOf(), tierMin: minT, baseMin: pick(minT, CFG.TYPE_BASE), promoMin: pick(minT, CFG.TYPE_PROMO),
      tierMax: maxT, baseMax: pick(maxT, CFG.TYPE_BASE), promoMax: pick(maxT, CFG.TYPE_PROMO),
    };
  });
  return out; // key → row
}

function getMaster_(ss, tabName, fallback) {
  const sh = ss.getSheetByName(tabName);
  if (!sh) return fallback;
  const vals = sh.getDataRange().getValues();
  const rows = [];
  for (var i = 1; i < vals.length; i++) { // 1행은 헤더로 간주
    var c = vals[i][0], iss = vals[i][1], name = vals[i][2];
    if (name) rows.push([String(c || ''), String(iss || ''), String(name)]);
  }
  return rows.length ? rows : fallback;
}

function normKey_(c, i, n) {
  return [c, i, n].map(function (s) { return String(s == null ? '' : s).replace(/\s+/g, ''); }).join('|');
}

function tierStr_(v) { return v == null ? '' : Number(v).toLocaleString('en-US') + '만원'; }
function numOr_(v) { return v == null ? '' : Number(v); }

/* MASTER 순서대로 행 구성 + 매칭 안 된 수집행은 뒤에 append */
function buildRows_(pivotMap, master) {
  const used = {};
  const out = [];
  master.forEach(function (m) {
    const key = normKey_(m[0], m[1], m[2]);
    const hit = pivotMap[key];
    used[key] = true;
    out.push(toCells_(m[0], m[1], m[2], hit));
  });
  Object.keys(pivotMap).forEach(function (key) {
    if (!used[key]) {
      const r = pivotMap[key];
      out.push(toCells_(r.carrier, r.issuer, r.card_name, r));
    }
  });
  return out;
}

function toCells_(carrier, issuer, cardName, r) {
  if (!r) return [carrier, issuer, cardName, '', '', '', '', '', '', ''];
  return [
    carrier, issuer, cardName,
    numOr_(r.fee), tierStr_(r.tierMin), numOr_(r.baseMin), numOr_(r.promoMin),
    tierStr_(r.tierMax), numOr_(r.baseMax), numOr_(r.promoMax),
  ];
}

function writeTab_(ss, sheetName, firstLabel, pivotMap, master, dateStr) {
  var sh = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
  sh.clear();

  const header = [firstLabel].concat(HEADERS);
  const body = buildRows_(pivotMap, master);
  const note = '기준일 ' + (dateStr || '-') + ' · 갱신 ' + Utilities.formatDate(new Date(), 'Asia/Seoul', 'MM-dd HH:mm');

  sh.getRange(1, 1, 1, 1).setValue(note).setFontColor('#888').setFontSize(9);
  sh.getRange(2, 1, 1, header.length).setValues([header])
    .setFontWeight('bold').setBackground('#334155').setFontColor('#ffffff')
    .setHorizontalAlignment('center');
  if (body.length) {
    sh.getRange(3, 1, body.length, header.length).setValues(body);
    // 금액 컬럼: 연회비(4), 기본(6), 프로모션(7), 최대기본(9), 최대프로모션(10)
    [4, 6, 7, 9, 10].forEach(function (col) {
      sh.getRange(3, col, body.length, 1).setNumberFormat('#,##0');
    });
  }
  sh.setFrozenRows(2);
  sh.getRange(2, 1, body.length + 1, header.length)
    .setBorder(true, true, true, true, true, true, '#cbd5e1', SpreadsheetApp.BorderStyle.SOLID);
  for (var c = 1; c <= header.length; c++) sh.autoResizeColumn(c);
}
