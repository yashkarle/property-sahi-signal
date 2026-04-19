import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from './client'
import type { SearchRequest, SearchResponse, PropertyDetail, CompareResponse } from '../types/property'

export const useSearchProperties = (request: SearchRequest | null) =>
  useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: (req) => apiClient.post('/search/semantic', req).then((r) => r.data),
  })

export const useProperty = (id: string | undefined) =>
  useQuery<PropertyDetail>({
    queryKey: ['property', id],
    queryFn: () => apiClient.get(`/search/properties/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useNeighbourhoodScore = (id: string | undefined) =>
  useQuery({
    queryKey: ['neighbourhood', id],
    queryFn: () => apiClient.get(`/search/properties/${id}/neighbourhood`).then((r) => r.data),
    enabled: !!id,
  })

export const useCompareProperties = () =>
  useMutation<CompareResponse, Error, { property_ids: string[] }>({
    mutationFn: (req) => apiClient.post('/search/properties/compare', req).then((r) => r.data),
  })
