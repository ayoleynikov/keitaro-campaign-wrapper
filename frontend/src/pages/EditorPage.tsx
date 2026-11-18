import { useEffect, useState, type FormEvent } from 'react'
import { api, type Offer, type StreamWorkspace, type WorkspaceOffer } from '../api'

export function EditorPage() {
  const [campaigns, setCampaigns] = useState<{ id: number; name: string }[]>([])
  const [campaignId, setCampaignId] = useState('')
  const [workspaces, setWorkspaces] = useState<StreamWorkspace[]>([])
  const [streamId, setStreamId] = useState('')
  const [workspace, setWorkspace] = useState<StreamWorkspace | null>(null)
  const [offerQuery, setOfferQuery] = useState('')
  const [offerOptions, setOfferOptions] = useState<Offer[]>([])
  const [newOfferId, setNewOfferId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  useEffect(() => {
    api.listCampaigns().then(setCampaigns).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (offerQuery.trim().length < 1) {
      setOfferOptions([])
      return
    }
    const t = setTimeout(() => api.searchOffers(offerQuery).then(setOfferOptions).catch(() => []), 250)
    return () => clearTimeout(t)
  }, [offerQuery])

  async function loadWorkspace(id: number) {
    const ws = await api.getWorkspace(id)
    setWorkspace(ws)
  }

  async function fetchFromKt() {
    if (!campaignId) return
    setBusy(true)
    setError(null)
    try {
      const list = await api.fetchStreams(Number(campaignId))
      setWorkspaces(list.filter((w) => w.has_offers))
      if (list.length) {
        const offerWs = list.find((w) => w.has_offers) ?? list[0]
        setStreamId(String(offerWs.keitaro_stream_id))
        setWorkspace(offerWs)
      }
      setInfo('Fetch Streams: синхронизация с Keitaro выполнена')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка fetch')
    } finally {
      setBusy(false)
    }
  }

  async function onSelectStream(id: string) {
    setStreamId(id)
    if (!id) {
      setWorkspace(null)
      return
    }
    try {
      await loadWorkspace(Number(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Нет workspace — сделайте Fetch Streams')
    }
  }

  async function run(action: () => Promise<StreamWorkspace>, okMessage: string) {
    setBusy(true)
    setError(null)
    setInfo(null)
    try {
      const ws = await action()
      setWorkspace(ws)
      setWorkspaces((prev) =>
        prev.map((w) => (w.keitaro_stream_id === ws.keitaro_stream_id ? ws : w)),
      )
      setInfo(okMessage)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  function onAdd(e: FormEvent) {
    e.preventDefault()
    const id = Number(newOfferId)
    if (!streamId || !id) return
    setOfferQuery('')
    return run(() => api.addOffer(Number(streamId), id), 'Оффер добавлен, доли пересчитаны')
  }

  function rowClass(o: WorkspaceOffer): string {
    if (o.lifecycle !== 'active') return 'row-muted'
    if (workspace?.sync_state === 'dirty') return 'row-draft'
    return 'row-clean'
  }

  return (
    <section className="panel">
      <h2>Редактор потоков (как в референс-видео)</h2>
      <p className="muted">
        Fetch → локальный черновик → Push to KT. Cancel откатывает к baseline. Локальный Remove — серая строка,
        state пустой; отсутствие в KT после Fetch — state <code>removed</code>. См. docs/ASSUMPTIONS.md.
      </p>

      <div className="form-grid">
        <label className="wide">
          Кампания
          <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
            <option value="">Выберите…</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                #{c.id} {c.name}
              </option>
            ))}
          </select>
        </label>
        <div className="wide actions">
          <button type="button" disabled={!campaignId || busy} onClick={fetchFromKt}>
            Fetch Streams from KT
          </button>
        </div>
        <label className="wide">
          Поток (offers)
          <select value={streamId} onChange={(e) => onSelectStream(e.target.value)} disabled={!workspaces.length}>
            <option value="">Выберите…</option>
            {workspaces.map((w) => (
              <option key={w.keitaro_stream_id} value={w.keitaro_stream_id}>
                #{w.keitaro_stream_id} {w.name} [{w.sync_state}]
              </option>
            ))}
          </select>
        </label>
      </div>

      {workspace && (
        <>
          <p className={workspace.sync_state === 'dirty' ? 'warn' : 'success'}>
            Заголовок потока: {workspace.sync_state === 'dirty' ? 'жёлтый (не синхронизировано)' : 'белый (синхронизировано)'}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Offer ID</th>
                  <th>Share %</th>
                  <th>State</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {workspace.offers.map((o) => (
                  <tr key={o.offer_id} className={rowClass(o)}>
                    <td>{o.offer_id}</td>
                    <td>
                      {o.is_pinned && <span title="pinned">📌 </span>}
                      {o.share}
                    </td>
                    <td>
                      {o.state_label ? (
                        <span className="state-removed">{o.state_label}</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="actions">
                      {o.lifecycle === 'active' && (
                        <>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() =>
                              run(
                                () => api.pinOffer(workspace.keitaro_stream_id, o.offer_id, o.share),
                                `Закреплено ${o.share}%`,
                              )
                            }
                            disabled={busy}
                          >
                            Pin
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() =>
                              run(() => api.removeOffer(workspace.keitaro_stream_id, o.offer_id), 'Remove (локально)')
                            }
                            disabled={busy}
                          >
                            Remove
                          </button>
                        </>
                      )}
                      {o.can_bring_back && (
                        <button
                          type="button"
                          onClick={() =>
                            run(
                              () => api.restoreOffer(workspace.keitaro_stream_id, o.offer_id),
                              'Bring back',
                            )
                          }
                          disabled={busy}
                        >
                          Bring back
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form className="form-grid" onSubmit={onAdd}>
            <label className="wide">
              Добавить оффер (ID / поиск)
              <input
                list="editor-offers"
                value={newOfferId || offerQuery}
                onChange={(e) => {
                  setOfferQuery(e.target.value)
                  if (/^\d+$/.test(e.target.value)) setNewOfferId(e.target.value)
                }}
                placeholder="ID оффера"
              />
              <datalist id="editor-offers">
                {offerOptions.map((o) => (
                  <option key={o.id} value={String(o.id)}>
                    {o.name}
                  </option>
                ))}
              </datalist>
            </label>
            <div className="actions wide">
              <button type="submit" disabled={busy || !newOfferId}>
                Add offer
              </button>
            </div>
          </form>

          <div className="actions">
            <button
              type="button"
              onClick={() => run(() => api.push(workspace.keitaro_stream_id), 'Push to KT')}
              disabled={busy || workspace.sync_state !== 'dirty'}
            >
              Push to KT
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => run(() => api.cancel(workspace.keitaro_stream_id), 'Cancel')}
              disabled={busy || workspace.sync_state !== 'dirty'}
            >
              Cancel
            </button>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}
      {info && <p className="success">{info}</p>}
    </section>
  )
}