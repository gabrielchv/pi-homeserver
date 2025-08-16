import functions_framework, logging, json, yt_dlp
from flask import Request, jsonify

logging.basicConfig(level=logging.INFO)
COOKIES_FILE = 'cookies.txt'
YDL_OPTS = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True, 'cookiefile': COOKIES_FILE, 'noplaylist': True, 'forcejson': True}

@functions_framework.http
def get_youtube_details(request: Request):
    headers = {'Access-Control-Allow-Origin': '*'}
    if request.method == 'OPTIONS':
        return ('', 204, {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '3600'})
    
    request_json = request.get_json(silent=True)
    if not request_json or 'url' not in request_json:
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