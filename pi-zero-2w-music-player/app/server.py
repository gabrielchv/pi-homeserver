import os
import json
import uuid
import time
import threading
import queue as thread_queue
import subprocess
import signal
import atexit
import psutil

import eventlet

eventlet.monkey_patch()

import requests
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO


CLOUD_FUNCTION_URL = 'https://get-youtube-audio-364938401510.southamerica-east1.run.app'
MPV_SOCKET = '/tmp/mpv.sock'

app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

# In-memory queue and playback state
submission_queue: thread_queue.Queue = thread_queue.Queue()
queue_items = []  # List[dict]: {'id','url','status','details'}
playback_state = {
    'current_id': None,
    'current_details': None,  # Store current track details separately
    'paused': True,
    'volume': 50.0,
    'time': 0.0,
    'duration': 0.0,
}
autoplay_enabled = True  # Toggle for automatic next track
mpv_process = None  # Track MPV process


def start_mpv():
    """Start MPV with socket interface"""
    global mpv_process
    try:
        # Kill any existing MPV processes to avoid conflicts
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == 'mpv':
                proc.kill()
        
        # Remove existing socket file if it exists
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)
        
        # Check if we're on a Raspberry Pi or ARM system
        is_raspberry_pi = False
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                is_raspberry_pi = 'raspberry pi' in cpuinfo or 'bcm' in cpuinfo
        except:
            pass
        
        # Build MPV command with appropriate audio settings
        mpv_cmd = [
            'mpv',
            '--no-video',
            '--idle=yes',
            f'--input-ipc-server={MPV_SOCKET}',
            '--volume=50'
        ]
        
        # Detect audio system and configure accordingly
        has_pipewire = False
        has_pulse = False
        try:
            # Check for PipeWire
            result = subprocess.run(['pactl', 'info'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and 'pipewire' in result.stdout.lower():
                has_pipewire = True
            elif result.returncode == 0:
                has_pulse = True
        except:
            pass
        
        if is_raspberry_pi:
            app.logger.info("Detected Raspberry Pi, configuring ALSA-first audio settings...")
            mpv_cmd.extend([
                '--ao=alsa,pulse,pipewire,',  # ALSA first for RPi
                '--audio-device=auto',
                '--audio-samplerate=44100',
                '--audio-format=s16',
            ])
        elif has_pipewire:
            app.logger.info("Detected PipeWire audio system...")
            mpv_cmd.extend([
                '--ao=pipewire,pulse,alsa,',  # PipeWire first
                '--audio-device=auto'
            ])
        elif has_pulse:
            app.logger.info("Detected PulseAudio system...")
            mpv_cmd.extend([
                '--ao=pulse,alsa,',  # PulseAudio first
                '--audio-device=auto'
            ])
        else:
            app.logger.info("Using default audio configuration...")
            mpv_cmd.extend([
                '--ao=pulse,alsa,pipewire,',  # Try all
                '--audio-device=auto'
            ])
        
        # Add terminal settings - still suppress stdout but capture stderr for debugging
        mpv_cmd.extend(['--no-terminal', '--msg-level=all=info'])
        
        app.logger.info(f"Starting MPV with command: {' '.join(mpv_cmd)}")
        
        # Start MPV - suppress both stdout and stderr initially for stability
        mpv_process = subprocess.Popen(
            mpv_cmd,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        # Wait a moment for socket to be created, but also check for early failures
        for i in range(10):  # Wait up to 1 second in 0.1s increments
            time.sleep(0.1)
            
            # Check if process died early
            if mpv_process.poll() is not None:
                raise Exception(f"MPV process died immediately (exit code: {mpv_process.poll()})")
            
            # Check if socket was created
            if os.path.exists(MPV_SOCKET):
                break
        
        if not os.path.exists(MPV_SOCKET):
            raise Exception(f"MPV socket {MPV_SOCKET} was not created")
        
        app.logger.info(f"MPV started successfully with PID {mpv_process.pid}")
        
        # Test basic MPV communication
        try:
            test_result = mpv_get('idle-active')
            app.logger.info(f"MPV communication test successful, idle-active: {test_result}")
        except Exception as e:
            app.logger.warning(f"MPV communication test failed: {e}")
        
        return True
        
    except Exception as e:
        app.logger.error(f"Failed to start MPV: {e}")
        
        # Additional diagnostics
        app.logger.info("Running MPV diagnostics...")
        
        # Check if MPV is installed
        try:
            result = subprocess.run(['mpv', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                app.logger.info(f"MPV version: {result.stdout.split('mpv')[1].split('(')[0].strip()}")
            else:
                app.logger.error(f"MPV version check failed: {result.stderr}")
        except Exception as ve:
            app.logger.error(f"MPV not found or not executable: {ve}")
        
        # Check audio devices
        try:
            # Try to list ALSA devices
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                app.logger.info(f"ALSA devices:\n{result.stdout}")
            else:
                app.logger.warning("No ALSA devices found or aplay not available")
        except:
            pass
        
        # Check if audio groups are accessible
        try:
            import grp, pwd
            username = pwd.getpwuid(os.getuid()).pw_name
            user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            audio_groups = [g for g in user_groups if 'audio' in g.lower()]
            app.logger.info(f"User {username} audio groups: {audio_groups}")
            if not audio_groups:
                app.logger.warning("User not in audio group - this may cause audio issues")
        except:
            pass
        
        # Cleanup failed process
        if mpv_process and mpv_process.poll() is None:
            mpv_process.terminate()
            time.sleep(0.5)
            if mpv_process.poll() is None:
                mpv_process.kill()
        
        return False


def ensure_mpv_running():
    """Ensure MPV is running and responsive"""
    global mpv_process
    
    # Check if process is still running
    if mpv_process is None or mpv_process.poll() is not None:
        app.logger.warning("MPV process is not running, attempting to restart...")
        return start_mpv()
    
    # Check if socket exists
    if not os.path.exists(MPV_SOCKET):
        app.logger.warning("MPV socket missing, attempting to restart MPV...")
        return start_mpv()
    
    # Test responsiveness with a direct socat call (avoid circular dependency)
    try:
        proc = subprocess.run(
            ['socat', '-', f'UNIX-CONNECT:{MPV_SOCKET}'],
            input='{"command":["get_property","idle-active"]}\n',
            text=True,
            capture_output=True,
            timeout=2.0,
        )
        if proc.returncode != 0:
            raise Exception(f"socat failed: {proc.stderr}")
        return True
    except Exception as e:
        app.logger.warning(f"MPV not responsive: {e}, attempting to restart...")
        return start_mpv()


def cleanup_on_exit():
    """Stop music and cleanup when server exits"""
    global mpv_process
    try:
        if mpv_process and mpv_process.poll() is None:
            mpv_process.terminate()
            time.sleep(1)
            if mpv_process.poll() is None:
                mpv_process.kill()
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)
    except Exception as e:
        app.logger.error(f"Error during cleanup: {e}")


# Register cleanup function
atexit.register(cleanup_on_exit)

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    cleanup_on_exit()
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def _run_socat_send(message: dict) -> dict:
    try:
        # Ensure MPV is running before attempting communication
        if not ensure_mpv_running():
            app.logger.error("MPV is not running and failed to start")
            return {}
        
        proc = subprocess.run(
            ['socat', '-', f'UNIX-CONNECT:{MPV_SOCKET}'],
            input=json.dumps(message) + '\n',
            text=True,
            capture_output=True,
            timeout=2.0,
        )
        
        if proc.returncode != 0:
            app.logger.error(f"socat failed with return code {proc.returncode}: {proc.stderr}")
            return {}
            
        stdout = (proc.stdout or '').strip().splitlines()
        if not stdout:
            app.logger.warning("No response from MPV")
            return {}
        # mpv replies with one JSON object per line, take the last
        last_line = stdout[-1].strip()
        result = json.loads(last_line) if last_line else {}
        
        # Check for MPV errors (but filter out common "property unavailable" when idle)
        if 'error' in result and result['error'] != 'success':
            if result['error'] != 'property unavailable':
                app.logger.error(f"MPV command error: {result}")
            
        return result
    except subprocess.TimeoutExpired:
        app.logger.error("MPV communication timeout")
        return {}
    except Exception as e:
        app.logger.error(f"Error communicating with MPV: {e}")
        return {}


def mpv_command(command_list):
    return _run_socat_send({'command': command_list})


def mpv_get(prop):
    resp = _run_socat_send({'command': ['get_property', prop]})
    return resp.get('data')


def mpv_set(prop, value):
    return _run_socat_send({'command': ['set_property', prop, value]})


def find_item_index_by_id(item_id: str) -> int:
    for idx, item in enumerate(queue_items):
        if item['id'] == item_id:
            return idx
    return -1


def play_item(item: dict) -> None:
    details = item.get('details') or {}
    audio_url = details.get('audioUrl')
    if not audio_url:
        app.logger.error(f"No audio URL found for item {item['id']}")
        return
    
    app.logger.info(f"Loading audio URL for item {item['id']}: {audio_url}")
    result = mpv_command(['loadfile', audio_url, 'replace'])
    
    # Check if command was successful
    if not result or result.get('error') != 'success':
        app.logger.error(f"Failed to load file in MPV: {result}")
        return
    
    playback_state['current_id'] = item['id']
    playback_state['current_details'] = details  # Store the details
    playback_state['paused'] = False
    # Set title if available
    title = details.get('title')
    if title:
        _ = mpv_set('media-title', title)
    
    # Remove the item from the queue when it starts playing
    idx = find_item_index_by_id(item['id'])
    if idx >= 0:
        removed_item = queue_items.pop(idx)
        socketio.emit('item_removed', {'id': item['id']})
    
    # Emit current track info immediately
    socketio.emit('status', {
        'paused': False,
        'time': 0.0,
        'duration': details.get('duration', 0.0),
        'volume': playback_state['volume'],
        'current': {
            'id': item['id'],
            'title': details.get('title'),
            'thumbnail': details.get('thumbnail'),
            'source': details.get('source'),
        }
    })


def play_next() -> None:
    if not autoplay_enabled:
        return
        
    if playback_state['current_id'] is None:
        # Start from the first ready item
        for item in queue_items:
            if item.get('details'):
                play_item(item)
                return
        return

    # Find current item and then play the next ready one
    current_index = find_item_index_by_id(playback_state['current_id'])
    next_candidates = queue_items[current_index + 1:] if current_index >= 0 else queue_items
    for next_item in next_candidates:
        if next_item.get('details'):
            play_item(next_item)
            return

    # No next item, clear current
    playback_state['current_id'] = None
    playback_state['current_details'] = None
    socketio.emit('status', {
        'paused': True,
        'time': 0.0,
        'duration': 0.0,
        'volume': playback_state['volume'],
        'current': None
    })


@app.route('/')
def index():
    return render_template('index.html', queue_items=queue_items)


@app.route('/queue')
def queue_partial():
    return render_template('queue.html', queue_items=queue_items)


@app.post('/submit')
def submit_url():
    url = (request.form.get('url') or '').strip()
    if not url:
        return ('', 400)
    item_id = str(uuid.uuid4())[:8]
    item = {
        'id': item_id,
        'url': url,
        'status': 'loading',
        'details': None,
    }
    queue_items.append(item)  # Add to end of queue
    submission_queue.put({'id': item_id, 'url': url})
    # Return a single-item partial to insert at the end of the queue
    return render_template('queue.html', queue_items=[item])


@app.post('/control')
def control():
    action = (request.form.get('action') or '').strip()
    if action == 'playpause':
        mpv_command(['cycle', 'pause'])
    elif action == 'stop':
        mpv_command(['stop'])
        playback_state['current_id'] = None
        playback_state['current_details'] = None
        socketio.emit('status', {
            'paused': True,
            'time': 0.0,
            'duration': 0.0,
            'volume': playback_state['volume'],
            'current': None
        })
    elif action == 'skip':
        play_next()
    return ('', 204)


@app.post('/volume')
def set_volume():
    try:
        volume = float(request.form.get('volume', '50'))
    except ValueError:
        return ('', 400)
    mpv_set('volume', max(0, min(100, volume)))
    playback_state['volume'] = volume
    return ('', 204)


@app.post('/seek')
def seek():
    # Expect percent position in 0..100
    try:
        percent = float(request.form.get('position', '0'))
    except ValueError:
        return ('', 400)
    percent = max(0.0, min(100.0, percent))
    mpv_set('percent-pos', percent)
    return ('', 204)


@app.post('/clear-queue')
def clear_queue():
    global queue_items
    queue_items.clear()
    playback_state['current_id'] = None
    playback_state['current_details'] = None
    mpv_command(['stop'])
    socketio.emit('queue_cleared')
    return ('', 204)


@app.post('/play-now')
def play_now():
    item_id = request.form.get('id')
    if not item_id:
        app.logger.error("No item ID provided for play-now")
        return ('', 400)
    
    app.logger.info(f"Play now requested for item: {item_id}")
    
    idx = find_item_index_by_id(item_id)
    if idx >= 0 and queue_items[idx].get('details'):
        # Move item to front of queue
        item = queue_items.pop(idx)
        queue_items.insert(0, item)
        # Play it immediately
        play_item(item)
        app.logger.info(f"Successfully moved and started playing item: {item_id}")
        
        # Use a slight delay to ensure the WebSocket event is processed after the HTTP response
        def emit_queue_update():
            socketio.emit('queue_refreshed', {'items': queue_items})
        
        socketio.start_background_task(emit_queue_update)
        return ('', 200)
    else:
        app.logger.error(f"Item not found or not ready: {item_id}")
        return ('', 404)


@app.post('/remove-item')
def remove_item():
    item_id = request.form.get('id')
    if not item_id:
        app.logger.error("No item ID provided for remove-item")
        return ('', 400)
    
    app.logger.info(f"Remove item requested for: {item_id}")
    
    idx = find_item_index_by_id(item_id)
    if idx >= 0:
        removed_item = queue_items.pop(idx)
        # If we removed the currently playing item, stop playback
        if playback_state['current_id'] == item_id:
            playback_state['current_id'] = None
            playback_state['current_details'] = None
            mpv_command(['stop'])
            
            def emit_status_update():
                socketio.emit('status', {
                    'paused': True,
                    'time': 0.0,
                    'duration': 0.0,
                    'volume': playback_state['volume'],
                    'current': None
                })
            
            socketio.start_background_task(emit_status_update)
        
        def emit_item_removed():
            socketio.emit('item_removed', {'id': item_id})
        
        socketio.start_background_task(emit_item_removed)
        app.logger.info(f"Successfully removed item: {item_id}")
        return ('', 200)
    else:
        app.logger.error(f"Item not found: {item_id}")
        return ('', 404)


@app.post('/shuffle-queue')
def shuffle_queue():
    import random
    global queue_items
    
    # Keep currently playing item at the top if any
    current_item = None
    if playback_state['current_id'] is not None:
        idx = find_item_index_by_id(playback_state['current_id'])
        if idx >= 0:
            current_item = queue_items.pop(idx)
    
    # Shuffle the rest
    random.shuffle(queue_items)
    
    # Put current item back at top if it exists
    if current_item:
        queue_items.insert(0, current_item)
    
    # Emit the full updated queue to refresh the frontend
    socketio.emit('queue_refreshed', {'items': queue_items})
    return ('', 204)


@app.post('/move-up')
def move_up():
    item_id = request.form.get('id')
    if not item_id:
        app.logger.error("No item ID provided for move-up")
        return ('', 400)
    
    app.logger.info(f"Move up requested for item: {item_id}")
    
    idx = find_item_index_by_id(item_id)
    if idx > 0:  # Can't move first item up
        # Swap with item above
        queue_items[idx], queue_items[idx - 1] = queue_items[idx - 1], queue_items[idx]
        app.logger.info(f"Successfully moved item {item_id} up from position {idx} to {idx - 1}")
        
        def emit_queue_update():
            socketio.emit('queue_refreshed', {'items': queue_items})
        
        socketio.start_background_task(emit_queue_update)
        return ('', 200)
    else:
        app.logger.warning(f"Item {item_id} is already at the top of the queue")
        return ('', 200)


@app.post('/move-down')
def move_down():
    item_id = request.form.get('id')
    if not item_id:
        app.logger.error("No item ID provided for move-down")
        return ('', 400)
    
    app.logger.info(f"Move down requested for item: {item_id}")
    
    idx = find_item_index_by_id(item_id)
    if idx < len(queue_items) - 1:  # Can't move last item down
        # Swap with item below
        queue_items[idx], queue_items[idx + 1] = queue_items[idx + 1], queue_items[idx]
        app.logger.info(f"Successfully moved item {item_id} down from position {idx} to {idx + 1}")
        
        def emit_queue_update():
            socketio.emit('queue_refreshed', {'items': queue_items})
        
        socketio.start_background_task(emit_queue_update)
        return ('', 200)
    else:
        app.logger.warning(f"Item {item_id} is already at the bottom of the queue")
        return ('', 200)


@app.post('/reorder-queue')
def reorder_queue():
    try:
        # Get JSON data from request
        data = request.get_json()
        if not data:
            app.logger.error("No JSON data received in reorder request")
            return ('', 400)
        
        old_index = data.get('oldIndex')
        new_index = data.get('newIndex')
        
        # Validate that both indices are provided and are integers
        if old_index is None or new_index is None:
            app.logger.error(f"Missing indices: oldIndex={old_index}, newIndex={new_index}")
            return ('', 400)
        
        try:
            old_index = int(old_index)
            new_index = int(new_index)
        except (ValueError, TypeError) as e:
            app.logger.error(f"Invalid index values: oldIndex={old_index}, newIndex={new_index}, error={e}")
            return ('', 400)
        
        app.logger.info(f"Reordering queue: {old_index} -> {new_index}, queue length: {len(queue_items)}")
        
        if 0 <= old_index < len(queue_items) and 0 <= new_index < len(queue_items):
            item = queue_items.pop(old_index)
            queue_items.insert(new_index, item)
            app.logger.info(f"Successfully reordered item '{item.get('id', 'unknown')}' from {old_index} to {new_index}")
            # Emit the full updated queue to refresh the frontend
            socketio.emit('queue_refreshed', {'items': queue_items})
        else:
            app.logger.error(f"Index out of range: oldIndex={old_index}, newIndex={new_index}, queue length={len(queue_items)}")
            return ('', 400)
            
    except Exception as e:
        app.logger.error(f"Error in reorder_queue: {e}")
        return ('', 500)
    
    return ('', 204)


@app.post('/toggle-autoplay')
def toggle_autoplay():
    global autoplay_enabled
    autoplay_enabled = not autoplay_enabled
    socketio.emit('autoplay_toggled', {'enabled': autoplay_enabled})
    return jsonify({'enabled': autoplay_enabled})


@app.get('/autoplay-status')
def get_autoplay_status():
    return jsonify({'enabled': autoplay_enabled})


@app.get('/debug-queue')
def debug_queue():
    """Debug endpoint to see current queue state"""
    global mpv_process
    
    mpv_status = "Not started"
    if mpv_process:
        if mpv_process.poll() is None:
            mpv_status = f"Running (PID: {mpv_process.pid})"
        else:
            mpv_status = f"Dead (exit code: {mpv_process.poll()})"
    
    debug_info = {
        'mpv_status': mpv_status,
        'mpv_socket_exists': os.path.exists(MPV_SOCKET),
        'queue_length': len(queue_items),
        'queue_items': [
            {
                'id': item['id'],
                'status': item['status'],
                'has_details': bool(item.get('details')),
                'title': item.get('details', {}).get('title', 'No title') if item.get('details') else 'No details'
            }
            for item in queue_items
        ],
        'playback_state': playback_state,
        'autoplay_enabled': autoplay_enabled
    }
    return jsonify(debug_info)


def submission_worker():
    while True:
        try:
            task = submission_queue.get()
        except Exception:
            continue
        if not task:
            continue
        item_id = task.get('id')
        url = task.get('url')
        try:
            app.logger.info(f"Processing URL: {url} for item: {item_id}")
            resp = requests.post(CLOUD_FUNCTION_URL, json={'url': url}, timeout=30)
            if resp.status_code == 200:
                details = resp.json()
                app.logger.info(f"Successfully got details for {item_id}: {details.get('title', 'Unknown')}")
                # Update item
                idx = find_item_index_by_id(item_id)
                if idx >= 0:
                    queue_items[idx]['details'] = details
                    queue_items[idx]['status'] = 'ready'
                    app.logger.info(f"Updated item {item_id} status to 'ready'")
                    socketio.emit('queue_update', {'id': item_id, 'item': queue_items[idx]})
                    # Autoplay if nothing is playing and autoplay is enabled
                    if autoplay_enabled and playback_state['current_id'] is None:
                        app.logger.info(f"Starting autoplay for item {item_id}")
                        play_item(queue_items[idx])
                    else:
                        app.logger.info(f"Autoplay not triggered: autoplay_enabled={autoplay_enabled}, current_id={playback_state['current_id']}")
                else:
                    app.logger.error(f"Item {item_id} not found in queue after processing")
            else:
                app.logger.error(f"Cloud function returned status {resp.status_code} for {item_id}")
                idx = find_item_index_by_id(item_id)
                if idx >= 0:
                    queue_items[idx]['status'] = 'error'
                    socketio.emit('queue_update', {'id': item_id, 'item': queue_items[idx]})
                    
                    # If it's a 500 error, show the cookies update modal
                    if resp.status_code == 500:
                        socketio.emit('show_cookies_modal', {'url': url, 'item_id': item_id})
        except Exception as e:
            app.logger.error(f"Error processing {item_id}: {e}")
            idx = find_item_index_by_id(item_id)
            if idx >= 0:
                queue_items[idx]['status'] = 'error'
                socketio.emit('queue_update', {'id': item_id, 'item': queue_items[idx]})
                
                # If it's a timeout or connection error, also suggest cookies update
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['timeout', 'connection', 'ssl', 'certificate']):
                    socketio.emit('show_cookies_modal', {'url': url, 'item_id': item_id})
        finally:
            try:
                submission_queue.task_done()
            except Exception:
                pass


def poll_mpv_state():
    while True:
        try:
            # First check if MPV is idle to avoid unnecessary property queries
            idle_active = bool(mpv_get('idle-active')) if mpv_get('idle-active') is not None else False
            
            # Only query playback properties if something is loaded
            if not idle_active:
                paused = bool(mpv_get('pause')) if mpv_get('pause') is not None else playback_state['paused']
                time_pos = float(mpv_get('time-pos') or 0.0)
                duration = float(mpv_get('duration') or 0.0)
                
                playback_state['paused'] = paused
                playback_state['time'] = time_pos
                playback_state['duration'] = duration
            else:
                # When idle, set appropriate default values
                playback_state['paused'] = True
                playback_state['time'] = 0.0
                playback_state['duration'] = 0.0
            
            # Volume can be queried even when idle
            volume = float(mpv_get('volume') or playback_state['volume'])
            playback_state['volume'] = volume

            # Detect end of file: mpv becomes idle after finishing the file
            if idle_active and playback_state['current_id'] is not None and not playback_state['paused']:
                play_next()

            # Use stored current details instead of searching queue
            current_details = playback_state.get('current_details')
            
            socketio.emit('status', {
                'paused': paused,
                'time': time_pos,
                'duration': duration,
                'volume': volume,
                'current': {
                    'id': playback_state['current_id'],
                    'title': current_details.get('title') if current_details else None,
                    'thumbnail': current_details.get('thumbnail') if current_details else None,
                    'source': current_details.get('source') if current_details else None,
                } if playback_state['current_id'] and current_details else None
            })
        except Exception:
            pass
        finally:
            time.sleep(0.5)


def start_background_threads():
    # Start MPV first
    if not start_mpv():
        app.logger.error("Failed to start MPV - music playback will not work!")
    
    threading.Thread(target=submission_worker, daemon=True).start()
    threading.Thread(target=poll_mpv_state, daemon=True).start()


start_background_threads()


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '5000'))) 