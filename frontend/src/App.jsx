import { useState, useEffect } from 'react'
import SongInput from './components/SongInput'
import './App.css'

function App() {
  const [songs, setSongs] = useState([])
  const [currentSong, setCurrentSong] = useState(null)

  useEffect(() => {
    fetch('/api/songs')
      .then((res) => res.json())
      .then((data) => setSongs(data))
      .catch(() => {
        // Backend not yet running - silently ignore
      })
  }, [])

  function handleProcess(result) {
    setCurrentSong(result)
    // Refresh song library
    fetch('/api/songs')
      .then((res) => res.json())
      .then((data) => setSongs(data))
      .catch(() => {})
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Jiyajale</h1>
        <p className="app-subtitle">Turn any song into a karaoke track</p>
      </header>

      <SongInput onProcess={handleProcess} />

      {songs.length > 0 && (
        <div className="song-library">
          <h2>Your Songs</h2>
          <ul className="song-list">
            {songs.map((song) => (
              <li
                key={song.name}
                className={`song-item${currentSong?.name === song.name ? ' active' : ''}`}
                onClick={() => setCurrentSong(song)}
              >
                <span className="song-name">{song.name}</span>
                <span className="song-tracks">
                  {song.has_instrumental && <span className="track-badge">Karaoke</span>}
                  {song.has_vocals && <span className="track-badge">Vocals</span>}
                  {song.has_original && <span className="track-badge">Original</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default App
