from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import re
import os

app = Flask(__name__)

# Configure CORS for production
CORS(app, resources={
    r"/*": {
        "origins": ["*"],  # In production, replace with your frontend domain
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

def scrape_tiktok_comments(video_url, target_username):
    """
    Scrape TikTok video page and search for comments by a specific username.
    Note: TikTok loads comments dynamically, so this scrapes initial data from HTML.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        # Fetch the TikTok page
        response = requests.get(video_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # TikTok embeds data in JSON within script tags
        comments = []
        
        # Look for SIGI_STATE or __UNIVERSAL_DATA_FOR_REHYDRATION__
        scripts = soup.find_all('script', {'id': 'SIGI_STATE'})
        if not scripts:
            scripts = soup.find_all('script', {'id': '__UNIVERSAL_DATA_FOR_REHYDRATION__'})
        
        for script in scripts:
            try:
                script_content = script.string
                if script_content:
                    # Parse JSON data
                    data = json.loads(script_content)
                    
                    # Navigate through the data structure to find comments
                    # Structure varies, so we'll search recursively
                    comments = find_comments_in_data(data, target_username)
                    if comments:
                        break
            except json.JSONDecodeError:
                continue
        
        # If no comments found in JSON, try parsing HTML comments
        if not comments:
            comments = scrape_comments_from_html(soup, target_username)
        
        return comments
        
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch TikTok page: {str(e)}")
    except Exception as e:
        raise Exception(f"Error scraping comments: {str(e)}")

def find_comments_in_data(data, target_username, comments=None):
    """Recursively search for comments in nested JSON data."""
    if comments is None:
        comments = []
    
    if isinstance(data, dict):
        # Check if this is a comment object
        if 'text' in data and 'user' in data:
            user = data.get('user', {})
            username = user.get('uniqueId', '') or user.get('nickname', '')
            
            if username.lower() == target_username.lower():
                comment = {
                    'text': data.get('text', ''),
                    'likes': data.get('digg_count', 0),
                    'timestamp': data.get('create_time', ''),
                }
                comments.append(comment)
        
        # Recursively search in nested dictionaries
        for value in data.values():
            find_comments_in_data(value, target_username, comments)
            
    elif isinstance(data, list):
        # Recursively search in lists
        for item in data:
            find_comments_in_data(item, target_username, comments)
    
    return comments

def scrape_comments_from_html(soup, target_username):
    """Fallback method to scrape comments from HTML if JSON parsing fails."""
    comments = []
    
    # Look for comment elements (structure may vary)
    comment_elements = soup.find_all(['div', 'span'], class_=re.compile(r'comment', re.I))
    
    for elem in comment_elements:
        text = elem.get_text(strip=True)
        # Simple heuristic: if element contains the username and has substantial text
        if target_username.lower() in text.lower() and len(text) > len(target_username) + 5:
            comments.append({
                'text': text,
                'likes': None,
                'timestamp': None,
            })
    
    return comments

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    return jsonify({
        'message': 'TikTok Comment Scraper API',
        'version': '1.0',
        'endpoints': {
            '/health': 'Health check',
            '/scrape': 'POST - Scrape comments from TikTok video'
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
        username = data['username'].lstrip('@')  # Remove @ if present
        
        # Validate TikTok URL
        if 'tiktok.com' not in video_url:
            return jsonify({'error': 'Invalid TikTok URL'}), 400
        
        # Scrape comments
        comments = scrape_tiktok_comments(video_url, username)
        
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
    return jsonify({'status': 'ok', 'service': 'tiktok-scraper'})

if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Bind to 0.0.0.0 for external access
    app.run(host='0.0.0.0', port=port, debug=False)
