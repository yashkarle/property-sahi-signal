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
