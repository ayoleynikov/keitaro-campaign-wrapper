import { useEffect, useState, type FormEvent } from 'react'
import { api, type Domain, type Group, type Offer, type TrafficSource } from '../api'

export function CreatorPage() {
  const [domains, setDomains] = useState<Domain[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [sources, setSources] = useState<TrafficSource[]>([])
  const [offerQuery, setOfferQuery] = useState('')
  const [offerOptions, setOfferOptions] = useState<Offer[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const [form, setForm] = useState({
    name: '',
    geo_iso: '',
    offer_id: '',
    domain_id: '',
    group_id: '',
    traffic_source_id: '',
  })

  useEffect(() => {
    Promise.all([api.domains(), api.groups(), api.trafficSources()])
      .then(([d, g, t]) => {
        setDomains(d)
        setGroups(g)
        setSources(t)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (offerQuery.trim().length < 1) {
      setOfferOptions([])
      return
    }
    const handle = setTimeout(() => {
      api.searchOffers(offerQuery).then(setOfferOptions).catch(() => setOfferOptions([]))
    }, 250)
    return () => clearTimeout(handle)
  }, [offerQuery])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setSubmitting(true)
    try {
      const payload = {
        name: form.name,
        geo_iso: form.geo_iso,
        offer_id: Number(form.offer_id),
        domain_id: Number(form.domain_id),
        group_id: Number(form.group_id),
        traffic_source_id: Number(form.traffic_source_id),
      }
      const res = await api.createCampaign(payload)
      setResult(`Кампания #${res.campaign_id} создана, операция #${res.operation_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка создания')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="muted">Загрузка справочников…</p>

  return (
    <section className="panel">
      <h2>Создание кампании</h2>
      <p className="muted">
        Обязательные поля: название, GEO (ISO), оффер, домен, группа, источник. Создаются 2 потока: GEO→Google,
        затем fallback-оффер. Ротация кампании: <code>position</code> (Keitaro Admin API).
      </p>
      <form className="form-grid" onSubmit={onSubmit}>
        <label>
          Название кампании
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Пример: Brand DE Q4"
          />
        </label>
        <label>
          GEO (ISO-3166 alpha-2)
          <input
            required
            maxLength={2}
            value={form.geo_iso}
            onChange={(e) => setForm({ ...form, geo_iso: e.target.value.toUpperCase() })}
            placeholder="DE"
          />
        </label>
        <label className="wide">
          Оффер (ID / поиск)
          <input
            list="offers"
            required
            value={offerQuery || form.offer_id}
            onChange={(e) => {
              setOfferQuery(e.target.value)
              if (/^\d+$/.test(e.target.value)) setForm({ ...form, offer_id: e.target.value })
            }}
            onBlur={() => {
              if (form.offer_id) setOfferQuery(form.offer_id)
            }}
            placeholder="5002 или имя оффера"
          />
          <datalist id="offers">
            {offerOptions.map((o) => (
              <option key={o.id} value={String(o.id)}>
                {o.name}
              </option>
            ))}
          </datalist>
        </label>
        <label>
          Домен
          <select
            required
            value={form.domain_id}
            onChange={(e) => setForm({ ...form, domain_id: e.target.value })}
          >
            <option value="">Выберите…</option>
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Группа кампаний
          <select
            required
            value={form.group_id}
            onChange={(e) => setForm({ ...form, group_id: e.target.value })}
          >
            <option value="">Выберите…</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Источник трафика
          <select
            required
            value={form.traffic_source_id}
            onChange={(e) => setForm({ ...form, traffic_source_id: e.target.value })}
          >
            <option value="">Выберите…</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <div className="wide actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Создание…' : 'Создать кампанию'}
          </button>
        </div>
      </form>
      {error && <p className="error">{error}</p>}
      {result && <p className="success">{result}</p>}
    </section>
  )
}