import { useState } from 'react'
import { useFinancingSimulation } from '../api/financing'
import { useFinancialProfile } from '../store/financialProfileStore'

function formatEur(n: number) {
  return `€${n.toLocaleString('en-IE')}`
}

function ProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100)
  const color = pct >= 75 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium w-8 text-right">{pct}%</span>
    </div>
  )
}

export default function FinancingPage() {
  const { aip, savings, isFirstTimeBuyer, setAip, setSavings, setIsFirstTimeBuyer } = useFinancialProfile()

  const [form, setForm] = useState({
    property_price: 325000,
    aip_amount: aip || 280000,
    current_savings: savings || 80000,
    monthly_savings_rate: 2000,
    is_first_time_buyer: isFirstTimeBuyer,
  })

  const simulate = useFinancingSimulation()

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Financing Scenarios</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          {[
            { label: 'Property price (€)', key: 'property_price' },
            { label: 'AIP amount (€)', key: 'aip_amount' },
            { label: 'Current savings (€)', key: 'current_savings' },
            { label: 'Monthly savings rate (€)', key: 'monthly_savings_rate' },
          ].map(({ label, key }) => (
            <div key={key}>
              <label className="block text-xs text-gray-600 mb-1">{label}</label>
              <input
                type="number"
                value={(form as any)[key]}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setForm((f) => ({ ...f, [key]: v }))
                  if (key === 'aip_amount') setAip(v)
                  if (key === 'current_savings') setSavings(v)
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm mb-4">
          <input
            type="checkbox"
            checked={form.is_first_time_buyer}
            onChange={(e) => {
              setForm((f) => ({ ...f, is_first_time_buyer: e.target.checked }))
              setIsFirstTimeBuyer(e.target.checked)
            }}
          />
          First-time buyer
        </label>
        <button
          onClick={() => simulate.mutate(form)}
          disabled={simulate.isPending}
          className="w-full py-2.5 rounded-xl bg-green-700 text-white font-medium hover:bg-green-600 disabled:opacity-50"
        >
          {simulate.isPending ? 'Simulating…' : 'Run Scenarios'}
        </button>
      </div>

      {simulate.data && (
        <>
          {/* Closing costs breakdown */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
            <h2 className="font-semibold text-gray-900 mb-3">One-off Closing Costs</h2>
            <div className="space-y-1.5 text-sm">
              {[
                ['Stamp duty (1%)', simulate.data.closing_costs.stamp_duty],
                ['Solicitor + land registry', simulate.data.closing_costs.solicitor_fee],
                ['Structural survey', simulate.data.closing_costs.surveyor_fee],
                ['Bank valuation + land reg fees', simulate.data.closing_costs.valuation_fee],
              ].map(([label, value]) => (
                <div key={label as string} className="flex justify-between">
                  <span className="text-gray-600">{label}</span>
                  <span className="font-medium">{formatEur(value as number)}</span>
                </div>
              ))}
              <div className="flex justify-between border-t border-gray-200 pt-1.5 font-semibold">
                <span>Total extras</span>
                <span>{formatEur(simulate.data.closing_costs.total)}</span>
              </div>
            </div>
          </div>

          {/* Scenarios */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
            <h2 className="font-semibold text-gray-900 mb-4">Timeline Scenarios</h2>
            <div className="space-y-4">
              {simulate.data.scenarios.map((s: any) => (
                <div key={s.timeline_weeks} className="border border-gray-100 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-gray-900">{s.timeline_weeks} weeks</span>
                    <span className="text-xs text-gray-500">Savings at close: {formatEur(s.savings_at_close)}</span>
                  </div>
                  <ProbBar prob={s.probability_of_success} />
                  <p className="text-xs text-gray-500 mt-2">{s.notes}</p>
                  {s.shortfall > 0 && (
                    <p className="text-xs text-red-600 mt-1">Shortfall: {formatEur(s.shortfall)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-900">
            <strong>Recommendation:</strong> {simulate.data.recommendation}
          </div>
        </>
      )}
    </div>
  )
}
