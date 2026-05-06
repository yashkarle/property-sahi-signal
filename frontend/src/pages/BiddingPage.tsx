import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Circle, Popup } from 'react-leaflet'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceArea, ResponsiveContainer, Cell,
} from 'recharts'
import { useSessionStore } from '../store/sessionStore'
import { useFinancialProfile, buyerCeiling } from '../store/financialProfileStore'
import {
  useCreateBidSession,
  useBidSession,
  useAddBid,
  useOfferBand,
  useAnalysePrice,
  useComparables,
  useRecordOutcome,
} from '../api/bidding'

function eur(n: number | undefined | null) {
  return n != null ? `€${n.toLocaleString('en-IE')}` : '—'
}

function SignalBar({ label, value, max, color, suffix = '' }: { label: string; value: number; max: number; color: string; suffix?: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="text-xs text-gray-600 w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-bold w-12 text-right" style={{ color }}>{value}{suffix}</span>
    </div>
  )
}

function StrategyStep({
  num, color, title, amount, rationale,
}: { num: number; color: string; title: string; amount?: number; rationale?: string }) {
  return (
    <div className="flex gap-3">
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5"
        style={{ background: color }}
      >
        {num}
      </div>
      <div>
        <div className="text-sm font-bold text-gray-900">{title}{amount != null ? ` — ${eur(amount)}` : ''}</div>
        <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{rationale}</div>
      </div>
    </div>
  )
}

const STEP_COLORS = ['#1e40af', '#0369a1', '#0d9488', '#dc2626']

export default function BiddingPage() {
  const { activePropertyId, activeBidSessionId, setActiveBidSession } = useSessionStore()
  const { aip, savings, isFirstTimeBuyer, setAip, setSavings } = useFinancialProfile()

  const [bidAmount, setBidAmount] = useState('')
  const [submittedBy, setSubmittedBy] = useState<'user' | 'other_buyer'>('user')
  const [showOutcome, setShowOutcome] = useState(false)
  const [outcomePrice, setOutcomePrice] = useState('')

  const queryClient = useQueryClient()
  const createSession = useCreateBidSession()
  const { data: session } = useBidSession(activeBidSessionId ?? undefined)
  const addBid = useAddBid(activeBidSessionId ?? '')
  const analysePrice = useAnalysePrice()
  const propertyId = session?.property_id ?? activePropertyId ?? undefined
  const { data: offerBand } = useOfferBand(propertyId)
  const { data: comparables = [] } = useComparables(propertyId)
  const recordOutcome = useRecordOutcome(activeBidSessionId ?? '')

  // Derive ceiling from saved session values when a session is active, so
  // editing the profile on FinancingPage doesn't silently rewrite an open session.
  // Must be computed after useBidSession so `session` is in scope.
  const sessionAip = (activeBidSessionId && session) ? (session.user_aip ?? aip) : aip
  const sessionSavings = (activeBidSessionId && session) ? (session.user_savings ?? savings) : savings
  const ceiling = buyerCeiling(sessionAip, sessionSavings, isFirstTimeBuyer)

  // Require both AIP and savings — without savings we cannot apply LTV/closing-cost
  // caps, and the resulting strategy/ceiling would be unsafe.
  const canStartSession = Boolean(activePropertyId && aip > 0 && savings > 0 && ceiling > 0)

  const handleCreateSession = () => {
    if (!canStartSession) return
    createSession.mutate(
      {
        property_id: activePropertyId!,
        user_max_budget: ceiling,
        user_aip: aip,
        user_savings: savings,
      },
      { onSuccess: (s: any) => setActiveBidSession(s.id) }
    )
  }

  const handleAddBid = () => {
    const amount = parseInt(bidAmount.replace(/[^0-9]/g, ''))
    if (!amount || !activeBidSessionId) return
    addBid.mutate(
      { bid_amount: amount, submitted_by: submittedBy },
      { onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bid-session'] }) }
    )
    setBidAmount('')
  }

  const handleOutcome = (outcome: 'won' | 'lost' | 'withdrawn') => {
    const price = outcomePrice ? parseInt(outcomePrice.replace(/[^0-9]/g, '')) : undefined
    recordOutcome.mutate(
      { outcome, actual_sale_price: price },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['bid-session'] })
          queryClient.invalidateQueries({ queryKey: ['bid-history'] })
          setShowOutcome(false)
        },
      }
    )
  }

  let strategy: any = null
  try {
    if (session?.strategy_advice) strategy = JSON.parse(session.strategy_advice)
  } catch { /* fall through */ }

  const chartData = (comparables as any[]).map((c) => ({
    date: new Date(c.date_of_sale + 'T12:00:00').getTime(), // noon UTC avoids timezone-shift by-1-day
    price: c.time_adjusted_price ?? c.price_eur,
    rawPrice: c.price_eur,
    address: c.address,
    distanceM: c.distance_m,
    monthsAgo: c.months_ago,
  }))

  // Percentile stats computed from comparables — always fresh, no ML model required
  const compStats = (() => {
    const prices = (comparables as any[])
      .map((c: any) => c.time_adjusted_price ?? c.price_eur)
      .filter(Boolean)
      .sort((a: number, b: number) => a - b)
    if (!prices.length) return null
    const pct = (p: number) => prices[Math.floor((prices.length - 1) * p)]
    const mean = Math.round(prices.reduce((s: number, v: number) => s + v, 0) / prices.length)
    return { p25: pct(0.25), median: pct(0.5), mean, p75: pct(0.75), count: prices.length }
  })()

  const tickFormatter = (ts: number) =>
    new Date(ts).toLocaleDateString('en-IE', { month: 'short', year: '2-digit' })

  const now = Date.now()
  const sixMonthsAgo = now - 6 * 30 * 24 * 60 * 60 * 1000
  const dotColor = (d: any) => {
    if (ceiling && d.price > ceiling) return '#94a3b8'
    if (d.date >= sixMonthsAgo) return '#3b82f6'
    return '#16a34a'
  }

  const compLats = (comparables as any[]).filter((c) => c.latitude && c.longitude)

  // Use the subject property's own coords (from offer-band) as map center.
  // Fall back to Dublin city centre only if neither is available.
  const propLat: number | null = (offerBand as any)?.property_lat ?? null
  const propLng: number | null = (offerBand as any)?.property_lng ?? null
  const mapCenter: [number, number] = propLat && propLng
    ? [propLat, propLng]
    : compLats.length > 0
      ? [
          compLats.reduce((s: number, c: any) => s + c.latitude, 0) / compLats.length,
          compLats.reduce((s: number, c: any) => s + c.longitude, 0) / compLats.length,
        ]
      : [53.3498, -6.2603]

  return (
    <div className="flex h-full overflow-hidden">

      {/* ═══ LEFT PANEL ═══ */}
      <div className="w-[420px] flex-shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-y-auto">

        {!activePropertyId && !session && (
          <div className="p-6">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
              Select a property from Search to start a bidding session.
            </div>
          </div>
        )}

        {(activePropertyId || session) && !activeBidSessionId && (
          <div className="p-5">
            <h2 className="font-bold text-gray-900 mb-4">Start Bidding Session</h2>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="block text-xs text-gray-600 mb-1">AIP mortgage (€)</label>
                <input type="number" value={aip || ''} onChange={(e) => setAip(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="370000" />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Cash savings (€)</label>
                <input type="number" value={savings || ''} onChange={(e) => setSavings(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="50000" />
              </div>
            </div>
            {ceiling > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm">
                <span className="text-gray-600">Your ceiling ({isFirstTimeBuyer ? '90%' : '80%'} LTV): </span>
                <span className="font-bold text-red-700">{eur(ceiling)}</span>
                <div className="text-gray-400 text-xs mt-0.5">
                  = {eur(aip)} AIP + {eur(savings)} − closing costs
                </div>
              </div>
            )}
            <button onClick={handleCreateSession} disabled={createSession.isPending || !canStartSession}
              className="w-full py-2.5 rounded-xl bg-green-700 text-white font-medium hover:bg-green-600 disabled:opacity-50">
              {createSession.isPending ? 'Starting…' : 'Start Session + Generate Strategy'}
            </button>
            {!canStartSession && activePropertyId && (
              <p className="text-xs text-gray-500 mt-2 text-center">
                Enter both AIP and savings to compute your ceiling.
              </p>
            )}
          </div>
        )}

        {activeBidSessionId && session && (
          <>
            <div className="grid grid-cols-3 border-b border-gray-100">
              {[
                { label: 'AIP', value: eur((session.user_aip ?? aip) || undefined), color: '#1e40af' },
                { label: 'Savings', value: eur((session.user_savings ?? savings) || undefined), color: '#16a34a' },
                { label: 'Your ceiling', value: eur(ceiling || session.user_max_budget || undefined), color: '#dc2626' },
              ].map((cell) => (
                <div key={cell.label} className="px-4 py-3 border-r border-gray-100 last:border-r-0">
                  <div className="text-[10px] text-gray-400 uppercase tracking-wide">{cell.label}</div>
                  <div className="text-base font-bold mt-0.5" style={{ color: cell.color }}>{cell.value}</div>
                </div>
              ))}
            </div>

            {offerBand && ceiling > 0 && offerBand.entry > ceiling && (
              <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex gap-2">
                <span className="text-amber-600 flex-shrink-0">⚠️</span>
                <p className="text-xs text-amber-800 leading-relaxed">
                  <strong>Market entry ({eur(offerBand.entry)}) exceeds your ceiling by {eur(offerBand.entry - ceiling)}.</strong>{' '}
                  Bid at ceiling as your Best & Final — see strategy →
                </p>
              </div>
            )}

            {offerBand && (
              <div className="px-4 py-3 border-b border-gray-100">
                <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Market signals</div>
                <SignalBar label="Sealed bid prob." value={Math.round((offerBand.sealed_bid_probability ?? 0) * 100)} max={100} color={(offerBand.sealed_bid_probability ?? 0) > 0.6 ? '#dc2626' : '#f97316'} suffix="%" />
                <SignalBar label="Seller leverage" value={offerBand.seller_leverage_score ?? 0} max={5} color="#f97316" suffix="/5" />
                <SignalBar label="Over-asking prob." value={Math.round((offerBand.over_asking_probability ?? 0) * 100)} max={100} color="#f97316" suffix="%" />
              </div>
            )}

            <div className="px-4 py-3 flex-1 border-b border-gray-100">
              <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Live bid ladder</div>
              {session.entries.length === 0 && (
                <p className="text-xs text-gray-400">No bids yet — log the first one below.</p>
              )}
              {[...session.entries].reverse().map((entry: any) => (
                <div key={entry.id} className="flex justify-between items-center py-2 border-b border-gray-50 last:border-b-0">
                  <span className={`text-sm ${entry.submitted_by === 'user' ? 'text-green-700 font-semibold' : 'text-gray-500'}`}>
                    {entry.submitted_by === 'user' ? '👤 You' : '🏷 Other buyer'}
                  </span>
                  <span className="text-sm font-bold">{eur(entry.bid_amount)}</span>
                  <span className="text-xs text-gray-400">
                    {new Date(entry.submitted_at).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>

            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Log a bid</div>
              <div className="flex gap-2 mb-2">
                {(['user', 'other_buyer'] as const).map((v) => (
                  <button key={v} onClick={() => setSubmittedBy(v)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                      submittedBy === v
                        ? v === 'user' ? 'bg-green-700 text-white border-green-700' : 'bg-gray-700 text-white border-gray-700'
                        : 'border-gray-200 text-gray-600'
                    }`}>
                    {v === 'user' ? '👤 My bid' : '🏷 Competing'}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input type="text" value={bidAmount} onChange={(e) => setBidAmount(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddBid()}
                  placeholder="€390,000"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <button onClick={handleAddBid}
                  className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-700">
                  Log
                </button>
              </div>
            </div>

            <div className="px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Record outcome</div>
              {!showOutcome ? (
                <div className="flex gap-2">
                  {(['won', 'lost', 'withdrawn'] as const).map((o) => (
                    <button key={o} onClick={() => setShowOutcome(true)}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border ${
                        o === 'won' ? 'border-green-400 text-green-700 bg-green-50' :
                        o === 'lost' ? 'border-red-400 text-red-700 bg-red-50' :
                        'border-gray-300 text-gray-600 bg-gray-50'
                      }`}>
                      {o === 'won' ? '🎉 Won' : o === 'lost' ? '❌ Lost' : '↩ Withdrawn'}
                    </button>
                  ))}
                </div>
              ) : (
                <div>
                  <input type="text" value={outcomePrice} onChange={(e) => setOutcomePrice(e.target.value)}
                    placeholder="Final sale price (optional)"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2" />
                  <div className="flex gap-2">
                    {(['won', 'lost', 'withdrawn'] as const).map((o) => (
                      <button key={o} onClick={() => handleOutcome(o)}
                        className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border ${
                          o === 'won' ? 'border-green-400 text-green-700 bg-green-50' :
                          o === 'lost' ? 'border-red-400 text-red-700 bg-red-50' :
                          'border-gray-300 text-gray-600 bg-gray-50'
                        }`}>
                        {o === 'won' ? '🎉 Won' : o === 'lost' ? '❌ Lost' : '↩ Withdrawn'}
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setShowOutcome(false)} className="text-xs text-gray-400 mt-1">Cancel</button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* ═══ RIGHT PANEL ═══ */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">

        {activeBidSessionId && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <button
              onClick={() => propertyId && analysePrice.mutate(
                {
                  property_id: propertyId,
                  buyer_aip: sessionAip || undefined,
                  buyer_savings: sessionSavings || undefined,
                  is_first_time_buyer: isFirstTimeBuyer,
                },
                {
                  onSuccess: () => {
                    queryClient.invalidateQueries({ queryKey: ['offer-band'] })
                    queryClient.invalidateQueries({ queryKey: ['bid-session'] })
                  },
                }
              )}
              disabled={analysePrice.isPending || !propertyId}
              className="w-full py-2.5 rounded-xl bg-blue-700 text-white font-medium hover:bg-blue-600 disabled:opacity-50">
              {analysePrice.isPending ? 'Running BuyerEdge price model…' : offerBand ? '↺ Re-run Price Analysis' : '▶ Run Price Analysis (BuyerEdge Methodology)'}
            </button>
            {analysePrice.isError && (
              <p className="mt-2 text-xs text-red-600">Analysis failed — check the browser console for details.</p>
            )}
          </div>
        )}

        {activeBidSessionId && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">💡 Bidding Strategy</h3>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                {strategy ? 'Live' : 'Awaiting price analysis'}
              </span>
            </div>
            <div className="p-4 space-y-4">
              {strategy ? (
                <>
                  <StrategyStep num={1} color={STEP_COLORS[0]} title="Opening offer"
                    amount={strategy.opening?.amount} rationale={strategy.opening?.rationale} />
                  <div className="border-t border-gray-100" />
                  <StrategyStep num={2} color={STEP_COLORS[1]} title={`Escalation — €2,500 increments to ${eur(strategy.escalation?.max_before_final)}`}
                    rationale={strategy.escalation?.rationale} />
                  <div className="border-t border-gray-100" />
                  <StrategyStep num={3} color={STEP_COLORS[2]} title="Best & Final"
                    amount={strategy.best_and_final?.amount} rationale={strategy.best_and_final?.rationale} />
                  <div className="border-t border-gray-100" />
                  <StrategyStep num={4} color={STEP_COLORS[3]} title="Walk away"
                    amount={strategy.walk_away?.ceiling} rationale={strategy.walk_away?.rationale} />
                </>
              ) : (
                <p className="text-sm text-gray-400 italic">Run price analysis above to generate your personalised 4-step bidding strategy.</p>
              )}
            </div>
          </div>
        )}

        {comparables.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">📈 Adjusted comparable sales</h3>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                {comparables.length} sales · 2km · 24mo
              </span>
            </div>
            <div className="p-4">
              {compStats && (
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    { label: 'P25', value: compStats.p25 },
                    { label: 'Median', value: compStats.median },
                    { label: 'Mean', value: compStats.mean },
                    { label: 'P75', value: compStats.p75 },
                  ].map(({ label, value }) => (
                    <div key={label} className="text-center bg-gray-50 rounded-lg py-1.5">
                      <div className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</div>
                      <div className="text-xs font-semibold text-gray-800">{eur(value)}</div>
                    </div>
                  ))}
                </div>
              )}
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" type="number" scale="time"
                    domain={[(d: number) => d - 30 * 86400000, (d: number) => d + 30 * 86400000]}
                    tickFormatter={tickFormatter} tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis dataKey="price" type="number"
                    tickFormatter={(v) => `€${Math.round(v / 1000)}k`}
                    tick={{ fontSize: 10 }} tickLine={false} width={50} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0].payload
                      return (
                        <div className="bg-white border border-gray-200 rounded-lg p-2 text-xs shadow-lg max-w-[200px]">
                          <div className="font-semibold text-gray-900 mb-1 truncate">{d.address}</div>
                          <div className="text-gray-600">Sale: {eur(d.rawPrice)}</div>
                          <div className="text-gray-600">Adjusted: {eur(d.price)}</div>
                          <div className="text-gray-400">{d.monthsAgo.toFixed(1)}mo ago · {Math.round(d.distanceM)}m away</div>
                        </div>
                      )
                    }}
                  />
                  {compStats && (
                    <ReferenceArea y1={compStats.p25} y2={compStats.p75}
                      fill="#10b981" fillOpacity={0.06}
                      stroke="#10b981" strokeOpacity={0.3} strokeWidth={1} />
                  )}
                  {ceiling > 0 && (
                    <ReferenceLine y={ceiling} stroke="#dc2626" strokeDasharray="4 3" strokeWidth={1.5}
                      label={{ value: `Ceiling ${eur(ceiling)}`, position: 'right', fontSize: 9, fill: '#dc2626' }} />
                  )}
                  <Scatter data={chartData} isAnimationActive={false}>
                    {chartData.map((d: any, i: number) => (
                      <Cell key={i} fill={dotColor(d)} opacity={0.85} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-1 flex-wrap">
                {[
                  { color: '#16a34a', label: 'Within ceiling' },
                  { color: '#3b82f6', label: 'Recent (6mo)' },
                  { color: '#94a3b8', label: 'Above ceiling' },
                ].map((l) => (
                  <div key={l.label} className="flex items-center gap-1.5 text-xs text-gray-500">
                    <div className="w-2 h-2 rounded-full" style={{ background: l.color }} />
                    {l.label}
                  </div>
                ))}
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <div className="w-3 h-2 rounded-sm" style={{ background: 'rgba(16,185,129,0.2)', border: '1px solid rgba(16,185,129,0.4)' }} />
                  P25–P75
                </div>
              </div>
              {compStats && ceiling > 0 && (
                <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800">
                  <strong>Key insight: </strong>
                  Your ceiling ({eur(ceiling)}) sits {ceiling >= compStats.p25 ? 'above' : 'below'} P25 ({eur(compStats.p25)})
                  {ceiling < compStats.median ? ` and below median (${eur(compStats.median)})` : ` and above median (${eur(compStats.median)})`}.
                  {ceiling < (offerBand?.entry ?? 0)
                    ? ` Market entry (${eur(offerBand!.entry)}) exceeds your ceiling — bid at ceiling as your Best & Final in round 1.`
                    : ' You are competitive in this price range.'}
                </div>
              )}
            </div>
          </div>
        )}

        {compLats.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">Comparable sales map</h3>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">2km · 24 months</span>
            </div>
            <div style={{ height: 280 }}>
              <MapContainer
                center={mapCenter}
                zoom={13}
                style={{ height: '100%', width: '100%' }}
                scrollWheelZoom={false}
              >
                <TileLayer
                  attribution='&copy; <a href="https://osm.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <Circle
                  center={mapCenter}
                  radius={2000}
                  pathOptions={{ color: '#64748b', fill: false, dashArray: '6 4', weight: 1, opacity: 0.4 }}
                />
                {/* Subject property pin — red star-like marker */}
                {propLat && propLng && (
                  <CircleMarker
                    center={[propLat, propLng]}
                    radius={9}
                    pathOptions={{ color: '#dc2626', fillColor: '#dc2626', fillOpacity: 1, weight: 2 }}
                  >
                    <Popup>
                      <div className="text-xs font-semibold text-red-700">This property</div>
                    </Popup>
                  </CircleMarker>
                )}
                {compLats.map((c: any, i: number) => {
                  const compPrice = c.time_adjusted_price ?? c.price_eur
                  const isRecent = c.months_ago < 6
                  const isInBudget = compPrice <= (ceiling || Infinity)
                  const color = !isInBudget ? '#94a3b8' : isRecent ? '#3b82f6' : '#16a34a'
                  return (
                    <CircleMarker key={i}
                      center={[c.latitude, c.longitude]}
                      radius={6}
                      pathOptions={{ color: '#fff', fillColor: color, fillOpacity: 0.85, weight: 1.5 }}>
                      <Popup>
                        <div className="text-xs">
                          <div className="font-semibold">{c.address}</div>
                          <div>Sale: {eur(c.price_eur)}</div>
                          {c.time_adjusted_price && <div>Adjusted: {eur(c.time_adjusted_price)}</div>}
                          <div className="text-gray-500">{c.months_ago.toFixed(1)} months ago · {Math.round(c.distance_m)}m away</div>
                        </div>
                      </Popup>
                    </CircleMarker>
                  )
                })}
              </MapContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
