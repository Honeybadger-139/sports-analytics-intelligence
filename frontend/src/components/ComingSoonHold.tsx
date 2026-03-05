import { useNavigate } from 'react-router-dom'
import { findSportOption, isLiveDataSelection } from '../config/sports'
import { useSportContext } from '../context/SportContext'

interface ComingSoonHoldProps {
  section: string
}

export default function ComingSoonHold({ section }: ComingSoonHoldProps) {
  const navigate = useNavigate()
  const { selection, setSport, setLeague } = useSportContext()

  const sport = findSportOption(selection.sport)
  const league = sport.leagues.find(item => item.id === selection.league)?.label ?? selection.league
  const isLive = isLiveDataSelection(selection)
  const basketballRoadmap = ['WNBA', 'NBL (Australia)', 'MPBL (Philippines)']

  if (isLive) return null

  function switchToNbaLive() {
    setSport('nba')
    setLeague('nba')
  }

  return (
    <div className="page-shell">
      <div className="page-content">
        <div className="coming-soon-card">
          <p className="coming-soon-eyebrow">{section}</p>
          <h1 className="coming-soon-title">Coming Soon</h1>
          <p className="coming-soon-subtitle">
            {sport.label} · {league} metrics are not live yet. This view is currently available only for Basketball · NBA.
          </p>
          {sport.id === 'nba' && league !== 'NBA' && (
            <p className="coming-soon-subtitle" style={{ marginTop: 8 }}>
              Basketball leagues planned next: {basketballRoadmap.join(', ')}.
            </p>
          )}
          <div className="coming-soon-actions">
            <button className="coming-soon-btn primary" onClick={switchToNbaLive}>
              Switch To Basketball · NBA
            </button>
            <button className="coming-soon-btn" onClick={() => navigate('/')}>
              Go To Home
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
