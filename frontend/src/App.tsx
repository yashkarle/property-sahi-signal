import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import PropertyDetailPage from './pages/PropertyDetailPage'
import ViewingPrepPage from './pages/ViewingPrepPage'
import BiddingPage from './pages/BiddingPage'
import FinancingPage from './pages/FinancingPage'
import ProfessionalsPage from './pages/ProfessionalsPage'
import ComparisonPage from './pages/ComparisonPage'
import BidHistoryPage from './pages/BidHistoryPage'
import { useComparisonStore } from './store/comparisonStore'

const navItems = [
  { to: '/', label: 'Search', emoji: '🔍' },
  { to: '/viewing', label: 'Viewing', emoji: '🏠' },
  { to: '/bidding', label: 'Bidding', emoji: '⚡' },
  { to: '/bid-history', label: 'History', emoji: '📋' },
  { to: '/financing', label: 'Financing', emoji: '💶' },
  { to: '/professionals', label: 'Solicitors', emoji: '⚖️' },
]

export default function App() {
  const { selectedProperties } = useComparisonStore()

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        {/* Sidebar */}
        <aside className="w-56 bg-gray-900 text-white flex flex-col py-6 px-4">
          <div className="mb-8">
            <h1 className="text-lg font-bold text-green-400">Sahi Signal</h1>
            <p className="text-xs text-gray-400 mt-1">Dublin Property Assistant</p>
          </div>
          <nav className="flex flex-col gap-1 flex-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive ? 'bg-green-700 text-white' : 'text-gray-300 hover:bg-gray-800'
                  }`
                }
              >
                <span>{item.emoji}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>
          {selectedProperties.length > 0 && (
            <NavLink
              to="/compare"
              className="mt-4 flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-blue-800 text-white"
            >
              <span>⚖️</span>
              Compare ({selectedProperties.length})
            </NavLink>
          )}
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<SearchPage />} />
            <Route path="/property/:id" element={<PropertyDetailPage />} />
            <Route path="/viewing" element={<ViewingPrepPage />} />
            <Route path="/bidding" element={<BiddingPage />} />
            <Route path="/bid-history" element={<BidHistoryPage />} />
            <Route path="/financing" element={<FinancingPage />} />
            <Route path="/professionals" element={<ProfessionalsPage />} />
            <Route path="/compare" element={<ComparisonPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
