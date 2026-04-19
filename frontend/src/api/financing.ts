import { useMutation, useQuery } from '@tanstack/react-query'
import { apiClient } from './client'

export const useFinancingSimulation = () =>
  useMutation({
    mutationFn: (data: {
      property_price: number
      aip_amount: number
      current_savings: number
      is_first_time_buyer?: boolean
      timeline_weeks?: number[]
      monthly_savings_rate?: number
    }) => apiClient.post('/financing/simulate', data).then((r) => r.data),
  })

export const useClosingCosts = (price: number | undefined) =>
  useQuery({
    queryKey: ['closing-costs', price],
    queryFn: () => apiClient.get(`/financing/closing-costs?price=${price}`).then((r) => r.data),
    enabled: !!price,
  })
