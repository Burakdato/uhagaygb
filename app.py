from flask import Flask, request, jsonify
from flask_cors import CORS
from TikTokApi import TikTokApi
import asyncio
import os
from contextlib import asynccontextmanager

app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize TikTok API
async def get_tiktok_api():
    """Initialize TikTok API with ms_token for authentication."""
    api = TikTokApi()
    await api.create_sessions(ms_tokens=[None], num_sessions=1, sleep_after=3)
    return api

def extract_video_id(url):
    """Extract video ID from TikTok URL."""
    # Handle different URL formats
    # https://www.tiktok.com/@username/video/1234567890
    # https://vm.tiktok.com/ZMj...
    import re
    
    # Pattern for regular URLs
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    
    # Pattern for short URLs - these need to be resolved
    if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
        # For short URLs, we'll need to expand them
        import requests
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            expanded_url = response.url
            match = re.search(r'/video/(\d+)', expanded_url)
            if match:
                return match.group(1)
        except:
            pass
    
    return None

async def scrape_comments_async(video_url, target_username):
    """Scrape comments using TikTok API."""
    try:
        # Extract video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            raise Exception("Could not extract video ID from URL")
        
        # Initialize API
        api = await get_tiktok_api()
        
        # Get video object
        video = api.video(id=video_id)
        
        # Fetch comments
        found_comments = []
        comment_count = 0
        max_comments = 100  # Limit to avoid timeout
        
        async for comment in video.comments(count=30):
            comment_count += 1
            if comment_count > max_comments:
                break
                
            try:
                # Get comment details
                author = comment.as_dict.get('user', {})
                username = author.get('unique_id', '') or author.get('nickname', '')
                
                # Check if this is our target user
                if username.lower() == target_username.lower():
                    comment_text = comment.as_dict.get('text', '')
                    likes = comment.as_dict.get('digg_count', 0)
                    create_time = comment.as_dict.get('create_time', 0)
                    
                    # Convert timestamp to readable format
                    from datetime import datetime
                    timestamp = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S') if create_time else None
                    
                    found_comments.append({
                        'text': comment_text,
                        'likes': likes,
                        'timestamp': timestamp
                    })
            except Exception as e:
                continue
        
        return found_comments
        
    except Exception as e:
        raise Exception(f"Error fetching comments: {str(e)}")

def scrape_comments_sync(video_url, target_username):
    """Synchronous wrapper for async comment scraping."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_comments_async(video_url, target_username))
    finally:
        loop.close()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    return jsonify({
        'message': 'TikTok Comment Scraper API',
        'version': '3.0',
        'method': 'TikTok API (No Browser Required)',
        'endpoints': {
            '/health': 'GET - Health check',
            '/scrape': 'POST - Scrape comments from TikTok video'
        },
        'usage': {
            'endpoint': '/scrape',
            'method': 'POST',
            'body': {
                'video_url': 'https://www.tiktok.com/@user/video/123',
                'username': 'target_username'
            }
        }
    })

@app.route('/scrape', methods=['POST'])
def scrape():
    """API endpoint to scrape TikTok comments."""
    try:
        data = request.get_json()
        
        if not data or 'video_url' not in data or 'username' not in data:
            return jsonify({'error': 'Missing video_url or username'}), 400
        
        video_url = data['video_url']
        username = data['username'].lstrip('@')
        
        # Validate TikTok URL
        if 'tiktok.com' not in video_url:
            return jsonify({'error': 'Invalid TikTok URL'}), 400
        
        # Scrape comments
        comments = scrape_comments_sync(video_url, username)
        
        return jsonify({
            'success': True,
            'username': username,
            'video_url': video_url,
            'comments': comments,
            'count': len(comments)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok', 
        'service': 'tiktok-scraper',
        'method': 'TikTok API'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
