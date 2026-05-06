import { useState } from 'react'
import { useBidHistory } from '../api/bidding'

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
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
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
    ? Math.round(
        outcomesWithPrice.reduce(
          (sum: number, i: any) => sum + ((i.actual_sale_price - i.your_max_bid) / i.your_max_bid) * 100,
          0
        ) / outcomesWithPrice.length * 10
      ) / 10
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
                  { label: 'Asking price', fn: (i: any) => eur(i.property.price) },
                  { label: 'Your max bid', fn: (i: any) => eur(i.your_max_bid ?? i.user_max_budget) },
                  { label: 'Beds / Size', fn: (i: any) => [i.property.bedrooms && `${i.property.bedrooms} bed`, i.property.carpet_area_sqm && `${i.property.carpet_area_sqm}m²`].filter(Boolean).join(' · ') || '—' },
                  { label: 'BER rating', fn: (i: any) => i.property.ber_rating ?? '—' },
                  { label: 'Sealed bid prob.', fn: (i: any) => i.latest_price_model?.sealed_bid_probability != null ? `${Math.round(i.latest_price_model.sealed_bid_probability * 100)}%` : '—' },
                  { label: 'PPR P25 (floor)', fn: (i: any) => eur(i.latest_price_model?.p25) },
                  { label: 'District', fn: (i: any) => i.property.dublin_district ?? '—' },
                  { label: 'Final price', fn: (i: any) => eur(i.actual_sale_price) },
                  { label: 'Cash buyer risk', fn: (i: any) => i.status === 'lost' && i.actual_sale_price != null && i.your_max_bid != null && i.actual_sale_price < i.your_max_bid ? '⚠️ Confirmed' : 'Unknown' },
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
