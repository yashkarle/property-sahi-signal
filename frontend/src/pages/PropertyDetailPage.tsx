import { useParams, useNavigate } from 'react-router-dom'
import { useProperty } from '../api/search'
import { useSessionStore } from '../store/sessionStore'

function Score({ label, value }: { label: string; value?: number }) {
  if (value === undefined || value === null) return null
  const pct = (value / 10) * 100
  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-green-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function PropertyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { setActiveProperty } = useSessionStore()
  const { data: prop, isLoading } = useProperty(id)

  if (isLoading) return <div className="p-6 text-gray-500 text-sm">Loading…</div>
  if (!prop) return <div className="p-6 text-gray-500 text-sm">Property not found</div>

  const warnings: string[] = []
  if (prop.heating_type === 'electric_storage') warnings.push('Electric storage heating — check upgrade cost')
  if (prop.year_built && prop.year_built >= 2000 && prop.year_built <= 2008 && prop.property_type !== 'house')
    warnings.push('Celtic Tiger era (2000-2008) — request fire safety certificate')
  if (!prop.carpet_area_sqm) warnings.push('Floor area missing — confirm carpet sqm at viewing')
  if (prop.management_fee_eur && prop.management_fee_eur > 2000)
    warnings.push(`High management fee €${prop.management_fee_eur?.toLocaleString('en-IE')}/yr`)

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-sm text-gray-500 hover:text-gray-700 mb-4">
        ← Back
      </button>

      <div className="flex justify-between items-start mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{prop.address || prop.title}</h1>
          <p className="text-sm text-gray-500">{prop.dublin_district} · {prop.estate_agent}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-green-700">€{prop.price?.toLocaleString('en-IE')}</p>
          <p className="text-xs text-gray-500">{prop.days_on_market} days on market</p>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Bedrooms', value: prop.bedrooms },
          { label: 'Bathrooms', value: prop.bathrooms },
          { label: 'Carpet area', value: prop.carpet_area_sqm ? `${prop.carpet_area_sqm}m²` : '—' },
          { label: 'BER', value: prop.ber_rating || '—' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-50 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-xs text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
          <h3 className="font-semibold text-amber-900 mb-2">⚠️ Watch-outs</h3>
          {warnings.map((w) => <p key={w} className="text-sm text-amber-800">• {w}</p>)}
        </div>
      )}

      {/* Badges */}
      <div className="flex flex-wrap gap-2 mb-6">
        {prop.is_chain_free && <span className="bg-blue-100 text-blue-800 text-xs px-2.5 py-1 rounded-full">Chain-free</span>}
        {prop.is_south_facing && <span className="bg-yellow-100 text-yellow-800 text-xs px-2.5 py-1 rounded-full">South-facing</span>}
        {prop.is_htb_eligible && <span className="bg-green-100 text-green-800 text-xs px-2.5 py-1 rounded-full">HTB eligible</span>}
        {prop.property_type && <span className="bg-gray-100 text-gray-700 text-xs px-2.5 py-1 rounded-full">{prop.property_type}</span>}
        {prop.heating_type && <span className={`text-xs px-2.5 py-1 rounded-full ${prop.heating_type === 'electric_storage' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}`}>{prop.heating_type}</span>}
      </div>

      {/* Description */}
      {prop.description && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="font-semibold text-gray-900 mb-2">Description</h3>
          <p className="text-sm text-gray-700 leading-relaxed">{prop.description}</p>
        </div>
      )}

      {/* Neighbourhood */}
      {prop.neighbourhood_score && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="font-semibold text-gray-900 mb-3">
            Neighbourhood Score
            {prop.neighbourhood_score.overall_score && (
              <span className="ml-2 text-green-700">{prop.neighbourhood_score.overall_score.toFixed(1)}/10</span>
            )}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <Score label="Connectivity (Luas/bus)" value={prop.neighbourhood_score.connectivity_score} />
            <Score label="Schools" value={prop.neighbourhood_score.schools_score} />
            <Score label="Amenities" value={prop.neighbourhood_score.amenities_score} />
            <Score label="Supermarkets" value={prop.neighbourhood_score.supermarkets_score} />
            <Score label="Parks" value={prop.neighbourhood_score.parks_score} />
            <Score label="Cafes" value={prop.neighbourhood_score.cafes_score} />
            <Score label="Safety" value={prop.neighbourhood_score.safety_score} />
            <Score label="M50/N11 access" value={prop.neighbourhood_score.m50_n11_score} />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => { setActiveProperty(prop.id); navigate('/viewing') }}
          className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-medium hover:bg-gray-50"
        >
          Prepare for Viewing
        </button>
        <button
          onClick={() => { setActiveProperty(prop.id); navigate('/bidding') }}
          className="flex-1 py-2.5 rounded-xl bg-green-700 text-white text-sm font-medium hover:bg-green-600"
        >
          Start Bidding Session
        </button>
      </div>
    </div>
  )
}
