import { useState, useRef } from 'react'

function SongInput({ onProcess }) {
  const [query, setQuery] = useState('')
  const [songName, setSongName] = useState('')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
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

      const result = await res.json()
      onProcess(result)

      // Reset form
      setQuery('')
      setSongName('')
      setFile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
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
        {loading ? 'Processing...' : 'Make Karaoke Track'}
      </button>
    </form>
  )
}

export default SongInput
