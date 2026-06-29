import { useEffect, useMemo, useState } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

/* 데이터가 예상과 다르면 여기만 고치면 됨 */
const CFG = {
  TYPE_BASE: '기본', // 기존회원 (기본할인)
  TYPE_PROMO: '프로모션', // 신규회원 (프로모션)
  TYPE_INSTALL: '할부이용', // 가정: 기존회원(기본) 칸에 합쳐 표시
  INSTALL_AS_BASE: true,
  TEL_CATS: ['통신', '통신-할부형'],
  RENTAL_CATS: ['렌탈'],
}

// 콤마·"원"·문자 섞인 값에서 숫자만 추출. 못 뽑으면 null
const num = (v) => {
  if (v == null) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const digits = String(v).replace(/[^0-9.-]/g, '')
  if (digits === '' || digits === '-' || digits === '.') return null
  const n = Number(digits)
  return Number.isFinite(n) ? n : null
}
const won = (v) => {
  const n = num(v)
  return n == null ? '' : n.toLocaleString('ko-KR')
}
const tier = (v) => {
  const n = num(v)
  return n == null ? '' : `${n.toLocaleString('ko-KR')}만원`
}
// 공백 무시 그룹 키 (표기 미묘하게 달라 쪼개지는 중복 합침)
const gkey = (r) =>
  [r.carrier, r.issuer, r.card_name].map((s) => String(s ?? '').replace(/\s+/g, '')).join('||')

/* long → wide 피벗 (25개월후/혜택기간 제외) */
function pivot(rows) {
  const groups = new Map()
  for (const r of rows) {
    const key = gkey(r)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(r)
  }

  const out = []
  for (const g of groups.values()) {
    const base = g[0]
    const tiers = g.map((r) => num(r.spend_tier)).filter((v) => v != null)
    const minT = tiers.length ? Math.min(...tiers) : null
    const maxT = tiers.length ? Math.max(...tiers) : null

    const pick = (t, type) => {
      const hit = g.find((r) => num(r.spend_tier) === t && r.type === type)
      if (hit) return num(hit.discount)
      if (type === CFG.TYPE_BASE && CFG.INSTALL_AS_BASE) {
        const inst = g.find((r) => num(r.spend_tier) === t && r.type === CFG.TYPE_INSTALL)
        if (inst) return num(inst.discount)
      }
      return null
    }

    out.push({
      carrier: base.carrier,
      issuer: base.issuer,
      card_name: base.card_name,
      fee: g.map((r) => r.fee).find((v) => v != null && v !== '') ?? '', // 원문 그대로
      tierMin: minT,
      baseMin: pick(minT, CFG.TYPE_BASE),
      promoMin: pick(minT, CFG.TYPE_PROMO),
      tierMax: maxT,
      baseMax: pick(maxT, CFG.TYPE_BASE),
      promoMax: pick(maxT, CFG.TYPE_PROMO),
    })
  }
  // 수집된 값이 하나도 없는 행은 대시보드에서 제외
  return out.filter(
    (r) => [r.baseMin, r.promoMin, r.baseMax, r.promoMax].some((v) => v != null)
  )
}

function withRowspan(rows) {
  const sorted = [...rows].sort(
    (a, b) =>
      a.carrier.localeCompare(b.carrier, 'ko') ||
      a.issuer.localeCompare(b.issuer, 'ko') ||
      a.card_name.localeCompare(b.card_name, 'ko')
  )
  const counts = {}
  sorted.forEach((r) => (counts[r.carrier] = (counts[r.carrier] || 0) + 1))
  let prev = null
  return sorted.map((r) => {
    const first = r.carrier !== prev
    prev = r.carrier
    return { ...r, _carrierFirst: first, _carrierSpan: counts[r.carrier] }
  })
}

function Cell({ v, money, isTier }) {
  const text = isTier ? tier(v) : money ? won(v) : v
  return (
    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{text || ''}</td>
  )
}

// 렌탈 표 맨 위에 원문 그대로 고정할 자사(아정당) 행
const PINNED_RENTAL = [
  { carrier: '아정당렌탈', issuer: '하나', card_name: '아정당 하나카드', fee: '29,000', tierMin: '30만원', baseMin: '15,000', promoMin: '25개월~ 6,000원', tierMax: '120만원', baseMax: '20,000', promoMax: '' },
  { carrier: '아정당렌탈', issuer: '우리', card_name: '아정당 우리카드', fee: '20,000', tierMin: '30만원', baseMin: '10,000', promoMin: '', tierMax: '150만원', baseMax: '15,000', promoMax: '' },
]

function CompareTable({ rows, firstColLabel, pinned }) {
  const data = withRowspan(rows)
  const hasPinned = pinned && pinned.length > 0
  if (!data.length && !hasPinned)
    return <div className="text-slate-400 text-sm py-8 text-center">표시할 카드가 없습니다.</div>

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full border-collapse text-[13px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-slate-700 text-white">
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap">{firstColLabel}</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap">카드사</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap text-left">카드명</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap">연회비</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap">전월실적(최소)</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap bg-emerald-700/80">기존회원<br/>(기본할인)</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap bg-emerald-700/80">신규회원<br/>(프로모션)</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap">전월실적(최대)</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap bg-sky-800/80">기존회원<br/>(최대)</th>
            <th className="border border-slate-600 px-2 py-2 whitespace-nowrap bg-sky-800/80">신규회원<br/>(최대)</th>
          </tr>
        </thead>
        <tbody>
          {hasPinned && pinned.map((r, i) => (
            <tr key={'pin' + i} className="bg-amber-100/70 font-medium">
              {i === 0 && (
                <td rowSpan={pinned.length} className="border border-slate-200 px-2 py-1 text-center font-semibold bg-amber-200/60 align-middle">
                  {r.carrier}
                </td>
              )}
              <td className="border border-slate-200 px-2 py-1 text-center whitespace-nowrap">{r.issuer}</td>
              <td className="border border-slate-200 px-2 py-1 text-left whitespace-nowrap">{r.card_name}</td>
              <td className="border border-slate-200 px-2 py-1 text-left text-[11px] text-slate-700 leading-tight min-w-[140px]">{r.fee}</td>
              <td className="border border-slate-200 px-2 py-1 text-right">{r.tierMin}</td>
              <td className="border border-slate-200 px-2 py-1 text-right">{r.baseMin}</td>
              <td className="border border-slate-200 px-2 py-1 text-right whitespace-nowrap">{r.promoMin}</td>
              <td className="border border-slate-200 px-2 py-1 text-right">{r.tierMax}</td>
              <td className="border border-slate-200 px-2 py-1 text-right">{r.baseMax}</td>
              <td className="border border-slate-200 px-2 py-1 text-right">{r.promoMax}</td>
            </tr>
          ))}
          {data.map((r, i) => (
            <tr key={i} className="even:bg-slate-50/60 hover:bg-amber-50">
              {r._carrierFirst && (
                <td
                  rowSpan={r._carrierSpan}
                  className="border border-slate-200 px-2 py-1 text-center font-semibold bg-slate-100 align-middle"
                >
                  {r.carrier}
                </td>
              )}
              <td className="border border-slate-200 px-2 py-1 text-center whitespace-nowrap">{r.issuer}</td>
              <td className="border border-slate-200 px-2 py-1 text-left whitespace-nowrap">{r.card_name}</td>
              <td className="border border-slate-200 px-2 py-1 text-left text-[11px] text-slate-600 leading-tight min-w-[140px]">{r.fee || ''}</td>
              <Cell v={r.tierMin} isTier />
              <Cell v={r.baseMin} money />
              <Cell v={r.promoMin} money />
              <Cell v={r.tierMax} isTier />
              <Cell v={r.baseMax} money />
              <Cell v={r.promoMax} money />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function App() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [tab, setTab] = useState('통신')
  const [latestDate, setLatestDate] = useState(null)

  useEffect(() => {
    ;(async () => {
      try {
        const { data, error } = await supabase.from('card_benefit2').select('*').limit(5000)
        if (error) throw error
        const dates = data.map((r) => r.date).filter(Boolean).sort()
        const newest = dates[dates.length - 1] || null
        setLatestDate(newest)
        setRows(newest ? data.filter((r) => r.date === newest) : data)
      } catch (e) {
        setErr(e.message || String(e))
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const telRows = useMemo(
    () => pivot(rows.filter((r) => CFG.TEL_CATS.includes(r.category))),
    [rows]
  )
  const rentalRows = useMemo(
    () => pivot(rows.filter((r) => CFG.RENTAL_CATS.includes(r.category))),
    [rows]
  )

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-[1400px] mx-auto">
      <header className="mb-4">
        <h1 className="text-xl font-bold text-slate-800">통신·렌탈 할인카드 비교표</h1>
        <p className="text-xs text-slate-500 mt-1">
          {latestDate ? `기준일: ${latestDate} · ` : ''}출처 card_benefit2 · 자동수집된 카드만 표시
        </p>
      </header>

      <div className="flex gap-2 mb-3">
        {['통신', '렌탈'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${
              tab === t ? 'bg-slate-700 text-white' : 'bg-white text-slate-600 border border-slate-200'
            }`}
          >
            {t} ({t === '통신' ? telRows.length : rentalRows.length})
          </button>
        ))}
      </div>

      {loading && <div className="text-slate-400 py-12 text-center">불러오는 중…</div>}
      {err && (
        <div className="text-rose-600 bg-rose-50 border border-rose-200 rounded p-3 text-sm">
          데이터 로드 실패: {err}
          <div className="text-rose-400 text-xs mt-1">
            VITE_SUPABASE_URL / ANON_KEY 환경변수와 card_benefit2 RLS read 정책을 확인하세요.
          </div>
        </div>
      )}

      {!loading && !err && (
        <>
          {tab === '통신' && <CompareTable rows={telRows} firstColLabel="통신사" />}
          {tab === '렌탈' && <CompareTable rows={rentalRows} firstColLabel="가맹점" pinned={PINNED_RENTAL} />}
        </>
      )}
    </div>
  )
}
