#!/usr/bin/env python3
"""
Standalone MPV test script for diagnosing audio issues on Raspberry Pi
Usage: python3 test_mpv.py
"""

import os
import sys
import time
import json
import subprocess
import tempfile

def check_system_info():
    """Check basic system information"""
    print("=== System Information ===")
    
    # Check if we're on Raspberry Pi
    is_raspberry_pi = False
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read().lower()
            is_raspberry_pi = 'raspberry pi' in cpuinfo or 'bcm' in cpuinfo
        print(f"Raspberry Pi detected: {is_raspberry_pi}")
    except Exception as e:
        print(f"Could not read /proc/cpuinfo: {e}")
    
    # Check user groups
    try:
        import grp, pwd
        username = pwd.getpwuid(os.getuid()).pw_name
        user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        audio_groups = [g for g in user_groups if 'audio' in g.lower()]
        print(f"User: {username}")
        print(f"Audio groups: {audio_groups}")
        if not audio_groups:
            print("WARNING: User not in audio group!")
    except Exception as e:
        print(f"Could not check user groups: {e}")
    
    return is_raspberry_pi

def check_audio_devices():
    """Check available audio devices"""
    print("\n=== Audio Devices ===")
    
    # Check ALSA devices
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("ALSA devices:")
            print(result.stdout)
        else:
            print(f"aplay failed: {result.stderr}")
    except Exception as e:
        print(f"Could not run aplay: {e}")
    
    # Check PulseAudio
    try:
        result = subprocess.run(['pactl', 'list', 'sinks', 'short'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("PulseAudio sinks:")
            print(result.stdout)
        else:
            print("PulseAudio not available or no sinks")
    except Exception as e:
        print("PulseAudio not available")

def check_mpv_installation():
    """Check MPV installation and capabilities"""
    print("\n=== MPV Installation ===")
    
    try:
        result = subprocess.run(['mpv', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"MPV version: {version_line}")
        else:
            print(f"MPV version check failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"MPV not found: {e}")
        return False
    
    # Check audio output options
    try:
        result = subprocess.run(['mpv', '--ao=help'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("Available audio outputs:")
            print(result.stdout)
        else:
            print(f"Could not get audio outputs: {result.stderr}")
    except Exception as e:
        print(f"Could not check audio outputs: {e}")
    
    return True

def test_mpv_basic():
    """Test basic MPV functionality"""
    print("\n=== Basic MPV Test ===")
    
    # Create a test audio file (1 second of silence)
    test_file = "/tmp/test_audio.wav"
    try:
        # Generate 1 second of silence
        subprocess.run([
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', 
            '-t', '1', '-y', test_file
        ], capture_output=True, timeout=10)
        
        if not os.path.exists(test_file):
            print("Could not create test audio file with ffmpeg, trying alternative...")
            # Try with sox if available
            subprocess.run([
                'sox', '-n', '-r', '44100', '-c', '2', test_file, 'trim', '0.0', '1.0'
            ], capture_output=True, timeout=10)
        
        if not os.path.exists(test_file):
            print("Could not create test audio file. Install ffmpeg or sox for testing.")
            return False
            
    except Exception as e:
        print(f"Could not create test file: {e}")
        return False
    
    # Test MPV playback
    try:
        print("Testing MPV playback (should hear 1 second of silence)...")
        result = subprocess.run([
            'mpv', '--no-video', '--really-quiet', test_file
        ], timeout=5)
        
        if result.returncode == 0:
            print("✓ Basic MPV playback successful")
            return True
        else:
            print(f"✗ MPV playback failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ MPV playback timed out")
        return False
    except Exception as e:
        print(f"✗ MPV playback failed: {e}")
        return False
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def test_mpv_socket():
    """Test MPV with socket interface"""
    print("\n=== MPV Socket Test ===")
    
    socket_path = "/tmp/test_mpv.sock"
    
    # Remove existing socket
    if os.path.exists(socket_path):
        os.remove(socket_path)
    
    # Detect system type
    is_raspberry_pi = False
    rpi_model = "unknown"
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read().lower()
            is_raspberry_pi = 'raspberry pi' in cpuinfo or 'bcm' in cpuinfo
            if 'pi zero' in cpuinfo:
                rpi_model = 'zero'
            elif 'raspberry pi' in cpuinfo:
                rpi_model = 'standard'
    except:
        pass
    
    # Build MPV command
    mpv_cmd = [
        'mpv', '--no-video', '--idle=yes', f'--input-ipc-server={socket_path}',
        '--volume=50', '--no-terminal', '--msg-level=all=info'
    ]
    
    if is_raspberry_pi:
        print(f"Configuring for Raspberry Pi ({rpi_model})...")
        
        # Check available audio devices first
        audio_devices = ""
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                audio_devices = result.stdout.lower()
                print(f"Available audio devices:\n{result.stdout}")
        except:
            pass
        
        # Use specific Raspberry Pi audio configuration
        if 'headphones' in audio_devices or 'bcm2835' in audio_devices:
            print("Found built-in audio, using ALSA hw:1,0")
            mpv_cmd.extend([
                '--ao=alsa',
                '--audio-device=alsa/hw:1,0',
                '--audio-samplerate=44100',
                '--audio-format=s16le'
            ])
        elif 'usb' in audio_devices:
            print("Found USB audio device")
            mpv_cmd.extend([
                '--ao=alsa',
                '--audio-device=alsa/hw:2,0',
                '--audio-samplerate=44100',
                '--audio-format=s16le'
            ])
        else:
            print("Using ALSA auto-detection")
            mpv_cmd.extend([
                '--ao=alsa,pulse,',
                '--audio-device=auto',
                '--audio-samplerate=44100',
                '--audio-format=s16le'
            ])
    else:
        mpv_cmd.extend([
            '--ao=pulse,alsa,',
            '--audio-device=auto'
        ])
    
    print(f"Starting MPV with: {' '.join(mpv_cmd)}")
    
    try:
        # Start MPV
        process = subprocess.Popen(
            mpv_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for socket creation
        socket_created = False
        for i in range(20):  # Wait up to 2 seconds
            time.sleep(0.1)
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"✗ MPV died early (exit code: {process.returncode})")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return False
            
            if os.path.exists(socket_path):
                socket_created = True
                break
        
        if not socket_created:
            print("✗ MPV socket was not created")
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        print("✓ MPV socket created successfully")
        
        # Test socket communication
        try:
            result = subprocess.run([
                'socat', '-', f'UNIX-CONNECT:{socket_path}'
            ], input='{"command":["get_property","idle-active"]}\n', 
            text=True, capture_output=True, timeout=2)
            
            if result.returncode == 0 and result.stdout.strip():
                response = json.loads(result.stdout.strip().split('\n')[-1])
                print(f"✓ Socket communication successful: {response}")
                success = True
            else:
                print(f"✗ Socket communication failed: {result.stderr}")
                success = False
        except Exception as e:
            print(f"✗ Socket communication error: {e}")
            success = False
        
        # Cleanup
        process.terminate()
        process.wait(timeout=5)
        
        if os.path.exists(socket_path):
            os.remove(socket_path)
        
        return success
        
    except Exception as e:
        print(f"✗ MPV socket test failed: {e}")
        return False

def main():
    """Main test function"""
    print("MPV Audio Diagnostic Tool for Raspberry Pi")
    print("=" * 50)
    
    is_raspberry_pi = check_system_info()
    check_audio_devices()
    
    if not check_mpv_installation():
        print("\n❌ MPV is not properly installed!")
        print("Install with: sudo apt install mpv")
        return 1
    
    if not test_mpv_basic():
        print("\n❌ Basic MPV test failed!")
        print("Check audio configuration and permissions.")
        return 1
    
    if not test_mpv_socket():
        print("\n❌ MPV socket test failed!")
        print("This will prevent the music player from working.")
        return 1
    
    print("\n✅ All tests passed! MPV should work with the music player.")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 