#!/usr/bin/env python3
"""
Simple test for CS202 USB audio device on Raspberry Pi
"""

import os
import subprocess
import time
import json

def test_cs202_mpv():
    """Test MPV with CS202 USB audio device"""
    
    socket_path = "/tmp/cs202_test.sock"
    
    # Clean up
    try:
        subprocess.run(['pkill', 'mpv'], capture_output=True)
        if os.path.exists(socket_path):
            os.remove(socket_path)
    except:
        pass
    
    time.sleep(0.5)
    
    # Test CS202 specific configuration
    mpv_cmd = [
        'mpv',
        '--no-video',
        '--idle=yes',
        f'--input-ipc-server={socket_path}',
        '--volume=50',
        '--no-terminal',
        '--ao=alsa',
        '--audio-device=alsa/hw:0,0',  # CS202 is on card 0
        '--audio-samplerate=48000',    # CS202 supports 48kHz
        '--audio-format=s16le'
    ]
    
    print(f"Testing CS202 with: {' '.join(mpv_cmd)}")
    
    # Start MPV
    process = subprocess.Popen(
        mpv_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print(f"MPV started with PID: {process.pid}")
    
    # Wait for socket creation
    for i in range(30):
        time.sleep(0.1)
        
        # Check if process died
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ MPV process died with exit code: {process.poll()}")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        # Check if socket exists
        if os.path.exists(socket_path):
            print(f"✅ MPV socket created successfully!")
            break
    else:
        print("❌ Socket was not created within timeout")
        process.terminate()
        return False
    
    # Test communication
    try:
        result = subprocess.run([
            'socat', '-', f'UNIX-CONNECT:{socket_path}'
        ], input='{"command":["get_property","idle-active"]}\n',
        text=True, capture_output=True, timeout=2)
        
        if result.returncode == 0:
            response = json.loads(result.stdout.strip().split('\n')[-1])
            print(f"✅ Communication successful: {response}")
            success = True
        else:
            print(f"❌ Communication failed: {result.stderr}")
            success = False
    except Exception as e:
        print(f"❌ Communication error: {e}")
        success = False
    
    # Cleanup
    process.terminate()
    process.wait(timeout=5)
    if os.path.exists(socket_path):
        os.remove(socket_path)
    
    return success

if __name__ == "__main__":
    print("Testing CS202 USB audio device with MPV...")
    print("=" * 50)
    
    success = test_cs202_mpv()
    
    if success:
        print("\n🎉 CS202 MPV test successful!")
        print("This configuration should work in the music player:")
        print("  --ao=alsa")
        print("  --audio-device=alsa/hw:0,0")
        print("  --audio-samplerate=48000")
        print("  --audio-format=s16le")
    else:
        print("\n💥 CS202 MPV test failed!")
        print("Try checking:")
        print("  - Is the CS202 plugged in?")
        print("  - Run 'aplay -l' to verify it's on card 0")
        print("  - Check 'speaker-test -D hw:0,0 -c 2'") 