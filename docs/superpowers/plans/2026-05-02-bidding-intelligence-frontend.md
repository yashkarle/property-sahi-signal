# Bidding Intelligence — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the BiddingPage as a split-panel intelligence console, add a BidHistoryPage with property comparison, wire a global financial profile (AIP + savings) into Zustand localStorage, and connect the FinancingPage to that shared store.

**Architecture:** Layout C split-panel (420px left / flexible right). Right panel has three sections stacked: 4-step strategy card → Recharts scatter chart → react-leaflet map. Global `financialProfileStore` persisted via Zustand `persist` middleware (built into zustand v5). All new API hooks go into `frontend/src/api/bidding.ts`.

**Tech Stack:** React 18, TypeScript, Zustand v5 (with persist), TanStack Query v5, Recharts 2.x, react-leaflet 4.x, Tailwind CSS

**Prerequisite:** The backend plan (`2026-05-02-bidding-intelligence-backend.md`) must be applied and the backend restarted before testing this plan.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/src/store/financialProfileStore.ts` | AIP + savings + FTB flag, persisted to localStorage; exports `buyerCeiling()` pure fn |
| Modify | `frontend/src/api/bidding.ts` | Add `useRecordOutcome`, `useBidHistory`, `useComparables` hooks |
| Modify | `frontend/src/pages/BiddingPage.tsx` | Full rewrite — split panel with all sections |
| Create | `frontend/src/pages/BidHistoryPage.tsx` | History + comparison table |
| Modify | `frontend/src/App.tsx` | Add `/bid-history` route + nav item |
| Modify | `frontend/src/pages/FinancingPage.tsx` | Pre-populate from financial profile store |

---

## Task 1: Financial Profile Store + buyerCeiling()

**Files:**
- Create: `frontend/src/store/financialProfileStore.ts`

- [ ] **Step 1: Create the store with persist middleware**

Create `frontend/src/store/financialProfileStore.ts`:

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface FinancialProfile {
  aip: number
  savings: number
  isFirstTimeBuyer: boolean
  setAip: (v: number) => void
  setSavings: (v: number) => void
  setIsFirstTimeBuyer: (v: boolean) => void
}

export const useFinancialProfile = create<FinancialProfile>()(
  persist(
    (set) => ({
      aip: 0,
      savings: 0,
      isFirstTimeBuyer: true,
      setAip: (v) => set({ aip: v }),
      setSavings: (v) => set({ savings: v }),
      setIsFirstTimeBuyer: (v) => set({ isFirstTimeBuyer: v }),
    }),
    { name: 'financial-profile' }
  )
)

/**
 * Compute the buyer's hard ceiling.
 *
 * Formula:
 *   ltv_ceiling   = floor(aip / 0.9)                 for FTBs  (90% LTV)
 *                 = floor(aip / 0.8)                 for non-FTBs (80% LTV)
 *   closing_costs = round(ltv_ceiling * 0.01) + 4500  (stamp 1% + solicitor + land reg + survey/val)
 *   affordability = aip + savings - closing_costs
 *   ceiling       = min(ltv_ceiling, affordability)  rounded down to nearest €1,000
 */
export function buyerCeiling(
  aip: number,
  savings: number,
  isFirstTimeBuyer: boolean
): number {
  if (!aip || !savings) return 0
  const ltvRatio = isFirstTimeBuyer ? 0.9 : 0.8
  const ltvCeiling = Math.floor(aip / ltvRatio)
  const closingCosts = Math.round(ltvCeiling * 0.01) + 4500
  const affordability = aip + savings - closingCosts
  const ceiling = Math.min(ltvCeiling, affordability)
  return Math.floor(ceiling / 1000) * 1000
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/yashkarle/git/property-sahi-signal/frontend && npx tsc --noEmit 2>&1 | grep -i "financialProfileStore\|error" | head -10
```

Expected: no errors mentioning financialProfileStore.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/financialProfileStore.ts
git commit -m "feat(frontend): add financialProfileStore with buyerCeiling() persisted to localStorage"
```

---

## Task 2: New API Hooks

**Files:**
- Modify: `frontend/src/api/bidding.ts`

- [ ] **Step 1: Read the current bidding.ts and add three new hooks**

The current file ends after `useGenerateBidLetter`. Append these exports:

```typescript
export const useRecordOutcome = (sessionId: string) =>
  useMutation<any, Error, { outcome: 'won' | 'lost' | 'withdrawn'; actual_sale_price?: number }>({
    mutationFn: (req) =>
      apiClient.patch(`/bidding/sessions/${sessionId}/outcome`, req).then((r) => r.data),
  })

export const useBidHistory = () =>
  useQuery({
    queryKey: ['bid-history'],
    queryFn: () => apiClient.get('/bidding/history').then((r) => r.data),
  })

export const useComparables = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['comparables', propertyId],
    queryFn: () => apiClient.get(`/pricing/${propertyId}/comparables`).then((r) => r.data),
    enabled: !!propertyId,
    staleTime: 5 * 60 * 1000,  // comparables don't change frequently
  })
```

The full `frontend/src/api/bidding.ts` after the addition:

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from './client'

export const useCreateBidSession = () =>
  useMutation({
    mutationFn: (data: { property_id: string; user_max_budget: number; user_aip?: number; user_savings?: number }) =>
      apiClient.post('/bidding/sessions', data).then((r) => r.data),
  })

export const useBidSession = (sessionId: string | undefined) =>
  useQuery({
    queryKey: ['bid-session', sessionId],
    queryFn: () => apiClient.get(`/bidding/sessions/${sessionId}`).then((r) => r.data),
    enabled: !!sessionId,
    refetchInterval: 30000,
  })

export const useAddBid = (sessionId: string) =>
  useMutation({
    mutationFn: (data: { bid_amount: number; submitted_by: string; notes?: string }) =>
      apiClient.post(`/bidding/sessions/${sessionId}/bids`, data).then((r) => r.data),
  })

export const usePriceModel = (sessionId: string | undefined) =>
  useQuery({
    queryKey: ['price-model', sessionId],
    queryFn: () => apiClient.get(`/bidding/sessions/${sessionId}/price-model`).then((r) => r.data),
    enabled: !!sessionId,
  })

export const useOfferBand = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['offer-band', propertyId],
    queryFn: () => apiClient.get(`/pricing/${propertyId}/offer-band`).then((r) => r.data),
    enabled: !!propertyId,
    retry: false,
    staleTime: 0,
  })

export const useAnalysePrice = () =>
  useMutation({
    mutationFn: (data: { property_id: string; subjective_inputs?: object; buyer_aip?: number; buyer_savings?: number }) =>
      apiClient.post('/pricing/analyse', data).then((r) => r.data),
  })

export const useGenerateBidLetter = (sessionId: string) =>
  useMutation({
    mutationFn: (data: { user_bid: number; competing_bid?: number; additional_context?: string }) =>
      apiClient.post(`/bidding/sessions/${sessionId}/bid-letter`, data).then((r) => r.data),
  })

export const useRecordOutcome = (sessionId: string) =>
  useMutation<any, Error, { outcome: 'won' | 'lost' | 'withdrawn'; actual_sale_price?: number }>({
    mutationFn: (req) =>
      apiClient.patch(`/bidding/sessions/${sessionId}/outcome`, req).then((r) => r.data),
  })

export const useBidHistory = () =>
  useQuery({
    queryKey: ['bid-history'],
    queryFn: () => apiClient.get('/bidding/history').then((r) => r.data),
  })

export const useComparables = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['comparables', propertyId],
    queryFn: () => apiClient.get(`/pricing/${propertyId}/comparables`).then((r) => r.data),
    enabled: !!propertyId,
    staleTime: 5 * 60 * 1000,
  })
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/yashkarle/git/property-sahi-signal/frontend && npx tsc --noEmit 2>&1 | grep "bidding.ts" | head -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/bidding.ts
git commit -m "feat(frontend): add useRecordOutcome, useBidHistory, useComparables hooks"
```

---

## Task 3: Full BiddingPage Rewrite

**Files:**
- Modify: `frontend/src/pages/BiddingPage.tsx`

- [ ] **Step 1: Install leaflet CSS (required for react-leaflet maps)**

Verify `frontend/src/index.css` or `frontend/src/main.tsx` imports leaflet CSS. If not present, add to `frontend/src/main.tsx`:

```typescript
import 'leaflet/dist/leaflet.css'
```

Check: `grep -n "leaflet" /Users/yashkarle/git/property-sahi-signal/frontend/src/main.tsx`

If missing, add it as the first import line.

- [ ] **Step 2: Fix leaflet default marker icon (known react-leaflet issue)**

Create `frontend/src/lib/leafletFix.ts`:

```typescript
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Fix default marker icons broken by webpack/vite bundling
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})
```

Import it in `frontend/src/main.tsx` after the leaflet CSS import:
```typescript
import './lib/leafletFix'
```

- [ ] **Step 3: Write the full BiddingPage**

Replace the entire content of `frontend/src/pages/BiddingPage.tsx`:

```tsx
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

function SignalBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="text-xs text-gray-600 w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-bold w-10 text-right" style={{ color }}>{value}</span>
    </div>
  )
}

function StrategyStep({
  num, color, title, amount, rationale,
}: { num: number; color: string; title: string; amount: number; rationale: string }) {
  return (
    <div className="flex gap-3">
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5"
        style={{ background: color }}
      >
        {num}
      </div>
      <div>
        <div className="text-sm font-bold text-gray-900">{title} — {eur(amount)}</div>
        <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{rationale}</div>
      </div>
    </div>
  )
}

const STEP_COLORS = ['#1e40af', '#0369a1', '#0d9488', '#dc2626']

export default function BiddingPage() {
  const { activePropertyId, activeBidSessionId, setActiveBidSession } = useSessionStore()
  const { aip, savings, isFirstTimeBuyer, setAip, setSavings } = useFinancialProfile()
  const ceiling = buyerCeiling(aip, savings, isFirstTimeBuyer)

  const [bidAmount, setBidAmount] = useState('')
  const [submittedBy, setSubmittedBy] = useState<'user' | 'other_buyer'>('user')
  const [showOutcome, setShowOutcome] = useState(false)
  const [outcomePrice, setOutcomePrice] = useState('')

  const queryClient = useQueryClient()
  const createSession = useCreateBidSession()
  const { data: session } = useBidSession(activeBidSessionId ?? undefined)
  const addBid = useAddBid(activeBidSessionId ?? '')
  const analysePrice = useAnalysePrice()
  const { data: offerBand } = useOfferBand(
    (session?.property_id ?? activePropertyId) ?? undefined
  )
  const { data: comparables = [] } = useComparables(
    (session?.property_id ?? activePropertyId) ?? undefined
  )
  const recordOutcome = useRecordOutcome(activeBidSessionId ?? '')

  const propertyId = session?.property_id ?? activePropertyId

  const handleCreateSession = () => {
    if (!activePropertyId) return
    createSession.mutate(
      {
        property_id: activePropertyId,
        user_max_budget: ceiling || aip,
        user_aip: aip || undefined,
        user_savings: savings || undefined,
      },
      { onSuccess: (s) => setActiveBidSession(s.id) }
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

  // Parse strategy JSON if available
  let strategy: any = null
  try {
    if (session?.strategy_advice) strategy = JSON.parse(session.strategy_advice)
  } catch { /* invalid JSON — show raw text below */ }

  // Chart data
  const chartData = comparables.map((c: any) => ({
    date: new Date(c.date_of_sale).getTime(),
    price: c.time_adjusted_price ?? c.price_eur,
    rawPrice: c.price_eur,
    address: c.address,
    distanceM: c.distance_m,
    monthsAgo: c.months_ago,
  }))

  const tickFormatter = (ts: number) =>
    new Date(ts).toLocaleDateString('en-IE', { month: 'short', year: '2-digit' })

  const now = Date.now()
  const sixMonthsAgo = now - 6 * 30 * 24 * 60 * 60 * 1000
  const dotColor = (d: any) => {
    if (d.price > (ceiling || Infinity)) return '#94a3b8'
    if (d.date >= sixMonthsAgo) return '#3b82f6'
    return '#16a34a'
  }

  // Map: subject property
  const subjectLat = session?.property_id ? undefined : undefined
  const compLats = comparables.filter((c: any) => c.latitude && c.longitude)

  return (
    <div className="flex h-full overflow-hidden">

      {/* ═══ LEFT PANEL ═══ */}
      <div className="w-[420px] flex-shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-y-auto">

        {/* No property selected */}
        {!activePropertyId && !session && (
          <div className="p-6">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
              Select a property from Search to start a bidding session.
            </div>
          </div>
        )}

        {/* Session start form */}
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
                <span className="text-gray-600">Your ceiling (90% LTV): </span>
                <span className="font-bold text-red-700">{eur(ceiling)}</span>
                <span className="text-gray-400 text-xs ml-2">
                  = {eur(aip)} AIP + {eur(savings)} savings − closing costs
                </span>
              </div>
            )}

            <button onClick={handleCreateSession} disabled={createSession.isPending || !activePropertyId}
              className="w-full py-2.5 rounded-xl bg-green-700 text-white font-medium hover:bg-green-600 disabled:opacity-50">
              {createSession.isPending ? 'Starting…' : 'Start Session + Generate Strategy'}
            </button>
          </div>
        )}

        {/* Active session */}
        {activeBidSessionId && session && (
          <>
            {/* Financial strip */}
            <div className="grid grid-cols-3 border-b border-gray-100">
              {[
                { label: 'AIP', value: eur(session.user_aip ?? aip || undefined), color: '#1e40af' },
                { label: 'Savings', value: eur(session.user_savings ?? savings || undefined), color: '#16a34a' },
                { label: 'Your ceiling', value: eur(ceiling || session.user_max_budget || undefined), color: '#dc2626' },
              ].map((cell) => (
                <div key={cell.label} className="px-4 py-3 border-r border-gray-100 last:border-r-0">
                  <div className="text-[10px] text-gray-400 uppercase tracking-wide">{cell.label}</div>
                  <div className="text-base font-bold mt-0.5" style={{ color: cell.color }}>{cell.value}</div>
                </div>
              ))}
            </div>

            {/* Warning banner */}
            {offerBand && ceiling && offerBand.entry > ceiling && (
              <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex gap-2">
                <span className="text-amber-600 flex-shrink-0">⚠️</span>
                <p className="text-xs text-amber-800 leading-relaxed">
                  <strong>Market entry ({eur(offerBand.entry)}) exceeds your ceiling by {eur(offerBand.entry - ceiling)}.</strong>
                  {' '}Bid at ceiling as your Best & Final — see strategy →
                </p>
              </div>
            )}

            {/* Market signals */}
            {offerBand && (
              <div className="px-4 py-3 border-b border-gray-100">
                <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Market signals</div>
                <SignalBar label="Sealed bid prob." value={`${Math.round((offerBand.sealed_bid_probability ?? 0) * 100)}%` as any} max={100} color={(offerBand.sealed_bid_probability ?? 0) > 0.6 ? '#dc2626' : '#f97316'} />
                <SignalBar label="Seller leverage" value={offerBand.seller_leverage_score ?? 0} max={5} color="#f97316" />
                <SignalBar label="Over-asking prob." value={`${Math.round((offerBand.over_asking_probability ?? 0) * 100)}%` as any} max={100} color="#f97316" />
              </div>
            )}

            {/* Bid ladder */}
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

            {/* Log bid */}
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

            {/* Outcome recording */}
            <div className="px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-2">Record outcome</div>
              {!showOutcome ? (
                <div className="flex gap-2">
                  {(['won', 'lost', 'withdrawn'] as const).map((o) => (
                    <button key={o} onClick={() => { setShowOutcome(true) }}
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

        {/* Price analysis trigger */}
        {activeBidSessionId && !offerBand && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <button
              onClick={() => propertyId && analysePrice.mutate(
                { property_id: propertyId, buyer_aip: session?.user_aip ?? aip || undefined, buyer_savings: session?.user_savings ?? savings || undefined },
                { onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offer-band'] }) }
              )}
              disabled={analysePrice.isPending || !propertyId}
              className="w-full py-2.5 rounded-xl bg-blue-700 text-white font-medium hover:bg-blue-600 disabled:opacity-50">
              {analysePrice.isPending ? 'Running BuyerEdge price model…' : '▶ Run Price Analysis (BuyerEdge Methodology)'}
            </button>
            {analysePrice.isError && (
              <p className="mt-2 text-xs text-red-600">Analysis failed — check the browser console for details.</p>
            )}
          </div>
        )}

        {/* 4-step strategy */}
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
                    amount={strategy.escalation?.max_before_final} rationale={strategy.escalation?.rationale} />
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

        {/* Comparables scatter chart */}
        {comparables.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">📈 Adjusted comparable sales</h3>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                {comparables.length} sales · 1km · 18mo
              </span>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="date" type="number" scale="time"
                    domain={['auto', 'auto']}
                    tickFormatter={tickFormatter}
                    tick={{ fontSize: 10 }} tickLine={false}
                  />
                  <YAxis
                    dataKey="price" type="number"
                    tickFormatter={(v) => `€${Math.round(v / 1000)}k`}
                    tick={{ fontSize: 10 }} tickLine={false} width={50}
                  />
                  <Tooltip
                    formatter={(v: number) => eur(v)}
                    labelFormatter={(ts: number) => new Date(ts).toLocaleDateString('en-IE')}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0].payload
                      return (
                        <div className="bg-white border border-gray-200 rounded-lg p-2 text-xs shadow-lg max-w-[200px]">
                          <div className="font-semibold text-gray-900 mb-1 truncate">{d.address}</div>
                          <div className="text-gray-600">Price: {eur(d.rawPrice)}</div>
                          <div className="text-gray-600">Adjusted: {eur(d.price)}</div>
                          <div className="text-gray-400">{d.monthsAgo.toFixed(1)}mo ago · {Math.round(d.distanceM)}m away</div>
                        </div>
                      )
                    }}
                  />
                  {/* P25–P75 band */}
                  {offerBand?.p25 && offerBand?.p75 && (
                    <ReferenceArea y1={offerBand.p25} y2={offerBand.p75}
                      fill="#10b981" fillOpacity={0.06}
                      stroke="#10b981" strokeOpacity={0.3} strokeWidth={1} />
                  )}
                  {/* Ceiling line */}
                  {ceiling > 0 && (
                    <ReferenceLine y={ceiling} stroke="#dc2626" strokeDasharray="4 3" strokeWidth={1.5}
                      label={{ value: `Ceiling ${eur(ceiling)}`, position: 'right', fontSize: 9, fill: '#dc2626' }} />
                  )}
                  {/* Asking line */}
                  {session && (
                    <ReferenceLine y={session.property?.price ?? undefined} stroke="#f97316" strokeDasharray="4 3" strokeWidth={1}
                      label={{ value: 'Asking', position: 'right', fontSize: 9, fill: '#f97316' }} />
                  )}
                  <Scatter data={chartData} isAnimationActive={false}>
                    {chartData.map((d: any, i: number) => (
                      <Cell key={i} fill={dotColor(d)} opacity={0.85} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
              {/* Legend */}
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

              {/* Insight box */}
              {offerBand?.p25 && ceiling > 0 && (
                <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800">
                  <strong>Key insight: </strong>
                  Your ceiling ({eur(ceiling)}) sits {ceiling >= offerBand.p25 ? 'above' : 'below'} P25 ({eur(offerBand.p25)})
                  {ceiling < (offerBand.p50 ?? Infinity) ? ` and below P50 (${eur(offerBand.p50)})` : ''}.
                  {ceiling < (offerBand.entry ?? 0)
                    ? ` Market entry (${eur(offerBand.entry)}) exceeds your ceiling — bid at ceiling as your Best & Final in round 1.`
                    : ' You are competitive in this price range.'}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Leaflet map */}
        {compLats.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="text-sm font-bold text-gray-900">🗺 Comparable sales map</h3>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">1km radius</span>
            </div>
            <div style={{ height: 280 }}>
              <MapContainer
                center={[compLats[0].latitude, compLats[0].longitude]}
                zoom={14}
                style={{ height: '100%', width: '100%' }}
                scrollWheelZoom={false}
              >
                <TileLayer
                  attribution='&copy; <a href="https://osm.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {/* 1km radius circle around subject (approx centre of comparables) */}
                <Circle
                  center={[compLats[0].latitude, compLats[0].longitude]}
                  radius={1000}
                  color="#64748b" fill={false} dashArray="6 4" weight={1} opacity={0.4}
                />
                {/* Comparable pins */}
                {compLats.map((c: any, i: number) => {
                  const isRecent = c.months_ago < 6
                  const isInBudget = c.price_eur <= (ceiling || Infinity)
                  const color = !isInBudget ? '#94a3b8' : isRecent ? '#3b82f6' : '#16a34a'
                  return (
                    <CircleMarker key={i}
                      center={[c.latitude, c.longitude]}
                      radius={6} color="#fff" fillColor={color} fillOpacity={0.85} weight={1.5}>
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
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd /Users/yashkarle/git/property-sahi-signal/frontend && npx tsc --noEmit 2>&1 | grep "BiddingPage" | head -10
```

Expected: no errors in BiddingPage.tsx.

- [ ] **Step 5: Start both servers and test in browser**

```bash
# Terminal 1 (if not already running)
cd /Users/yashkarle/git/property-sahi-signal/backend && python3.11 -m uvicorn app.main:app --reload --port 8000
# Terminal 2 (if not already running — use port 5174)
cd /Users/yashkarle/git/property-sahi-signal/frontend && npm run dev
```

Open http://localhost:5174/bidding. Navigate to a property → View Details → Bidding. Verify:
- AIP/Savings inputs appear in session start form
- Ceiling calculates live as you type
- After session creation: financial strip, market signals, bid ladder all render

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/BiddingPage.tsx frontend/src/main.tsx frontend/src/lib/leafletFix.ts
git commit -m "feat(frontend): rewrite BiddingPage as split-panel with strategy, chart, and map"
```

---

## Task 4: BidHistoryPage

**Files:**
- Create: `frontend/src/pages/BidHistoryPage.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/BidHistoryPage.tsx`:

```tsx
import { useState } from 'react'
import { useBidHistory } from '../api/bidding'
import { buyerCeiling } from '../store/financialProfileStore'

function eur(n: number | null | undefined) {
  return n != null ? `€${n.toLocaleString('en-IE')}` : '—'
}

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-orange-100 text-orange-700',
  won: 'bg-green-100 text-green-700',
  lost: 'bg-red-100 text-red-700',
  withdrawn: 'bg-gray-100 text-gray-500',
}

const STATUS_LABEL: Record<string, string> = {
  active: '🔴 Active',
  won: '🎉 Won',
  lost: '❌ Lost',
  withdrawn: '↩ Withdrawn',
}

function comparisonInsight(items: any[]): string {
  const insights: string[] = []

  // Cash buyer flag
  const lostToCash = items.find(
    (i) => i.status === 'lost' &&
           i.actual_sale_price != null &&
           i.your_max_bid != null &&
           i.actual_sale_price < i.your_max_bid
  )
  if (lostToCash) {
    insights.push(
      `You bid ${eur(lostToCash.your_max_bid)} on ${lostToCash.property.address?.split(',')[0]} but lost at ${eur(lostToCash.actual_sale_price)} — likely a cash buyer or faster chain. ` +
      `Cash buyers can beat a higher mortgage bid on speed-to-close. Always ask the agent if cash buyers are in the pool.`
    )
  }

  // Sealed bid warning for active
  const activeHighSealed = items.find(
    (i) => i.status === 'active' && (i.latest_price_model?.sealed_bid_probability ?? 0) > 0.65
  )
  if (activeHighSealed) {
    const prob = Math.round((activeHighSealed.latest_price_model?.sealed_bid_probability ?? 0) * 100)
    insights.push(
      `${activeHighSealed.property.address?.split(',')[0]} has a ${prob}% sealed-bid probability — ` +
      `put in your Best & Final at ceiling in round 1 rather than incrementally escalating.`
    )
  }

  if (insights.length === 0) {
    insights.push('No patterns detected yet. Record more bids and outcomes to surface insights.')
  }

  return insights.join(' ')
}

export default function BidHistoryPage() {
  const { data: history = [], isLoading } = useBidHistory()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const selected = history.filter((i: any) => selectedIds.has(i.session_id))

  // Summary stats
  const active = history.filter((i: any) => i.status === 'active').length
  const won = history.filter((i: any) => i.status === 'won').length
  const lost = history.filter((i: any) => i.status === 'lost').length

  const outcomesWithPrice = history.filter(
    (i: any) => i.actual_sale_price && i.your_max_bid && i.status !== 'active'
  )
  const avgDelta = outcomesWithPrice.length > 0
    ? Math.round(outcomesWithPrice.reduce((sum: number, i: any) => sum + ((i.actual_sale_price - i.your_max_bid) / i.your_max_bid) * 100, 0) / outcomesWithPrice.length * 10) / 10
    : null

  if (isLoading) return <div className="p-6 text-gray-400 text-sm">Loading bid history…</div>

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Bid History</h1>
      <p className="text-sm text-gray-500 mb-6">All properties tracked — bids, outcomes, and final prices</p>

      {/* Summary stats */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {[
          { label: 'Properties', value: history.length, color: '#0f172a' },
          { label: 'Active', value: active, color: '#f97316' },
          { label: 'Won', value: won, color: '#16a34a' },
          { label: 'Lost', value: lost, color: '#dc2626' },
          { label: 'Avg vs your bid', value: avgDelta != null ? `${avgDelta > 0 ? '+' : ''}${avgDelta}%` : '—', color: '#64748b' },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">{s.label}</div>
            <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {history.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">🏠</p>
          <p className="text-sm">No bid history yet. Start a bidding session from the Search page.</p>
        </div>
      )}

      {/* Property list */}
      <div className="space-y-2 mb-8">
        {/* Header */}
        {history.length > 0 && (
          <div className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr_120px] px-4 pb-1 gap-3">
            {['Property', 'Asking', 'Your max bid', 'Status', 'Final price', 'Compare'].map((h) => (
              <div key={h} className="text-[10px] uppercase tracking-wider text-gray-400">{h}</div>
            ))}
          </div>
        )}

        {history.map((item: any) => {
          const isSelected = selectedIds.has(item.session_id)
          return (
            <div key={item.session_id}
              className={`bg-white border rounded-xl overflow-hidden ${
                item.status === 'active' ? 'border-l-4 border-l-orange-400 border-gray-200' :
                item.status === 'won' ? 'border-l-4 border-l-green-500 border-gray-200' :
                item.status === 'lost' ? 'border-l-4 border-l-red-400 border-gray-200' :
                'border-l-4 border-l-gray-300 border-gray-200'
              }`}>
              <div className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr_120px] items-center px-4 py-3 gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900 leading-tight">
                    {item.property.address ?? item.property.url}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {[item.property.bedrooms && `${item.property.bedrooms} bed`,
                      item.property.carpet_area_sqm && `${item.property.carpet_area_sqm}m²`,
                      item.property.ber_rating && `BER ${item.property.ber_rating}`,
                      item.property.dublin_district,
                    ].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <div className="text-sm font-semibold">{eur(item.property.price)}</div>
                <div className="text-sm font-semibold text-red-700">{eur(item.your_max_bid ?? item.user_max_budget)}</div>
                <div>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLES[item.status]}`}>
                    {STATUS_LABEL[item.status]}
                  </span>
                </div>
                <div className="text-sm font-semibold text-gray-600">{eur(item.actual_sale_price)}</div>
                <div>
                  <button onClick={() => toggleSelect(item.session_id)}
                    className={`w-full py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                      isSelected
                        ? 'bg-blue-700 text-white border-blue-700'
                        : 'border-gray-200 text-gray-600 hover:border-blue-400'
                    }`}>
                    {isSelected ? '✓ In compare' : '+ Compare'}
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Comparison table */}
      {selected.length >= 2 && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center">
            <h2 className="text-base font-bold text-gray-900">Property Comparison · {selected.length} selected</h2>
            <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">AI-summarised differences</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-5 py-2.5 text-left text-xs uppercase tracking-wider text-gray-400 font-medium w-40">Dimension</th>
                  {selected.map((item: any) => (
                    <th key={item.session_id} className="px-5 py-2.5 text-left text-xs font-medium text-gray-700">
                      {item.property.address?.split(',')[0] ?? 'Property'}
                      {' '}
                      <span className={`ml-1 px-1.5 py-0.5 rounded text-xs ${STATUS_STYLES[item.status]}`}>
                        {STATUS_LABEL[item.status]}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    label: 'Asking price',
                    fn: (i: any) => eur(i.property.price),
                  },
                  {
                    label: 'Your max bid',
                    fn: (i: any) => eur(i.your_max_bid ?? i.user_max_budget),
                  },
                  {
                    label: 'Beds / Size',
                    fn: (i: any) => [i.property.bedrooms && `${i.property.bedrooms} bed`, i.property.carpet_area_sqm && `${i.property.carpet_area_sqm}m²`].filter(Boolean).join(' · ') || '—',
                  },
                  {
                    label: 'BER rating',
                    fn: (i: any) => i.property.ber_rating ?? '—',
                  },
                  {
                    label: 'Sealed bid prob.',
                    fn: (i: any) => i.latest_price_model?.sealed_bid_probability != null
                      ? `${Math.round(i.latest_price_model.sealed_bid_probability * 100)}%`
                      : '—',
                  },
                  {
                    label: 'PPR P25 (floor)',
                    fn: (i: any) => eur(i.latest_price_model?.p25),
                  },
                  {
                    label: 'District',
                    fn: (i: any) => i.property.dublin_district ?? '—',
                  },
                  {
                    label: 'Final price',
                    fn: (i: any) => eur(i.actual_sale_price),
                  },
                  {
                    label: 'Cash buyer risk',
                    fn: (i: any) => i.status === 'lost' && i.actual_sale_price != null && i.your_max_bid != null && i.actual_sale_price < i.your_max_bid
                      ? '⚠️ Confirmed' : 'Unknown',
                  },
                ].map((row) => (
                  <tr key={row.label} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-xs text-gray-500 font-medium">{row.label}</td>
                    {selected.map((item: any) => (
                      <td key={item.session_id} className="px-5 py-2.5 text-sm font-semibold text-gray-900">
                        {row.fn(item)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Insight */}
          <div className="mx-4 mb-4 mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800 leading-relaxed">
            <strong className="block mb-1">🤖 Key differences</strong>
            {comparisonInsight(selected)}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/yashkarle/git/property-sahi-signal/frontend && npx tsc --noEmit 2>&1 | grep "BidHistory" | head -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/BidHistoryPage.tsx
git commit -m "feat(frontend): add BidHistoryPage with summary stats and comparison table"
```

---

## Task 5: App.tsx Routing + Nav

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Read App.tsx and add the bid history route + nav item**

In `frontend/src/App.tsx`:

1. Add import: `import BidHistoryPage from './pages/BidHistoryPage'`

2. Add to `navItems` array (after bidding):
```typescript
{ to: '/bid-history', label: 'History', emoji: '📋' },
```

3. Add to `<Routes>`:
```tsx
<Route path="/bid-history" element={<BidHistoryPage />} />
```

- [ ] **Step 2: Verify in browser**

Navigate to http://localhost:5174/bid-history. Expect: history page with summary stats.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): add /bid-history route and nav item"
```

---

## Task 6: Update FinancingPage to Use Financial Profile Store

**Files:**
- Modify: `frontend/src/pages/FinancingPage.tsx`

- [ ] **Step 1: Read FinancingPage.tsx and update to use shared store**

In `frontend/src/pages/FinancingPage.tsx`:

1. Add import at top:
```typescript
import { useFinancialProfile } from '../store/financialProfileStore'
```

2. Inside `FinancingPage()`, before the existing `const [form, setForm]`, add:
```typescript
const { aip, savings, isFirstTimeBuyer, setAip, setSavings, setIsFirstTimeBuyer } = useFinancialProfile()
```

3. Replace the existing `useState` initializer for `form`:
```typescript
const [form, setForm] = useState({
  property_price: 325000,
  aip_amount: aip || 280000,
  current_savings: savings || 80000,
  monthly_savings_rate: 2000,
  is_first_time_buyer: isFirstTimeBuyer,
})
```

4. In the `onChange` handlers for `aip_amount` and `current_savings`, also update the global store:

For the `aip_amount` input:
```tsx
onChange={(e) => {
  const v = Number(e.target.value)
  setForm((f) => ({ ...f, aip_amount: v }))
  setAip(v)
}}
```

For the `current_savings` input:
```tsx
onChange={(e) => {
  const v = Number(e.target.value)
  setForm((f) => ({ ...f, current_savings: v }))
  setSavings(v)
}}
```

For the FTB checkbox:
```tsx
onChange={(e) => {
  setForm((f) => ({ ...f, is_first_time_buyer: e.target.checked }))
  setIsFirstTimeBuyer(e.target.checked)
}}
```

- [ ] **Step 2: Build check**

```bash
cd /Users/yashkarle/git/property-sahi-signal/frontend && npm run build 2>&1 | grep -i "error" | grep -v "node_modules" | head -10
```

Expected: no errors in FinancingPage.tsx.

- [ ] **Step 3: Smoke test — navigate Financing → Bidding, AIP should pre-populate**

1. Open http://localhost:5174/financing
2. Enter AIP = 370000, Savings = 50000
3. Navigate to /bidding → start a new session
4. Verify: AIP field shows 370000, Savings shows 50000

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/FinancingPage.tsx
git commit -m "feat(frontend): pre-populate FinancingPage from shared financialProfileStore"
```

---

## Self-Review

| Spec requirement | Covered |
|------------------|---------|
| Global financial profile persisted to localStorage | Task 1 (Zustand persist) ✅ |
| `buyerCeiling()` pure function (Central Bank LTV + closing costs formula) | Task 1 ✅ |
| FTB 90% LTV / non-FTB 80% LTV handling | Task 1 ✅ |
| AIP + savings captured in session start form | Task 3 (BiddingPage session start) ✅ |
| Financial strip (AIP / Savings / Ceiling) on active session | Task 3 ✅ |
| Warning banner when market entry > ceiling | Task 3 ✅ |
| Market signals bars | Task 3 ✅ |
| Live bid ladder | Task 3 ✅ |
| Outcome recording (Won/Lost/Withdrawn + price input) | Task 3 ✅ |
| 4-step strategy rendered from JSON | Task 3 (StrategyStep component) ✅ |
| Comparables scatter chart with reference lines + P25-P75 band | Task 3 (Recharts ScatterChart) ✅ |
| Leaflet map with colour-coded pins + 1km circle | Task 3 (react-leaflet) ✅ |
| Dot colours: grey=above ceiling, green=in budget, blue=recent | Task 3 (dotColor fn) ✅ |
| Key insight box below chart | Task 3 ✅ |
| `useRecordOutcome`, `useBidHistory`, `useComparables` hooks | Task 2 ✅ |
| BidHistoryPage with 5 summary stats | Task 4 ✅ |
| Property list with status badges + compare toggle | Task 4 ✅ |
| Comparison table for ≥2 selected properties | Task 4 ✅ |
| Rule-based comparison insight (cash buyer flag, sealed bid warning) | Task 4 (comparisonInsight fn) ✅ |
| /bid-history route + nav item | Task 5 ✅ |
| FinancingPage pre-populated from store | Task 6 ✅ |
| AIP/savings written back to store when changed in FinancingPage | Task 6 ✅ |
