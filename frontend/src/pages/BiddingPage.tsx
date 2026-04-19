import { useState } from 'react'
import { useSessionStore } from '../store/sessionStore'
import {
  useCreateBidSession,
  useBidSession,
  useAddBid,
  useOfferBand,
  useAnalysePrice,
  useGenerateBidLetter,
} from '../api/bidding'

function formatEur(n: number | undefined) {
  return n ? `€${n.toLocaleString('en-IE')}` : '—'
}

export default function BiddingPage() {
  const { activePropertyId, activeBidSessionId, setActiveBidSession } = useSessionStore()
  const [budget, setBudget] = useState(325000)
  const [bidAmount, setBidAmount] = useState('')
  const [submittedBy, setSubmittedBy] = useState<'user' | 'other_buyer'>('user')

  const createSession = useCreateBidSession()
  const { data: session } = useBidSession(activeBidSessionId || undefined)
  const addBid = useAddBid(activeBidSessionId || '')
  const analysePrice = useAnalysePrice()
  const { data: offerBand } = useOfferBand(activePropertyId || undefined)
  const generateLetter = useGenerateBidLetter(activeBidSessionId || '')

  const handleCreateSession = () => {
    if (!activePropertyId) return
    createSession.mutate(
      { property_id: activePropertyId, user_max_budget: budget },
      { onSuccess: (s) => setActiveBidSession(s.id) }
    )
  }

  const handleAddBid = () => {
    const amount = parseInt(bidAmount.replace(/[^0-9]/g, ''))
    if (!amount || !activeBidSessionId) return
    addBid.mutate({ bid_amount: amount, submitted_by: submittedBy })
    setBidAmount('')
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Bidding Strategy</h1>

      {!activePropertyId && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          Select a property from Search to start a bidding session.
        </div>
      )}

      {activePropertyId && !activeBidSessionId && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Start Bidding Session</h2>
          <label className="block text-sm text-gray-700 mb-1">Your maximum budget (€)</label>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-4"
          />
          <button
            onClick={handleCreateSession}
            disabled={createSession.isPending}
            className="w-full py-2.5 rounded-xl bg-green-700 text-white font-medium hover:bg-green-600 disabled:opacity-50"
          >
            {createSession.isPending ? 'Starting…' : 'Start Session + Get AI Strategy'}
          </button>
        </div>
      )}

      {activeBidSessionId && (
        <>
          {/* Offer Band */}
          {offerBand && (
            <div className="grid grid-cols-3 gap-4 mb-6">
              {[
                { label: 'Entry Bid', value: offerBand.entry, color: 'bg-blue-50 border-blue-200 text-blue-900' },
                { label: 'Sealed Target', value: offerBand.sealed, color: 'bg-green-50 border-green-200 text-green-900' },
                { label: 'Ceiling', value: offerBand.ceiling, color: 'bg-red-50 border-red-200 text-red-900' },
              ].map((band) => (
                <div key={band.label} className={`rounded-xl border p-4 ${band.color}`}>
                  <p className="text-xs font-medium mb-1">{band.label}</p>
                  <p className="text-2xl font-bold">{formatEur(band.value)}</p>
                </div>
              ))}
            </div>
          )}

          {/* Analyse price button */}
          {!offerBand && (
            <button
              onClick={() => analysePrice.mutate({ property_id: activePropertyId! })}
              disabled={analysePrice.isPending}
              className="w-full py-2.5 rounded-xl bg-blue-700 text-white font-medium hover:bg-blue-600 disabled:opacity-50 mb-6"
            >
              {analysePrice.isPending ? 'Running price model…' : 'Run Price Analysis (BuyerEdge Methodology)'}
            </button>
          )}

          {/* Strategy advice */}
          {session?.strategy_advice && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">AI Bidding Strategy</h3>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{session.strategy_advice}</p>
            </div>
          )}

          {/* Bid timeline */}
          {session?.entries && session.entries.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
              <h3 className="font-semibold text-gray-900 mb-3">Live Bid Ladder</h3>
              <div className="space-y-2">
                {[...session.entries].reverse().map((entry: any) => (
                  <div key={entry.id} className="flex justify-between items-center text-sm">
                    <span className={entry.submitted_by === 'user' ? 'text-green-700 font-medium' : 'text-gray-600'}>
                      {entry.submitted_by === 'user' ? '👤 You' : '🏷 Other buyer'}
                    </span>
                    <span className="font-semibold">{formatEur(entry.bid_amount)}</span>
                    <span className="text-xs text-gray-400">{new Date(entry.submitted_at).toLocaleTimeString('en-IE')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Add bid */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Log a Bid</h3>
            <div className="flex gap-3 mb-3">
              <button
                onClick={() => setSubmittedBy('user')}
                className={`flex-1 py-2 rounded-lg text-sm ${submittedBy === 'user' ? 'bg-green-700 text-white' : 'border border-gray-300 text-gray-600'}`}
              >
                My bid
              </button>
              <button
                onClick={() => setSubmittedBy('other_buyer')}
                className={`flex-1 py-2 rounded-lg text-sm ${submittedBy === 'other_buyer' ? 'bg-gray-700 text-white' : 'border border-gray-300 text-gray-600'}`}
              >
                Competing bid
              </button>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={bidAmount}
                onChange={(e) => setBidAmount(e.target.value)}
                placeholder="€320,000"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <button
                onClick={handleAddBid}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-700"
              >
                Log
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
