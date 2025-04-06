import requests
import json
import time
import logging
from datetime import datetime
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# File path constants
DATA_FILE = 'reddit_tracker_data.json'

def get_online_users(subreddit, verbose=False):
    """
    Scrapes the number of online users from a subreddit.
    
    Args:
        subreddit: Name of the subreddit without r/
        verbose: Whether to print detailed output
    
    Returns:
        int or None: Number of online users or None if failed
    """
    # Normalize subreddit name for the API call (lowercase)
    subreddit = subreddit.lower()
    url = f'https://www.reddit.com/r/{subreddit}/about.json'
    
    # Enhanced headers to prevent caching and mimic a browser
    headers = {
        'User-Agent': 'RedditUserTracker/1.0 (by /u/YourUsername)',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Accept': 'application/json',
        'DNT': '1',
        'Connection': 'keep-alive'
    }
    
    if verbose:
        print(f"\n{'='*50}")
        print(f"Requesting data from: {url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
    
    try:
        # Make the request
        if verbose:
            print("Sending request...")
        response = requests.get(url, headers=headers)
        
        # Print status code
        if verbose:
            print(f"Response status code: {response.status_code}")
        
        # Ensure successful response
        response.raise_for_status()
        
        # Parse JSON response
        if verbose:
            print("Parsing JSON response...")
        data = response.json()
        
        # Debug: Print part of the JSON structure
        if verbose:
            print("Response structure (first level keys):", list(data.keys()))
            if 'data' in data:
                print("Data keys:", list(data['data'].keys()))
        
        # Check if we got the "active_user_count" field
        if 'data' in data and 'active_user_count' in data['data']:
            online_users = data['data']['active_user_count']
            if verbose:
                print(f"SUCCESS: Found {online_users} online users in r/{subreddit}")
            logger.info(f"Found {online_users} online users in r/{subreddit}")
            return online_users
        else:
            if verbose:
                print(f"WARNING: Could not find active_user_count for r/{subreddit}")
                print("Response data:", json.dumps(data, indent=2)[:500] + "...")  # Print first 500 chars
            logger.warning(f"Could not find active_user_count for r/{subreddit}")
            return None
    
    except requests.exceptions.HTTPError as e:
        if verbose:
            print(f"HTTP Error: {e}")
        logger.error(f"HTTP Error scraping r/{subreddit}: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        if verbose:
            print(f"Connection Error: {e}")
        logger.error(f"Connection Error scraping r/{subreddit}: {e}")
        return None
    except requests.exceptions.Timeout as e:
        if verbose:
            print(f"Timeout Error: {e}")
        logger.error(f"Timeout Error scraping r/{subreddit}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"Request Exception: {e}")
        logger.error(f"Request Exception scraping r/{subreddit}: {e}")
        return None
    except json.JSONDecodeError as e:
        if verbose:
            print(f"JSON Decode Error: {e}")
            print(f"Response content: {response.text[:500]}...")  # Print first 500 chars
        logger.error(f"JSON Decode Error scraping r/{subreddit}: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"Unexpected Error: {e}")
        logger.error(f"Error scraping r/{subreddit}: {e}")
        return None

def normalize_subreddit_names(data):
    """
    Normalize all subreddit names to lowercase and merge data for duplicates.
    """
    if not isinstance(data, dict):
        return data
        
    normalized_data = {}
    
    # Process each subreddit entry and normalize names
    for subreddit, points in data.items():
        # Convert to lowercase
        norm_name = subreddit.lower()
        
        # Initialize entry if needed
        if norm_name not in normalized_data:
            normalized_data[norm_name] = []
        
        # Add all data points
        normalized_data[norm_name].extend(points)
    
    return normalized_data

def migrate_data_format(old_data):
    """
    Migrates data from the old flat format to the new subreddit-grouped format.
    """
    new_data = {}
    
    # Group data by subreddit
    for item in old_data:
        subreddit = item.get("subreddit", "unknown").lower()  # Normalize to lowercase
        
        # Initialize subreddit entry if it doesn't exist
        if subreddit not in new_data:
            new_data[subreddit] = []
        
        # Add data point without the redundant subreddit field
        data_point = {
            "timestamp": item["timestamp"],
            "online_users": item["online_users"]
        }
        new_data[subreddit].append(data_point)
    
    return new_data

def save_data_to_json(data, filename=DATA_FILE, verbose=False):
    """
    Save the tracking data to a JSON file.
    The data is organized by subreddit name.
    """
    try:
        if verbose:
            print(f"\nSaving data to {filename}...")
        
        # Check if data is in the old flat format (list of dicts) and migrate if needed
        if isinstance(data, list):
            if verbose:
                print("Converting data to new format organized by subreddit...")
            data = migrate_data_format(data)
        
        # Normalize subreddit names (lowercase and combine duplicates)
        data = normalize_subreddit_names(data)
        
        # Save the organized data
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Count total data points
        total_points = sum(len(points) for points in data.values())
        if verbose:
            print(f"Successfully saved {total_points} data points across {len(data)} subreddits to {filename}")
        logger.info(f"Data saved to {filename}")
        return True
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to save data to {filename}: {e}")
        logger.error(f"Error saving data to {filename}: {e}")
        return False

def load_data_from_json(filename=DATA_FILE, verbose=False):
    """
    Load existing tracking data from a JSON file.
    Handles both the old flat format and the new subreddit-grouped format.
    """
    try:
        if os.path.exists(filename):
            if verbose:
                print(f"\nLoading data from existing file: {filename}")
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Check data format (old = list, new = dict)
            if isinstance(data, list):
                if verbose:
                    print(f"Found data in old format. Converting to new format organized by subreddit...")
                data = migrate_data_format(data)
            
            # Normalize subreddit names
            data = normalize_subreddit_names(data)
            
            # Save the normalized data back to the file
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Count total data points
            total_points = sum(len(points) for points in data.values())
            if verbose:
                print(f"Successfully loaded {total_points} data points across {len(data)} subreddits from {filename}")
            return data
        
        if verbose:
            print(f"\nNo existing file found at {filename}, starting with empty dataset")
        return {}  # Return empty dict instead of list
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to load data from {filename}: {e}")
        logger.error(f"Error loading data from {filename}: {e}")
        return {}