export type Domain = { id: number; name: string }
export type Group = { id: number; name: string }
export type TrafficSource = { id: number; name: string }
export type Offer = { id: number; name: string }

export type WorkspaceOffer = {
  offer_id: number
  share: number
  lifecycle: string
  is_pinned: boolean
  pinned_share?: number | null
  is_new_unpublished: boolean
  can_bring_back: boolean
  removed_origin: string
  state_label?: string | null
}

export type StreamWorkspace = {
  keitaro_stream_id: number
  keitaro_campaign_id: number
  name: string
  has_offers: boolean
  sync_state: 'clean' | 'dirty'
  offers: WorkspaceOffer[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    throw new Error(detail || res.statusText)
  }
  return body as T
}

export const api = {
  health: () => request<{ status: string; keitaro_mode: string }>('/api/health'),
  domains: () => request<Domain[]>('/api/references/domains'),
  groups: () => request<Group[]>('/api/references/groups'),
  trafficSources: () => request<TrafficSource[]>('/api/references/traffic-sources'),
  searchOffers: (q: string) => request<Offer[]>(`/api/references/offers/search?q=${encodeURIComponent(q)}`),
  listCampaigns: () => request<{ id: number; name: string }[]>('/api/campaigns'),
  createCampaign: (payload: Record<string, unknown>) =>
    request<{ operation_id: number; campaign_id: number; streams: unknown[] }>('/api/campaigns', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  fetchStreams: (campaignId: number) =>
    request<StreamWorkspace[]>(`/api/campaigns/${campaignId}/fetch-streams`, { method: 'POST' }),
  getWorkspace: (streamId: number) => request<StreamWorkspace>(`/api/streams/${streamId}/workspace`),
  addOffer: (streamId: number, offerId: number) =>
    request<StreamWorkspace>(`/api/streams/${streamId}/offers`, {
      method: 'POST',
      body: JSON.stringify({ offer_id: offerId }),
    }),
  removeOffer: (streamId: number, offerId: number) =>
    request<StreamWorkspace>(`/api/streams/${streamId}/offers/${offerId}`, { method: 'DELETE' }),
  restoreOffer: (streamId: number, offerId: number) =>
    request<StreamWorkspace>(`/api/streams/${streamId}/offers/${offerId}/restore`, { method: 'POST' }),
  pinOffer: (streamId: number, offerId: number, share?: number) =>
    request<StreamWorkspace>(`/api/streams/${streamId}/offers/${offerId}/pin`, {
      method: 'POST',
      body: JSON.stringify(share != null ? { share } : {}),
    }),
  unpinOffer: (streamId: number, offerId: number) =>
    request<StreamWorkspace>(`/api/streams/${streamId}/offers/${offerId}/pin`, { method: 'DELETE' }),
  cancel: (streamId: number) => request<StreamWorkspace>(`/api/streams/${streamId}/cancel`, { method: 'POST' }),
  push: (streamId: number) => request<StreamWorkspace>(`/api/streams/${streamId}/push`, { method: 'POST' }),
}