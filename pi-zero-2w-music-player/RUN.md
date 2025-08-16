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

### 4. Test MPV Configuration (Optional but Recommended for Raspberry Pi)

```bash
# Run the diagnostic script to test MPV setup
python3 test_mpv.py
```

This will check audio configuration, MPV installation, and socket communication.

### 5. Run the Application

```bash
cd app/
python server.py
```

The app will:
- Start MPV automatically with socket interface
- Run the web server on port 5000 
- Accept YouTube URLs for queueing and playback

### 6. Access the Interface

Open your browser to `http://localhost:5000`

## Troubleshooting

### Common Issues

- **No audio playback**: Check `/debug-queue` endpoint to verify MPV status
- **Cloud function errors**: Ensure function is deployed and URL is correct
- **Socket errors**: Verify socat is installed and `/tmp/mpv.sock` permissions
- **Queue buttons not working**: Check browser console for errors, ensure WebSocket connection is active
- **Items not playing**: Verify autoplay is enabled and check server logs for MPV communication errors
- **Buttons work once then stop**: Call `forceRefreshQueue()` in browser console to manually refresh the queue
- **MPV property errors**: These are normal when no music is playing and have been filtered out
- **YouTube processing fails**: A modal will appear automatically suggesting to update cookies.txt when the cloud function returns errors

### Raspberry Pi Specific Issues

- **MPV socket not created**: This is usually an audio configuration issue. Try:
  ```bash
  # Check if user is in audio group
  groups $USER
  
  # If not in audio group, add user to audio group
  sudo usermod -a -G audio $USER
  # Then logout and login again
  
  # Test audio output manually
  speaker-test -t wav -c 2
  
  # Check available audio devices
  aplay -l
  
  # For headphone jack on RPi (if no USB audio)
  sudo raspi-config
  # Advanced Options -> Audio -> Force 3.5mm jack
  
  # Or enable via config
  echo "dtparam=audio=on" | sudo tee -a /boot/config.txt
  sudo reboot
  ```

- **No audio output**: Configure audio output device:
  ```bash
  # List audio devices
  mpv --audio-device=help
  
  # Test MPV directly
  mpv --no-video --ao=alsa test-audio-file.mp3
  
  # For USB audio devices, they usually appear as hw:1,0
  # For built-in audio, usually hw:0,0 or hw:0,1
  ```

- **Permission errors**: Ensure proper permissions:
  ```bash
  # Check audio device permissions
  ls -la /dev/snd/
  
  # Should show audio group ownership
  # If not, add user to audio group as shown above
  ```

## Debug Endpoints

- `GET /debug-queue` - Shows MPV status, queue state, and playback information
- Browser console shows HTMX request/response details and WebSocket events
- `forceRefreshQueue()` - Browser console function to manually refresh queue with proper HTMX binding 