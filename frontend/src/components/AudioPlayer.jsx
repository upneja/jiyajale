import { useState, useEffect, useRef, useCallback } from 'react'
import * as Tone from 'tone'

const TRACKS = [
  { key: 'instrumental', label: 'Karaoke' },
  { key: 'vocals', label: 'Vocals Only' },
  { key: 'original', label: 'Original' },
]

function AudioPlayer({ song }) {
  const [selectedTrack, setSelectedTrack] = useState('instrumental')
  const [playing, setPlaying] = useState(false)
  const [semitones, setSemitones] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)

  const playerRef = useRef(null)
  const pitchShiftRef = useRef(null)

  // Cleanup Tone resources
  const cleanup = useCallback(() => {
    if (playerRef.current) {
      playerRef.current.stop()
      playerRef.current.disconnect()
      playerRef.current.dispose()
      playerRef.current = null
    }
    if (pitchShiftRef.current) {
      pitchShiftRef.current.disconnect()
      pitchShiftRef.current.dispose()
      pitchShiftRef.current = null
    }
    setPlaying(false)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  // Cleanup when track or song changes
  useEffect(() => {
    cleanup()
  }, [selectedTrack, song, cleanup])

  // Update pitch in real-time without reloading
  useEffect(() => {
    if (pitchShiftRef.current) {
      pitchShiftRef.current.pitch = semitones
    }
  }, [semitones])

  function getTrackUrl(trackKey) {
    return `/api/audio/${encodeURIComponent(song.name)}/${trackKey}`
  }

  function isTrackAvailable(trackKey) {
    if (trackKey === 'instrumental') return song.has_instrumental
    if (trackKey === 'vocals') return song.has_vocals
    if (trackKey === 'original') return song.has_original
    return false
  }

  async function handlePlayStop() {
    if (playing) {
      cleanup()
      return
    }

    try {
      await Tone.start()

      // Create pitch shifter and player
      const pitchShift = new Tone.PitchShift(semitones).toDestination()
      const player = new Tone.Player({
        url: getTrackUrl(selectedTrack),
        autostart: false,
        onload: () => {
          player.start()
          setPlaying(true)
        },
        onstop: () => {
          setPlaying(false)
        },
      }).connect(pitchShift)

      pitchShiftRef.current = pitchShift
      playerRef.current = player
    } catch (err) {
      console.error('Playback error:', err)
      cleanup()
    }
  }

  async function handleExport() {
    setExporting(true)
    setExportError(null)
    try {
      const formData = new FormData()
      formData.append('song_name', song.name)
      formData.append('track', selectedTrack)
      formData.append('semitones', String(semitones))

      const res = await fetch('/api/pitch-shift', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Server error: ${res.status}`)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${song.name}_${selectedTrack}_${semitones >= 0 ? '+' : ''}${semitones}.wav`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err.message)
    } finally {
      setExporting(false)
    }
  }

  const currentTrackAvailable = isTrackAvailable(selectedTrack)

  return (
    <div className="audio-player">
      <h2 className="player-song-name">{song.name}</h2>

      <div className="track-selector">
        {TRACKS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`track-btn${selectedTrack === t.key ? ' active' : ''}${!isTrackAvailable(t.key) ? ' unavailable' : ''}`}
            onClick={() => setSelectedTrack(t.key)}
            disabled={!isTrackAvailable(t.key)}
            title={!isTrackAvailable(t.key) ? 'Track not available' : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        className={`play-btn${playing ? ' playing' : ''}`}
        onClick={handlePlayStop}
        disabled={!currentTrackAvailable}
      >
        {playing ? 'Stop' : 'Play'}
      </button>

      <div className="pitch-control">
        <span className="pitch-label">Pitch</span>
        <input
          type="range"
          min="-12"
          max="12"
          step="1"
          value={semitones}
          onChange={(e) => setSemitones(Number(e.target.value))}
          className="pitch-slider"
        />
        <span className="pitch-value">
          {semitones > 0 ? `+${semitones}` : semitones}
        </span>
        <button
          type="button"
          className="reset-pitch-btn"
          onClick={() => setSemitones(0)}
          disabled={semitones === 0}
        >
          Reset
        </button>
      </div>

      {exportError && <p className="error-msg">{exportError}</p>}

      <button
        type="button"
        className="export-btn"
        onClick={handleExport}
        disabled={exporting || !currentTrackAvailable}
      >
        {exporting
          ? 'Exporting...'
          : `Download${semitones !== 0 ? ` (${semitones > 0 ? '+' : ''}${semitones} semitones)` : ''}`}
      </button>
    </div>
  )
}

export default AudioPlayer
