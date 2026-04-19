import { useState } from 'react'
import { useSessionStore } from '../store/sessionStore'
import { useViewingChecklist, useAgentQuestions, useMissingData, useEmailDraft } from '../api/viewing'

const PRIORITY_COLORS = {
  critical: 'border-l-red-500 bg-red-50',
  important: 'border-l-amber-500 bg-amber-50',
  nice_to_have: 'border-l-gray-300 bg-gray-50',
}

export default function ViewingPrepPage() {
  const { activePropertyId } = useSessionStore()
  const [agentName, setAgentName] = useState('')
  const [visitDate, setVisitDate] = useState('')
  const [showEmail, setShowEmail] = useState(false)

  const { data: checklist } = useViewingChecklist(activePropertyId || undefined)
  const { data: questions } = useAgentQuestions(activePropertyId || undefined)
  const { data: missingData } = useMissingData(activePropertyId || undefined)
  const emailDraft = useEmailDraft(activePropertyId || '')

  if (!activePropertyId) {
    return (
      <div className="p-6">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          Select a property from Search to see viewing prep materials.
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Viewing Prep</h1>

      {/* Risk flags */}
      {missingData?.risk_flags?.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <h3 className="font-semibold text-red-900 mb-2">⚠️ Critical Risk Flags</h3>
          {missingData.risk_flags.map((f: string) => (
            <p key={f} className="text-sm text-red-700">• {f}</p>
          ))}
        </div>
      )}

      {/* Checklist */}
      {checklist?.items && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Viewing Checklist</h2>
          <div className="space-y-2">
            {checklist.items.map((item: any, i: number) => (
              <div
                key={i}
                className={`border-l-4 pl-3 py-2 rounded-r-lg ${PRIORITY_COLORS[item.priority as keyof typeof PRIORITY_COLORS] || ''}`}
              >
                <div className="flex items-start gap-2">
                  <input type="checkbox" className="mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{item.item}</p>
                    <p className="text-xs text-gray-500">{item.category} · {item.priority}</p>
                    {item.rationale && <p className="text-xs text-gray-400 mt-0.5">{item.rationale}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Questions for agent */}
      {questions?.questions && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Questions for the Estate Agent</h2>
          <div className="space-y-3">
            {questions.questions.map((q: any, i: number) => (
              <div key={i} className="border border-gray-200 rounded-lg p-3">
                <p className="text-sm font-medium text-gray-800">{q.question}</p>
                <p className="text-xs text-gray-500 mt-1">{q.why_it_matters}</p>
                {q.red_flag_if && (
                  <p className="text-xs text-red-600 mt-1">🚩 Red flag: {q.red_flag_if}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Email draft */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Draft Follow-up Email</h2>
        <div className="flex gap-3 mb-3">
          <input
            type="text"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            placeholder="Agent name"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          <input
            type="date"
            value={visitDate}
            onChange={(e) => setVisitDate(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <button
          onClick={() => {
            emailDraft.mutate({ agent_name: agentName, visit_date: visitDate })
            setShowEmail(true)
          }}
          disabled={!agentName || !visitDate || emailDraft.isPending}
          className="w-full py-2.5 rounded-xl bg-gray-900 text-white font-medium hover:bg-gray-700 disabled:opacity-50"
        >
          {emailDraft.isPending ? 'Drafting…' : 'Generate Email Draft'}
        </button>
        {showEmail && emailDraft.data && (
          <div className="mt-4 border border-gray-200 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Subject: {emailDraft.data.subject}</p>
            <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans">{emailDraft.data.body}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
