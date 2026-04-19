import axios from 'axios'

const API_KEY = import.meta.env.VITE_API_KEY || 'change-me-in-production'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API error:', error.response?.data)
    return Promise.reject(error)
  }
)
