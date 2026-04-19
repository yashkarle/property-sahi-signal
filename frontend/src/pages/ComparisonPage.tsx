import { useComparisonStore } from '../store/comparisonStore'
import { useCompareProperties } from '../api/search'

export default function ComparisonPage() {
  const { selectedProperties, removeProperty, clearAll } = useComparisonStore()
  const compare = useCompareProperties()

  const handleCompare = () => {
    compare.mutate({ property_ids: selectedProperties.map((p) => p.id) })
  }

  if (selectedProperties.length < 2) {
    return (
      <div className="p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          Select 2-3 properties from Search to compare them side by side.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Property Comparison</h1>
        <div className="flex gap-2">
          <button onClick={clearAll} className="text-sm px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            Clear all
          </button>
          <button
            onClick={handleCompare}
            disabled={compare.isPending}
            className="text-sm px-4 py-2 bg-green-700 text-white rounded-lg hover:bg-green-600 disabled:opacity-50"
          >
            {compare.isPending ? 'Analysing…' : 'Get AI Comparison'}
          </button>
        </div>
      </div>

      {/* Side-by-side cards */}
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: `repeat(${selectedProperties.length}, 1fr)` }}>
        {selectedProperties.map((prop) => (
          <div key={prop.id} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-sm font-semibold text-gray-900 leading-tight">{prop.address || prop.title}</h3>
              <button onClick={() => removeProperty(prop.id)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
            </div>
            <p className="text-xl font-bold text-green-700 mb-3">€{prop.price?.toLocaleString('en-IE')}</p>
            <div className="space-y-1 text-xs text-gray-600">
              <div className="flex justify-between"><span>Bedrooms</span><span className="font-medium">{prop.bedrooms}</span></div>
              <div className="flex justify-between"><span>Bathrooms</span><span className="font-medium">{prop.bathrooms}</span></div>
              <div className="flex justify-between"><span>Carpet area</span><span className="font-medium">{prop.carpet_area_sqm ? `${prop.carpet_area_sqm}m²` : '—'}</span></div>
              <div className="flex justify-between"><span>BER</span><span className="font-medium">{prop.ber_rating || '—'}</span></div>
              <div className="flex justify-between"><span>Heating</span><span className={`font-medium ${prop.heating_type === 'electric_storage' ? 'text-red-600' : ''}`}>{prop.heating_type || '—'}</span></div>
              <div className="flex justify-between"><span>Chain-free</span><span className="font-medium">{prop.is_chain_free ? '✓' : '✗'}</span></div>
              <div className="flex justify-between"><span>Days live</span><span className="font-medium">{prop.days_on_market || '—'}</span></div>
              {prop.price && prop.carpet_area_sqm && (
                <div className="flex justify-between border-t border-gray-100 pt-1">
                  <span className="font-medium">€/m²</span>
                  <span className="font-bold text-gray-900">€{Math.round(prop.price / prop.carpet_area_sqm).toLocaleString('en-IE')}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* AI comparison summary */}
      {compare.data && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-3">AI Analysis</h2>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{compare.data.summary}</p>
        </div>
      )}
    </div>
  )
}
