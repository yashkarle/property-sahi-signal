export interface PropertySummary {
  id: string
  url: string
  title?: string
  address?: string
  dublin_district?: string
  price?: number
  bedrooms?: number
  bathrooms?: number
  carpet_area_sqm?: number
  property_type?: string
  ber_rating?: string
  heating_type?: string
  is_chain_free?: boolean
  is_south_facing?: boolean
  is_htb_eligible?: boolean
  days_on_market?: number
  estate_agent?: string
  latitude?: number
  longitude?: number
  is_active: boolean
  missing_data_flags?: string[]
}

export interface NeighbourhoodScore {
  safety_score?: number
  amenities_score?: number
  connectivity_score?: number
  schools_score?: number
  parks_score?: number
  cafes_score?: number
  supermarkets_score?: number
  m50_n11_score?: number
  overall_score?: number
  commute_dundrum_min?: number
}

export interface PropertyDetail extends PropertySummary {
  eircode?: string
  year_built?: number
  management_fee_eur?: number
  seller_status?: string
  description?: string
  features_list?: string[]
  price_history?: { price: number; date: string; type: string }[]
  neighbourhood_score?: NeighbourhoodScore
}

export interface SearchFilters {
  price_min?: number
  price_max?: number
  bedrooms_min?: number
  bathrooms_min?: number
  carpet_area_sqm_min?: number
  property_types?: string[]
  ber_ratings?: string[]
  heating_types?: string[]
  dublin_districts?: string[]
  is_chain_free?: boolean
  is_htb_eligible?: boolean
  days_on_market_max?: number
  exclude_electric_storage?: boolean
}

export interface SearchRequest {
  query: string
  filters?: SearchFilters
  limit?: number
  offset?: number
}

export interface SearchResponse {
  results: PropertySummary[]
  total: number
  search_id: string
  query_time_ms: number
}

export interface CompareResponse {
  summary: string
  properties: PropertySummary[]
  comparison_table: Record<string, Record<string, unknown>>
}
