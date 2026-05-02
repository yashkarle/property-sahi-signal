import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from './client'

export const useCreateBidSession = () =>
  useMutation({
    mutationFn: (data: { property_id: string; user_max_budget: number; user_aip?: number; user_savings?: number }) =>
      apiClient.post('/bidding/sessions', data).then((r) => r.data),
  })

export const useBidSession = (sessionId: string | undefined) =>
  useQuery({
    queryKey: ['bid-session', sessionId],
    queryFn: () => apiClient.get(`/bidding/sessions/${sessionId}`).then((r) => r.data),
    enabled: !!sessionId,
    refetchInterval: 30000,
  })

export const useAddBid = (sessionId: string) =>
  useMutation({
    mutationFn: (data: { bid_amount: number; submitted_by: string; notes?: string }) =>
      apiClient.post(`/bidding/sessions/${sessionId}/bids`, data).then((r) => r.data),
  })

export const usePriceModel = (sessionId: string | undefined) =>
  useQuery({
    queryKey: ['price-model', sessionId],
    queryFn: () => apiClient.get(`/bidding/sessions/${sessionId}/price-model`).then((r) => r.data),
    enabled: !!sessionId,
  })

export const useOfferBand = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['offer-band', propertyId],
    queryFn: () => apiClient.get(`/pricing/${propertyId}/offer-band`).then((r) => r.data),
    enabled: !!propertyId,
    retry: false,
    staleTime: 0,
  })

export const useAnalysePrice = () =>
  useMutation({
    mutationFn: (data: { property_id: string; subjective_inputs?: object; buyer_aip?: number; buyer_savings?: number }) =>
      apiClient.post('/pricing/analyse', data).then((r) => r.data),
  })

export const useGenerateBidLetter = (sessionId: string) =>
  useMutation({
    mutationFn: (data: { user_bid: number; competing_bid?: number; additional_context?: string }) =>
      apiClient.post(`/bidding/sessions/${sessionId}/bid-letter`, data).then((r) => r.data),
  })

export const useRecordOutcome = (sessionId: string) =>
  useMutation<any, Error, { outcome: 'won' | 'lost' | 'withdrawn'; actual_sale_price?: number }>({
    mutationFn: (req) =>
      apiClient.patch(`/bidding/sessions/${sessionId}/outcome`, req).then((r) => r.data),
  })

export const useBidHistory = () =>
  useQuery({
    queryKey: ['bid-history'],
    queryFn: () => apiClient.get('/bidding/history').then((r) => r.data),
  })

export const useComparables = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['comparables', propertyId],
    queryFn: () => apiClient.get(`/pricing/${propertyId}/comparables`).then((r) => r.data),
    enabled: !!propertyId,
    staleTime: 5 * 60 * 1000,
  })
