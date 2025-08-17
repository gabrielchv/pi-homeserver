#!/usr/bin/env python3
"""
Test script for the search functionality
Usage: python3 test_search.py
"""

import requests
import json

def test_search_endpoint():
    """Test the local search endpoint"""
    print("Testing search endpoint...")
    
    # Test with a simple query
    query = "never gonna give you up"
    
    try:
        response = requests.post('http://localhost:5000/search', 
                               json={'query': query}, 
                               timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"✅ Search successful! Found {len(results)} results for '{query}'")
            
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result.get('title', 'Unknown')}")
                print(f"     By: {result.get('uploader', 'Unknown')}")
                print(f"     URL: {result.get('url', 'No URL')}")
                print(f"     Duration: {result.get('duration', 0)}s")
                print()
                
        else:
            print(f"❌ Search failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is the server running on localhost:5000?")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_cloud_function_direct():
    """Test the cloud function directly"""
    print("Testing cloud function directly...")
    
    cloud_function_url = 'https://get-youtube-audio-364938401510.southamerica-east1.run.app'
    query = "rick astley"
    
    try:
        response = requests.post(cloud_function_url, 
                               json={'query': query}, 
                               timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"✅ Cloud function search successful! Found {len(results)} results for '{query}'")
            
            for i, result in enumerate(results[:2], 1):
                print(f"  {i}. {result.get('title', 'Unknown')}")
                print(f"     By: {result.get('uploader', 'Unknown')}")
                print()
                
        else:
            print(f"❌ Cloud function failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Cloud function error: {e}")

if __name__ == "__main__":
    print("🎵 Music Search Test")
    print("=" * 50)
    
    # Test local endpoint first
    test_search_endpoint()
    print()
    
    # Test cloud function directly
    test_cloud_function_direct()
    
    print("\n💡 Tips:")
    print("- Make sure the server is running: python app/server.py")
    print("- Make sure the cloud function is deployed and updated")
    print("- Try the search feature in the web interface!") 