import { create } from 'zustand'

interface SessionStore {
  activePropertyId: string | null
  activeBidSessionId: string | null
  setActiveProperty: (id: string | null) => void
  setActiveBidSession: (id: string | null) => void
}

export const useSessionStore = create<SessionStore>((set) => ({
  activePropertyId: null,
  activeBidSessionId: null,
  setActiveProperty: (id) => set({ activePropertyId: id, activeBidSessionId: null }),
  setActiveBidSession: (id) => set({ activeBidSessionId: id }),
}))
