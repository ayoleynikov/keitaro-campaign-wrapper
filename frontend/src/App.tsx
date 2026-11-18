import { useEffect, useState } from 'react'
import { api } from './api'
import { CreatorPage } from './pages/CreatorPage'
import { EditorPage } from './pages/EditorPage'
import './App.css'

type Tab = 'creator' | 'editor'

function App() {
  const [tab, setTab] = useState<Tab>('creator')
  const [mode, setMode] = useState('…')

  useEffect(() => {
    api.health().then((h) => setMode(h.keitaro_mode)).catch(() => setMode('unknown'))
  }, [])

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Keitaro Campaign Wrapper</h1>
          <p className="muted">Режим API: {mode}</p>
        </div>
        <nav>
          <button type="button" className={tab === 'creator' ? 'active' : ''} onClick={() => setTab('creator')}>
            Создание
          </button>
          <button type="button" className={tab === 'editor' ? 'active' : ''} onClick={() => setTab('editor')}>
            Редактор
          </button>
        </nav>
      </header>
      <main>{tab === 'creator' ? <CreatorPage /> : <EditorPage />}</main>
    </div>
  )
}

export default App