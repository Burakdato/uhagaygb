from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import os

app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

def extract_video_id(url):
    """Extract video ID from TikTok URL."""
    # Handle different URL formats
    patterns = [
        r'/video/(\d+)',
        r'tiktok\.com/.*?/(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Handle short URLs
    if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
        try:
            response = requests.head(url, allow_redirects=True, timeout=5)
            expanded_url = response.url
            match = re.search(r'/video/(\d+)', expanded_url)
            if match:
                return match.group(1)
        except:
            pass
    
    return None

def scrape_tiktok_comments(video_url, target_username):
    """
    Scrape comments using TikTok's unofficial API endpoints.
    This method is lightweight and works without a browser.
    """
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            raise Exception("Could not extract video ID from URL. Make sure URL is valid.")
        
        # TikTok's comment API endpoint (unofficial)
        api_url = f"https://www.tiktok.com/api/comment/list/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': video_url,
            'Accept': 'application/json, text/plain, */*',
        }
        
        comments_found = []
        cursor = 0
        max_iterations = 5  # Limit iterations to avoid timeout
        
        for i in range(max_iterations):
            params = {
                'aweme_id': video_id,
                'count': 20,
                'cursor': cursor
            }
            
            try:
                response = requests.get(api_url, params=params, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    # If API fails, break and return what we have
                    break
                
                data = response.json()
                
                # Check if we got comments
                comments_list = data.get('comments', [])
                
                if not comments_list:
                    break
                
                # Search for target username
                for comment in comments_list:
                    try:
                        user = comment.get('user', {})
                        username = user.get('unique_id', '') or user.get('nickname', '')
                        
                        if username.lower() == target_username.lower():
                            text = comment.get('text', '')
                            likes = comment.get('digg_count', 0)
                            create_time = comment.get('create_time', 0)
                            
                            # Format timestamp
                            from datetime import datetime
                            timestamp = None
                            if create_time:
                                try:
                                    timestamp = datetime.fromtimestamp(int(create_time)).strftime('%Y-%m-%d %H:%M:%S')
                                except:
                                    timestamp = str(create_time)
                            
                            comments_found.append({
                                'text': text,
                                'likes': likes,
                                'timestamp': timestamp
                            })
                    except Exception as e:
                        continue
                
                # Check if there are more comments
                has_more = data.get('has_more', 0)
                if not has_more:
                    break
                
                cursor = data.get('cursor', 0)
                
            except requests.exceptions.RequestException:
                break
            except Exception:
                break
        
        return comments_found
        
    except Exception as e:
        raise Exception(f"Error scraping comments: {str(e)}")

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    return jsonify({
        'message': 'TikTok Comment Scraper API',
        'version': '4.0',
        'status': 'Production Ready',
        'method': 'Lightweight API (No dependencies)',
        'endpoints': {
            '/health': 'GET - Health check',
            '/scrape': 'POST - Scrape comments from TikTok video'
        },
        'usage': {
            'method': 'POST',
            'endpoint': '/scrape',
            'body': {
                'video_url': 'https://www.tiktok.com/@user/video/123456789',
                'username': 'target_username'
            },
            'example': 'curl -X POST https://your-api.onrender.com/scrape -H "Content-Type: application/json" -d \'{"video_url":"https://www.tiktok.com/@user/video/123","username":"user"}\''
        }
    })

@app.route('/scrape', methods=['POST'])
def scrape():
    """API endpoint to scrape TikTok comments."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        if 'video_url' not in data:
            return jsonify({'error': 'Missing video_url in request body'}), 400
            
        if 'username' not in data:
            return jsonify({'error': 'Missing username in request body'}), 400
        
        video_url = data['video_url'].strip()
        username = data['username'].strip().lstrip('@')
        
        if not video_url:
            return jsonify({'error': 'video_url cannot be empty'}), 400
            
        if not username:
            return jsonify({'error': 'username cannot be empty'}), 400
        
        # Validate TikTok URL
        if 'tiktok.com' not in video_url:
            return jsonify({'error': 'Invalid TikTok URL. Must contain tiktok.com'}), 400
        
        # Scrape comments
        comments = scrape_tiktok_comments(video_url, username)
        
        return jsonify({
            'success': True,
            'username': username,
            'video_url': video_url,
            'comments': comments,
            'count': len(comments),
            'message': f'Found {len(comments)} comment(s) from @{username}'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'tiktok-comment-scraper',
        'version': '4.0',
        'method': 'API-based (lightweight)'
    }), 200

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint to verify API is working."""
    return jsonify({
        'status': 'ok',
        'message': 'API is working! Use POST /scrape to scrape comments.',
        'test_request': {
            'method': 'POST',
            'endpoint': '/scrape',
            'headers': {'Content-Type': 'application/json'},
            'body': {
                'video_url': 'https://www.tiktok.com/@username/video/1234567890',
                'username': 'target_user'
            }
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting TikTok Comment Scraper on port {port}")
    print(f"📡 Health check: http://localhost:{port}/health")
    print(f"🔍 Scrape endpoint: http://localhost:{port}/scrape")
    app.run(host='0.0.0.0', port=port, debug=False)
