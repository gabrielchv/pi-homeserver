# API Endpoints Documentation

## External Endpoints

### Google Cloud Function

**URL**: `https://get-youtube-audio-364938401510.southamerica-east1.run.app`

**Method**: `POST`

**Description**: Extracts audio stream URL and metadata from YouTube URLs, or searches YouTube for music

#### URL Processing Request:
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response** (Success - 200):
```json
{
  "title": "Rick Astley - Never Gonna Give You Up",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "audioUrl": "https://rr3---sn-4g5e6nez.googlevideo.com/...",
  "duration": 213,
  "source": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

#### Search Request:
```json
{
  "query": "never gonna give you up rick astley"
}
```

**Response** (Success - 200):
```json
{
  "results": [
    {
      "id": "dQw4w9WgXcQ",
      "title": "Rick Astley - Never Gonna Give You Up",
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
      "duration": 213,
      "uploader": "Rick Astley"
    }
  ]
}
```

**Response** (Error - 400/500):
```json
{
  "error": "Failed to process URL." // or "Search failed."
}
```

## Internal App Endpoints

### Web Interface

- `GET /` - Main player interface
- `GET /queue` - Queue partial template

### Player Control

- `POST /submit` - Add URL to queue
  - Body: `url=<youtube_url>`
  - Returns: HTML partial for new queue item

- `POST /search` - Search YouTube for music
  - Body: `{"query": "artist song name"}`
  - Returns: `{"results": [...]}`

- `POST /control` - Control playback
  - Body: `action=playpause|stop|skip`

- `POST /volume` - Set volume
  - Body: `volume=<0-100>`

- `POST /seek` - Seek position  
  - Body: `position=<0-100>` (percentage)

### Queue Management

- `POST /clear-queue` - Clear entire queue
- `POST /play-now` - Play specific item immediately
  - Body: `id=<item_id>`
- `POST /remove-item` - Remove item from queue
  - Body: `id=<item_id>`
- `POST /shuffle-queue` - Shuffle queue order
- `POST /move-up` - Move item up in queue
  - Body: `id=<item_id>`
- `POST /move-down` - Move item down in queue
  - Body: `id=<item_id>`
- `POST /reorder-queue` - Reorder queue items
  - Body: `{"oldIndex": 0, "newIndex": 2}`

### Settings

- `POST /toggle-autoplay` - Toggle autoplay mode
- `GET /autoplay-status` - Get autoplay status
  - Returns: `{"enabled": true}`

### Debug

- `GET /debug-queue` - Debug information
  - Returns: Queue state, MPV status, playback state

## WebSocket Events

### Client → Server
- Connect to socket.io on same port

### Server → Client

- `status` - Playback status updates
- `queue_update` - Single item updated  
- `queue_cleared` - Queue cleared
- `item_removed` - Item removed from queue
- `queue_refreshed` - Full queue refresh
- `autoplay_toggled` - Autoplay status changed
- `show_cookies_modal` - Triggered when cloud function returns 500 error, shows modal with cookie update instructions 