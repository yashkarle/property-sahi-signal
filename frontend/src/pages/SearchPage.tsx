import { useState } from 'react'
import { useSearchProperties } from '../api/search'
import { useComparisonStore } from '../store/comparisonStore'
import { useSessionStore } from '../store/sessionStore'
import { useNavigate } from 'react-router-dom'
import type { PropertySummary, SearchFilters } from '../types/property'

const DUBLIN_DISTRICTS = ['D1','D2','D3','D4','D6','D6W','D7','D8','D9','D10','D11','D12','D14','D15','D16','D18','D20','D22','D24']
const PROPERTY_TYPES = ['apartment','duplex','house','own_door_apartment']
const BER_RATINGS = ['A1','A2','A3','B1','B2','B3','C1','C2','D1','E1','F','G']

function formatPrice(p: number | undefined) {
  return p ? `€${p.toLocaleString('en-IE')}` : '—'
}

function PropertyCard({ prop }: { prop: PropertySummary }) {
  const { addProperty, removeProperty, selectedProperties } = useComparisonStore()
  const { setActiveProperty } = useSessionStore()
  const navigate = useNavigate()
  const isSelected = selectedProperties.some((p) => p.id === prop.id)

  const warnings: string[] = []
  if (prop.heating_type === 'electric_storage') warnings.push('⚠️ Electric storage heating')
  if ((prop.missing_data_flags || []).includes('carpet_area_sqm')) warnings.push('❗ Missing floor area')
  if (prop.bathrooms === 1) warnings.push('⚠️ Only 1 bathroom')

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm leading-tight">
            {prop.address || prop.title || 'Unknown address'}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">{prop.dublin_district} · {prop.estate_agent}</p>
        </div>
        <span className="text-lg font-bold text-green-700">{formatPrice(prop.price)}</span>
      </div>

      <div className="flex gap-3 text-xs text-gray-600 mb-2">
        <span>{prop.bedrooms}🛏</span>
        <span>{prop.bathrooms}🚿</span>
        {prop.carpet_area_sqm && <span>{prop.carpet_area_sqm}m²</span>}
        {prop.ber_rating && <span className="bg-green-100 text-green-800 px-1.5 rounded">BER {prop.ber_rating}</span>}
        {prop.is_chain_free && <span className="bg-blue-100 text-blue-800 px-1.5 rounded">Chain-free</span>}
      </div>

      {warnings.length > 0 && (
        <div className="mb-2">
          {warnings.map((w) => (
            <p key={w} className="text-xs text-amber-600">{w}</p>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-3">
        <button
          onClick={() => { setActiveProperty(prop.id); navigate(`/property/${prop.id}`) }}
          className="flex-1 text-xs py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700"
        >
          View Details
        </button>
        <button
          onClick={() => isSelected ? removeProperty(prop.id) : addProperty(prop)}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
            isSelected ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-600 hover:border-blue-400'
          }`}
        >
          {isSelected ? '✓ Compare' : '+ Compare'}
        </button>
      </div>
    </div>
  )
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<SearchFilters>({
    price_max: 375000,
    bedrooms_min: 2,
    bathrooms_min: 2,
    carpet_area_sqm_min: 70,
    exclude_electric_storage: true,
  })
  const { mutate: search, data, isPending } = useSearchProperties(null)

  const handleSearch = () => {
    if (!query.trim()) return
    search({ query, filters, limit: 20 })
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Property Search</h1>
        <p className="text-sm text-gray-500">Semantic search across Dublin listings — describe what you want</p>
      </div>

      {/* Search bar */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder='e.g. "turnkey 2-bed apartment near Luas in D12 with gas heating"'
          className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        />
        <button
          onClick={handleSearch}
          disabled={isPending}
          className="px-6 py-2.5 rounded-xl bg-green-700 text-white text-sm font-medium hover:bg-green-600 disabled:opacity-50"
        >
          {isPending ? 'Searching…' : 'Search'}
        </button>
      </div>

      {/* Quick filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        <select
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white"
          onChange={(e) => setFilters((f) => ({ ...f, price_max: Number(e.target.value) }))}
          defaultValue="375000"
        >
          <option value="325000">Max €325k</option>
          <option value="350000">Max €350k</option>
          <option value="375000">Max €375k</option>
          <option value="400000">Max €400k</option>
        </select>
        <select
          className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white"
          onChange={(e) => setFilters((f) => ({ ...f, carpet_area_sqm_min: Number(e.target.value) }))}
          defaultValue="70"
        >
          <option value="60">≥60m²</option>
          <option value="70">≥70m² (min)</option>
          <option value="80">≥80m²</option>
        </select>
        <label className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white cursor-pointer">
          <input
            type="checkbox"
            checked={filters.exclude_electric_storage ?? true}
            onChange={(e) => setFilters((f) => ({ ...f, exclude_electric_storage: e.target.checked }))}
          />
          Exclude electric storage
        </label>
        <label className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-300 bg-white cursor-pointer">
          <input
            type="checkbox"
            checked={filters.is_chain_free ?? false}
            onChange={(e) => setFilters((f) => ({ ...f, is_chain_free: e.target.checked || undefined }))}
          />
          Chain-free only
        </label>
      </div>

      {/* Results */}
      {data && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            {data.total} results · {data.query_time_ms}ms
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.results.map((prop: PropertySummary) => (
              <PropertyCard key={prop.id} prop={prop} />
            ))}
          </div>
        </div>
      )}

      {!data && !isPending && (
        <div className="text-center py-20 text-gray-400">
          <p className="text-4xl mb-4">🏠</p>
          <p className="text-sm">Describe your ideal property above to get started</p>
        </div>
      )}
    </div>
  )
}
