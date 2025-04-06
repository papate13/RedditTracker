import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import logging

# Import shared functionality from the core module
from reddit_tracker_core import (
    get_online_users,
    save_data_to_json, 
    load_data_from_json
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def plot_data(data, subreddit):
    """
    Create a plot of online users over time.
    """
    if not data or subreddit not in data or not data[subreddit]:
        print(f"No data to plot for r/{subreddit}!")
        logger.warning(f"No data to plot for r/{subreddit}")
        return
    
    subreddit_data = data[subreddit]
    print(f"\nCreating plot for r/{subreddit} with {len(subreddit_data)} data points...")
    
    timestamps = [datetime.fromisoformat(item["timestamp"]) for item in subreddit_data]
    online_counts = [item["online_users"] for item in subreddit_data]
    
    print(f"Time range: {min(timestamps)} to {max(timestamps)}")
    print(f"User count range: {min(online_counts)} to {max(online_counts)}")
    
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, online_counts, marker='o', linestyle='-')
    plt.title(f"Online Users in r/{subreddit}")
    plt.xlabel("Time")
    plt.ylabel("Number of Online Users")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save the plot as an image
    plot_filename = f"{subreddit}_online_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(plot_filename)
    print(f"Plot saved as {plot_filename}")
    logger.info(f"Plot saved as {plot_filename}")
    
    # Show the plot
    plt.show()

def main():
    """
    Main function to run the Reddit tracker.
    """
    print("\n" + "="*50)
    print("Reddit User Tracker")
    print("="*50)
    
    subreddit = input("Enter the subreddit name (without r/): ")
    
    action = input("Do you want to (1) collect data or (2) plot existing data? Enter 1 or 2: ")
    
    if action == "1":
        # Collecting data
        interval_minutes = float(input("Enter the time interval between checks (in minutes): "))
        interval_seconds = interval_minutes * 60
        
        # Load existing data or start with an empty dict
        tracking_data = load_data_from_json(verbose=True)
        
        # Initialize subreddit entry if it doesn't exist
        if subreddit not in tracking_data:
            tracking_data[subreddit] = []
        
        try:
            print("\n" + "="*50)
            logger.info(f"Starting to track online users for r/{subreddit}...")
            print(f"Starting to track online users for r/{subreddit}")
            print(f"Interval: {interval_minutes} minutes ({interval_seconds} seconds)")
            print(f"Press Ctrl+C to stop tracking")
            print("="*50 + "\n")
            
            count = 0
            while True:
                count += 1
                print(f"\n[Check #{count}] Fetching online user count...")
                
                # Get current online users
                online_users = get_online_users(subreddit, verbose=True)
                
                if online_users is not None:
                    timestamp = datetime.now().isoformat()
                    data_point = {
                        "timestamp": timestamp,
                        "online_users": online_users
                    }
                    
                    tracking_data[subreddit].append(data_point)
                    save_data_to_json(tracking_data, verbose=True)
                    
                    print(f"RESULT: r/{subreddit} has {online_users} users online at {timestamp}")
                    logger.info(f"r/{subreddit} has {online_users} users online at {timestamp}")
                
                # Wait for the next check
                next_check = datetime.now() + timedelta(seconds=interval_seconds)
                print(f"\nNext check scheduled for: {next_check.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Waiting {interval_minutes} minutes...")
                time.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\nTracking stopped by user (Ctrl+C pressed)")
            logger.info("Tracking stopped by user")
            save_data_to_json(tracking_data, verbose=True)
            
            plot_choice = input("Do you want to plot the collected data? (y/n): ")
            if plot_choice.lower() == 'y':
                plot_data(tracking_data, subreddit)
    
    elif action == "2":
        # Plotting existing data
        tracking_data = load_data_from_json(verbose=True)
        
        # List available subreddits
        if not tracking_data:
            print("No tracking data found.")
            return
        
        print("\nAvailable subreddits:")
        for idx, sub in enumerate(tracking_data.keys(), 1):
            data_points = len(tracking_data[sub])
            print(f"{idx}. r/{sub} ({data_points} data points)")
        
        # Allow user to select from available subreddits if their input doesn't match
        if subreddit not in tracking_data:
            print(f"\nr/{subreddit} not found in existing data.")
            use_available = input("Would you like to select from available subreddits? (y/n): ")
            
            if use_available.lower() == 'y':
                try:
                    selected_idx = int(input("Enter the number of the subreddit to plot: ")) - 1
                    subreddit = list(tracking_data.keys())[selected_idx]
                except (ValueError, IndexError):
                    print("Invalid selection. Exiting.")
                    return
            else:
                print("Exiting.")
                return
        
        # Plot data for the selected subreddit
        plot_data(tracking_data, subreddit)
    
    else:
        print("Invalid choice. Please run the script again and select 1 or 2.")

if __name__ == "__main__":
    main()