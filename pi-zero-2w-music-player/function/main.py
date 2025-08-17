import functions_framework, logging, json, yt_dlp
from flask import Request, jsonify

logging.basicConfig(level=logging.INFO)
COOKIES_FILE = 'cookies.txt'
YDL_OPTS = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True, 'cookiefile': COOKIES_FILE, 'noplaylist': True, 'forcejson': True}
SEARCH_OPTS = {'quiet': True, 'no_warnings': True, 'cookiefile': COOKIES_FILE, 'noplaylist': True, 'extract_flat': True}

@functions_framework.http
def get_youtube_details(request: Request):
    headers = {'Access-Control-Allow-Origin': '*'}
    if request.method == 'OPTIONS':
        return ('', 204, {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '3600'})
    
    request_json = request.get_json(silent=True)
    if not request_json:
        return (jsonify({'error': 'Invalid request.'}), 400, headers)
    
    # Handle search requests
    if 'query' in request_json:
        return handle_search(request_json['query'], headers)
    
    # Handle URL processing requests
    if 'url' not in request_json:
        return (jsonify({'error': 'Invalid request.'}), 400, headers)
    
    video_url = request_json['url']
    logging.info(f'Processing URL: {video_url}')
    
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info or 'url' not in info: raise ValueError('Could not extract audio stream.')
            song_details = {'title': info.get('title', 'Unknown'), 'thumbnail': info.get('thumbnail'), 'audioUrl': info['url'], 'duration': info.get('duration', 0), 'source': video_url}
            return (jsonify(song_details), 200, headers)
    except Exception as e:
        logging.error(f'Error processing {video_url}: {e}')
        return (jsonify({'error': 'Failed to process URL.'}), 500, headers)

def handle_search(query, headers):
    """Handle YouTube search requests"""
    if not query or len(query.strip()) < 2:
        return (jsonify({'error': 'Query too short.'}), 400, headers)
    
    query = query.strip()
    logging.info(f'Searching for: {query}')
    
    try:
        search_query = f"ytsearch5:{query}"  # Search for top 5 results
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            search_results = ydl.extract_info(search_query, download=False)
            
            if not search_results or 'entries' not in search_results:
                return (jsonify({'results': []}), 200, headers)
            
            results = []
            for entry in search_results['entries'][:5]:  # Limit to 5 results
                if entry:
                    result = {
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Unknown'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        'thumbnail': entry.get('thumbnail') or f"https://img.youtube.com/vi/{entry.get('id', '')}/mqdefault.jpg",
                        'duration': entry.get('duration', 0),
                        'uploader': entry.get('uploader', 'Unknown')
                    }
                    results.append(result)
            
            logging.info(f'Found {len(results)} results for: {query}')
            return (jsonify({'results': results}), 200, headers)
            
    except Exception as e:
        logging.error(f'Error searching for {query}: {e}')
        return (jsonify({'error': 'Search failed.'}), 500, headers)