import { useQuery, useMutation } from '@tanstack/react-query'
import { apiClient } from './client'

export const useViewingChecklist = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['viewing-checklist', propertyId],
    queryFn: () => apiClient.get(`/viewing/${propertyId}/checklist`).then((r) => r.data),
    enabled: !!propertyId,
  })

export const useAgentQuestions = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['agent-questions', propertyId],
    queryFn: () => apiClient.get(`/viewing/${propertyId}/questions`).then((r) => r.data),
    enabled: !!propertyId,
  })

export const useMissingData = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['missing-data', propertyId],
    queryFn: () => apiClient.get(`/viewing/${propertyId}/missing-data`).then((r) => r.data),
    enabled: !!propertyId,
  })

export const useEmailDraft = (propertyId: string) =>
  useMutation({
    mutationFn: (data: { agent_name: string; visit_date: string; additional_context?: string }) =>
      apiClient.post(`/viewing/${propertyId}/email-draft`, data).then((r) => r.data),
  })
