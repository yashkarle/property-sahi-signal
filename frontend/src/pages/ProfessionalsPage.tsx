import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'

type Tab = 'solicitors' | 'surveyors'

export default function ProfessionalsPage() {
  const [tab, setTab] = useState<Tab>('solicitors')

  const { data = [] } = useQuery<any[]>({
    queryKey: ['professionals', tab],
    queryFn: () => apiClient.get(`/professionals/${tab}`).then((r) => r.data),
  })

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Find a Professional</h1>
      <p className="text-sm text-gray-500 mb-6">Aggregated from SCSI and Engineers Ireland</p>

      <div className="flex gap-2 mb-6">
        {(['solicitors', 'surveyors'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize ${
              tab === t ? 'bg-gray-900 text-white' : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {data.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-3xl mb-3">⚖️</p>
            <p className="text-sm">No {tab} seeded yet — run <code>make seed-professionals</code></p>
          </div>
        )}
        {data.map((p: any) => (
          <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-4 flex justify-between items-start">
            <div>
              <p className="font-semibold text-gray-900 text-sm">{p.name || p.firm_name}</p>
              {p.firm_name && p.name && <p className="text-xs text-gray-500">{p.firm_name}</p>}
              <p className="text-xs text-gray-500 mt-0.5">{p.address}</p>
              {p.specialties?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {p.specialties.map((s: string) => (
                    <span key={s} className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">{s}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="text-right text-sm space-y-1">
              {p.phone && <p className="text-gray-600">{p.phone}</p>}
              {p.email && <a href={`mailto:${p.email}`} className="text-blue-600 hover:underline block">{p.email}</a>}
              {p.website && <a href={p.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline block text-xs">Website →</a>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
