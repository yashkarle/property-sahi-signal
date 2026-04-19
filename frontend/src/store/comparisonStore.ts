import { create } from 'zustand'
import type { PropertySummary } from '../types/property'

interface ComparisonStore {
  selectedProperties: PropertySummary[]
  addProperty: (prop: PropertySummary) => void
  removeProperty: (id: string) => void
  clearAll: () => void
}

export const useComparisonStore = create<ComparisonStore>((set) => ({
  selectedProperties: [],
  addProperty: (prop) =>
    set((state) => {
      if (state.selectedProperties.length >= 3) return state
      if (state.selectedProperties.find((p) => p.id === prop.id)) return state
      return { selectedProperties: [...state.selectedProperties, prop] }
    }),
  removeProperty: (id) =>
    set((state) => ({
      selectedProperties: state.selectedProperties.filter((p) => p.id !== id),
    })),
  clearAll: () => set({ selectedProperties: [] }),
}))
