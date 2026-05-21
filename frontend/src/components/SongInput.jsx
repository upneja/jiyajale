import { useState, useRef, useEffect } from 'react'

const STEP_LABELS = {
  queued: 'Waiting in queue...',
  uploading: 'Uploading file...',
  converting: 'Converting to WAV...',
  downloading: 'Downloading from YouTube...',
  downloaded: 'Download complete, starting separation...',
  separating: 'Separating vocals with Demucs AI...',
  done: 'Complete!',
  error: 'Something went wrong',
}

const STEP_ORDER = ['uploading', 'converting', 'downloading', 'downloaded', 'separating', 'done']

function getStepIndex(status) {
  const idx = STEP_ORDER.indexOf(status)
  return idx === -1 ? 0 : idx
}

function getOverallProgress(status, pct) {
  // Map stages to overall progress ranges
  if (status === 'queued' || status === 'uploading') return 5
  if (status === 'converting' || status === 'downloading') return 15
  if (status === 'downloaded') return 40
  if (status === 'separating') return 40 + (pct / 100) * 55 // 40-95%
  if (status === 'done') return 100
  return 0
}

function ElapsedTime({ startTime }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [startTime])

  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  return <span className="elapsed-time">{mins}:{secs.toString().padStart(2, '0')}</span>
}

function SongInput({ onProcess }) {
  const [query, setQuery] = useState('')
  const [songName, setSongName] = useState('')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [jobStatus, setJobStatus] = useState(null) // { status, progress }
  const [startTime, setStartTime] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  function handleFileSelect(selectedFile) {
    if (!selectedFile) return
    setFile(selectedFile)
    // Auto-populate song name from filename (strip extension)
    const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, '')
    setSongName(nameWithoutExt)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && dropped.type.startsWith('audio/')) {
      handleFileSelect(dropped)
    }
  }

  function handleDragOver(e) {
    e.preventDefault()
    setDragging(true)
  }

  function handleDragLeave(e) {
    e.preventDefault()
    setDragging(false)
  }

  async function pollJob(name) {
    while (true) {
      await new Promise((r) => setTimeout(r, 1500))
      const res = await fetch(`/api/jobs/${encodeURIComponent(name)}`)
      if (!res.ok) throw new Error(`Poll failed: ${res.status}`)
      const data = await res.json()
      setJobStatus({ status: data.status, progress: data.progress || 0 })
      if (data.status === 'done') return data
      if (data.status === 'error') throw new Error(data.error || 'Processing failed')
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!songName.trim()) {
      setError('Please enter a song name.')
      return
    }
    if (!query.trim() && !file) {
      setError('Please enter a YouTube URL/song name or upload a file.')
      return
    }

    setError(null)
    setLoading(true)
    setStartTime(Date.now())
    setJobStatus({ status: 'uploading', progress: 0 })

    try {
      const formData = new FormData()
      if (query.trim()) formData.append('query', query.trim())
      formData.append('song_name', songName.trim())
      if (file) formData.append('file', file)

      const res = await fetch('/api/process', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Server error: ${res.status}`)
      }

      const { name } = await res.json()
      setJobStatus({ status: 'queued', progress: 0 })

      // Poll until processing completes
      await pollJob(name)

      // Fetch updated song list and select the new song
      const songsRes = await fetch('/api/songs')
      const songs = await songsRes.json()
      const processed = songs.find((s) => s.name === name)
      if (processed) onProcess(processed)

      // Reset form
      setQuery('')
      setSongName('')
      setFile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setJobStatus(null)
      setStartTime(null)
    }
  }

  if (loading && jobStatus) {
    const overall = getOverallProgress(jobStatus.status, jobStatus.progress)
    const label = STEP_LABELS[jobStatus.status] || jobStatus.status
    const isSeparating = jobStatus.status === 'separating'

    return (
      <div className="processing-panel">
        <div className="processing-header">
          <span className="processing-title">Processing: {songName}</span>
          {startTime && <ElapsedTime startTime={startTime} />}
        </div>

        <div className="progress-bar-container">
          <div className="progress-bar-fill" style={{ width: `${overall}%` }} />
        </div>

        <div className="progress-details">
          <span className="progress-step">{label}</span>
          {isSeparating && (
            <span className="progress-hint">This takes a few minutes — Demucs is running 4 models</span>
          )}
        </div>

        <div className="progress-steps">
          {['Upload', 'Convert', 'Separate', 'Done'].map((step, i) => {
            const stepKeys = [['uploading'], ['converting', 'downloading', 'downloaded'], ['separating'], ['done']]
            const isActive = stepKeys[i].includes(jobStatus.status)
            const isPast = getStepIndex(jobStatus.status) > getStepIndex(stepKeys[i][stepKeys[i].length - 1])
            return (
              <div key={step} className={`progress-step-dot${isActive ? ' active' : ''}${isPast ? ' past' : ''}`}>
                <div className="dot" />
                <span>{step}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <form className="song-input" onSubmit={handleSubmit}>
      <div
        className={`drop-zone${dragging ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          style={{ display: 'none' }}
          onChange={(e) => handleFileSelect(e.target.files[0])}
        />
        {file ? (
          <span className="drop-zone-label">
            {file.name}
            <button
              type="button"
              className="remove-file"
              onClick={(e) => {
                e.stopPropagation()
                setFile(null)
                setSongName('')
              }}
            >
              x
            </button>
          </span>
        ) : (
          <span className="drop-zone-label">
            Drop an audio file here, or click to browse
          </span>
        )}
      </div>

      <div className="input-divider">
        <span>or</span>
      </div>

      <input
        type="text"
        className="text-input"
        placeholder="YouTube URL or song name (e.g. Bohemian Rhapsody)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={loading}
      />

      <input
        type="text"
        className="text-input"
        placeholder="Song name (used to save the track)"
        value={songName}
        onChange={(e) => setSongName(e.target.value)}
        disabled={loading}
        required
      />

      {error && <p className="error-msg">{error}</p>}

      <button type="submit" className="submit-btn" disabled={loading}>
        Make Karaoke Track
      </button>
    </form>
  )
}

export default SongInput
