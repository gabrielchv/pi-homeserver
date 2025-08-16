#!/usr/bin/env python3
"""
Simple MPV debug script to test basic functionality
"""

import os
import subprocess
import time
import json

MPV_SOCKET = '/tmp/debug_mpv.sock'

def test_mpv_startup():
    """Test MPV startup with the same config as the server"""
    
    # Clean up any existing processes and sockets
    try:
        subprocess.run(['pkill', 'mpv'], capture_output=True)
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)
    except:
        pass
    
    time.sleep(0.5)
    
    # Start MPV with PipeWire config (same as working manual test)
    mpv_cmd = [
        'mpv',
        '--no-video',
        '--idle=yes',
        f'--input-ipc-server={MPV_SOCKET}',
        '--volume=50',
        '--no-terminal',
        '--ao=pipewire,pulse,alsa,',
        '--audio-device=auto'
    ]
    
    print(f"Starting MPV with: {' '.join(mpv_cmd)}")
    
    # Start MPV
    process = subprocess.Popen(
        mpv_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print(f"MPV started with PID: {process.pid}")
    
    # Wait for socket creation
    for i in range(30):
        time.sleep(0.1)
        
        # Check if process died
        if process.poll() is not None:
            print(f"❌ MPV process died with exit code: {process.poll()}")
            return False
        
        # Check if socket exists
        if os.path.exists(MPV_SOCKET):
            print(f"✅ MPV socket created successfully!")
            break
    else:
        print("❌ Socket was not created within timeout")
        process.terminate()
        return False
    
    # Test communication
    try:
        result = subprocess.run([
            'socat', '-', f'UNIX-CONNECT:{MPV_SOCKET}'
        ], input='{"command":["get_property","idle-active"]}\n',
        text=True, capture_output=True, timeout=2)
        
        if result.returncode == 0:
            response = json.loads(result.stdout.strip().split('\n')[-1])
            print(f"✅ Communication test successful: {response}")
            success = True
        else:
            print(f"❌ Communication test failed: {result.stderr}")
            success = False
    except Exception as e:
        print(f"❌ Communication error: {e}")
        success = False
    
    # Cleanup
    process.terminate()
    process.wait(timeout=5)
    if os.path.exists(MPV_SOCKET):
        os.remove(MPV_SOCKET)
    
    return success

if __name__ == "__main__":
    print("Testing basic MPV startup...")
    success = test_mpv_startup()
    if success:
        print("\n🎉 MPV test successful!")
    else:
        print("\n�� MPV test failed!") 