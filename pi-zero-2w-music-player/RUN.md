# Running the Pi Zero 2W Music Player

## Prerequisites

- Python 3.8+ 
- MPV media player
- socat (for socket communication)
- Google Cloud Function deployed (optional, for remote processing)

## Installation Steps

### 1. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mpv socat python3-pip

# Arch Linux  
sudo pacman -S mpv socat python-pip
```

### 2. Install Python Dependencies

```bash
cd app/
pip install -r requirements.txt
```

### 3. Deploy Google Cloud Function (Optional)

```bash
cd function/
gcloud functions deploy get-youtube-audio --runtime python311 --trigger-http --allow-unauthenticated
```

Update `CLOUD_FUNCTION_URL` in `app/server.py` with your function URL.

### 4. Run the Application

```bash
cd app/
python server.py
```

The app will:
- Start MPV automatically with socket interface
- Run the web server on port 5000 
- Accept YouTube URLs for queueing and playback

### 5. Access the Interface

Open your browser to `http://localhost:5000`

## Troubleshooting

- **No audio playback**: Check `/debug-queue` endpoint to verify MPV status
- **Cloud function errors**: Ensure function is deployed and URL is correct
- **Socket errors**: Verify socat is installed and `/tmp/mpv.sock` permissions
- **Queue buttons not working**: Check browser console for errors, ensure WebSocket connection is active
- **Items not playing**: Verify autoplay is enabled and check server logs for MPV communication errors
- **Buttons work once then stop**: Call `forceRefreshQueue()` in browser console to manually refresh the queue
- **MPV property errors**: These are normal when no music is playing and have been filtered out
- **YouTube processing fails**: A modal will appear automatically suggesting to update cookies.txt when the cloud function returns errors

## Debug Endpoints

- `GET /debug-queue` - Shows MPV status, queue state, and playback information
- Browser console shows HTMX request/response details and WebSocket events
- `forceRefreshQueue()` - Browser console function to manually refresh queue with proper HTMX binding 