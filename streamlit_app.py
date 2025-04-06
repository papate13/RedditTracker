import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import logging
import threading
import time
import altair as alt
import matplotlib.pyplot as plt
import queue

# Import shared functionality from the core module
from reddit_tracker_core import (
    get_online_users,
    save_data_to_json, 
    load_data_from_json,
    DATA_FILE
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Reddit User Tracker",
    page_icon="📊",
    layout="wide"
)

# Session state initialization
if 'tracking_thread' not in st.session_state:
    st.session_state.tracking_thread = None
if 'tracking_active' not in st.session_state:
    st.session_state.tracking_active = False
if 'latest_data' not in st.session_state:
    st.session_state.latest_data = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'tracking_history' not in st.session_state:
    st.session_state.tracking_history = []
# Add a thread-safe queue for communication
if 'update_queue' not in st.session_state:
    st.session_state.update_queue = queue.Queue()

def track_subreddit(subreddit, interval_minutes, stop_event, update_queue):
    """Background tracking function"""
    try:
        # Record start time
        start_time = datetime.now()
        
        # Create a history entry locally (don't access session_state directly from thread)
        history_entry = {
            'subreddit': subreddit,
            'start_time': start_time,
            'status': 'active',
            'data_points': 0
        }
        
        # Send history entry to main thread via queue
        update_queue.put(('add_history', history_entry))
        
        # Load existing data
        tracking_data = load_data_from_json()
        
        # Initialize subreddit entry if it doesn't exist
        if subreddit not in tracking_data:
            tracking_data[subreddit] = []
        
        while not stop_event.is_set():
            # Get current online users
            online_users = get_online_users(subreddit)
            
            if online_users is not None:
                timestamp = datetime.now().isoformat()
                data_point = {
                    "timestamp": timestamp,
                    "online_users": online_users
                }
                
                tracking_data[subreddit].append(data_point)
                save_data_to_json(tracking_data)
                
                # Send update to main thread via queue
                update_queue.put(('update_latest', {
                    'timestamp': timestamp,
                    'online_users': online_users,
                    'subreddit': subreddit
                }))
                
                # Update local count
                history_entry['data_points'] += 1
                update_queue.put(('update_count', history_entry['data_points']))
            
            # Wait for the next check
            time.sleep(interval_minutes * 60)
            
        # Update history when stopped
        end_time = datetime.now()
        history_entry['end_time'] = end_time
        history_entry['duration'] = (end_time - start_time).total_seconds() / 60
        history_entry['status'] = 'completed'
        
        # Send final status update
        update_queue.put(('update_status', 'completed'))
        
    except Exception as e:
        logger.error(f"Tracking error: {str(e)}")
        update_queue.put(('error', str(e)))

def start_tracking():
    """Start tracking in a background thread"""
    if not st.session_state.subreddit:
        st.error("Please enter a subreddit name")
        return
        
    if st.session_state.tracking_active:
        st.warning("Tracking is already in progress")
        return
    
    # Clear previous error messages
    st.session_state.error_message = None
    
    # Reset queue
    st.session_state.update_queue = queue.Queue()
    
    # Create a stop event for the thread
    stop_event = threading.Event()
    
    # Create and start the tracking thread
    tracking_thread = threading.Thread(
        target=track_subreddit,
        args=(
            st.session_state.subreddit, 
            st.session_state.interval, 
            stop_event,
            st.session_state.update_queue
        )
    )
    tracking_thread.daemon = True
    tracking_thread.start()
    
    # Store thread and stop event in session state
    st.session_state.tracking_thread = tracking_thread
    st.session_state.stop_event = stop_event
    st.session_state.tracking_active = True
    
    # Add initial history entry in the main thread
    track_id = len(st.session_state.tracking_history) + 1
    st.session_state.tracking_history.append({
        'id': track_id,
        'subreddit': st.session_state.subreddit,
        'start_time': datetime.now(),
        'status': 'active',
        'data_points': 0
    })

def stop_tracking():
    """Stop the background tracking thread"""
    if not st.session_state.tracking_active:
        st.info("No active tracking to stop")
        return
        
    if hasattr(st.session_state, 'stop_event') and st.session_state.stop_event:
        st.session_state.stop_event.set()
        
    # Update history to reflect stopped status
    if st.session_state.tracking_history and st.session_state.tracking_history[-1]['status'] == 'active':
        entry = st.session_state.tracking_history[-1]
        entry['status'] = 'stopped'
        entry['end_time'] = datetime.now()
        entry['duration'] = (entry['end_time'] - entry['start_time']).total_seconds() / 60
    
    # Reset tracking state
    st.session_state.tracking_active = False
    st.session_state.tracking_thread = None
    st.success("Tracking stopped")

# Process any updates from the background thread
def process_queue_updates():
    if hasattr(st.session_state, 'update_queue'):
        queue_obj = st.session_state.update_queue
        try:
            # Process all available updates
            while not queue_obj.empty():
                action, data = queue_obj.get_nowait()
                
                if action == 'update_latest':
                    st.session_state.latest_data = data
                    
                elif action == 'update_count' and st.session_state.tracking_history:
                    st.session_state.tracking_history[-1]['data_points'] = data
                    
                elif action == 'update_status' and st.session_state.tracking_history:
                    st.session_state.tracking_history[-1]['status'] = data
                    st.session_state.tracking_history[-1]['end_time'] = datetime.now()
                    
                elif action == 'error':
                    st.session_state.error_message = f"Error: {data}"
                    if st.session_state.tracking_history:
                        st.session_state.tracking_history[-1]['status'] = 'error'
                        st.session_state.tracking_history[-1]['error'] = data
                        st.session_state.tracking_history[-1]['end_time'] = datetime.now()
                
        except queue.Empty:
            pass  # Queue is empty, no problem

# UI Components with enhanced styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #4B6BFF;
        text-align: center;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #4B6BFF;
        border-bottom: 2px solid #F0F2F6;
        padding-bottom: 0.5rem;
    }
    .info-box {
        background-color: #F0F2F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stButton>button {
        width: 100%;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Process any updates from the background thread
process_queue_updates()

st.markdown("<h1 class='main-header'>📊 Reddit User Tracker</h1>", unsafe_allow_html=True)

# Termination instructions in a more prominent location
st.info("⚠️ To stop the Streamlit app completely, press CTRL+C in the terminal where you started it")

tabs = st.tabs(["📝 Track Subreddit", "📈 View Data", "📜 Tracking History"])

# Track Subreddit Tab
with tabs[0]:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("<h2 class='section-header'>Track Online Users</h2>", unsafe_allow_html=True)
        
        # Input form
        with st.form("tracking_form"):
            st.session_state.subreddit = st.text_input(
                "Subreddit Name (without r/)",
                value=st.session_state.get('subreddit', "")
            )
            st.session_state.interval = st.slider(
                "Check Interval (minutes)",
                2.0, 60.0,  # Changed minimum from 0.5 to 2.0
                max(st.session_state.get('interval', 2.0), 2.0),  # Ensure default is at least 2.0
                0.5
            )
            start_button = st.form_submit_button("▶️ Start Tracking")
        
        # Handle button clicks
        if start_button:
            start_tracking()

        if st.button("⏹️ Stop Tracking"):
            stop_tracking()
        
        # Show tracking status
        if st.session_state.tracking_active:
            st.success(f"✅ Tracking r/{st.session_state.subreddit} every {st.session_state.interval} minutes")
            
            # Show latest data if available
            if st.session_state.latest_data:
                data = st.session_state.latest_data
                st.metric(
                    label=f"r/{data['subreddit']} Online Users", 
                    value=data['online_users'],
                    delta=None
                )
                st.caption(f"Last updated: {datetime.fromisoformat(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show error if any
        if st.session_state.error_message:
            st.error(st.session_state.error_message)
    
    with col2:
        st.markdown("<h2 class='section-header'>Current Data</h2>", unsafe_allow_html=True)
        data = load_data_from_json()
        
        if data:
            total_points = sum(len(points) for points in data.values())
            
            # Better visualization of stats
            stats_container = st.container()
            col1, col2 = stats_container.columns(2)
            with col1:
                st.metric("Subreddits", len(data))
            with col2:
                st.metric("Data Points", total_points)
            
            # List subreddits
            st.markdown("<h3>Tracked Subreddits</h3>", unsafe_allow_html=True)
            for subreddit, points in data.items():
                st.write(f"r/{subreddit}: {len(points)} points")
                
            # Add refresh button
            if st.button("🔄 Refresh Data"):
                st.rerun()  # Use rerun() instead of experimental_rerun()
        else:
            st.markdown("<div class='info-box'>No data collected yet.</div>", unsafe_allow_html=True)

# View Data Tab - Fixed columns nesting issue
with tabs[1]:
    st.markdown("<h2 class='section-header'>View & Analyze Data</h2>", unsafe_allow_html=True)
    
    # Load data
    data = load_data_from_json()
    
    if not data:
        st.warning("No data available to display. Start tracking subreddits first.")
    else:
        # Subreddit selection
        subreddit_names = list(data.keys())
        selected_subreddit = st.selectbox("Select Subreddit", subreddit_names)
        
        if selected_subreddit:
            subreddit_data = data[selected_subreddit]
            
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(subreddit_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Time range selection
            st.subheader("Select Time Range")
            date_min = df['timestamp'].min().date()
            date_max = df['timestamp'].max().date()
            
            # Use a container instead of nested columns
            date_container = st.container()
            left, right = date_container.columns(2)
            
            with left:
                start_date = st.date_input("Start Date", date_min, min_value=date_min, max_value=date_max)
            with right:
                end_date = st.date_input("End Date", date_max, min_value=date_min, max_value=date_max)
            
            # Filter data by selected date range
            mask = (df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)
            filtered_df = df[mask]
            
            # Display statistics
            st.subheader("Statistics")
            
            # Use another container for the metrics
            stats_container = st.container()
            col1, col2, col3 = stats_container.columns(3)
            
            with col1:
                st.metric("Average", f"{filtered_df['online_users'].mean():.1f} users")
            with col2:
                st.metric("Minimum", f"{filtered_df['online_users'].min()} users")
            with col3:
                st.metric("Maximum", f"{filtered_df['online_users'].max()} users")
            
            # Create interactive chart with improved styling
            st.subheader(f"Online Users for r/{selected_subreddit}")
            
            # A more visually appealing chart
            chart = alt.Chart(filtered_df).mark_area(
                line={'color': '#4B6BFF'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='white', offset=0),
                           alt.GradientStop(color='#4B6BFF', offset=1)],
                    x1=1,
                    x2=1,
                    y1=1,
                    y2=0
                )
            ).encode(
                x=alt.X('timestamp:T', title='Time'),
                y=alt.Y('online_users:Q', title='Online Users'),
                tooltip=['timestamp:T', 'online_users:Q']
            ).properties(
                height=400
            ).interactive()
            
            st.altair_chart(chart, use_container_width=True)
            
            # Display raw data if wanted
            with st.expander("View Raw Data"):
                st.dataframe(filtered_df, use_container_width=True)
            
            # Download data option
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"{selected_subreddit}_data.csv",
                mime="text/csv",
            )

# New Tracking History Tab - Fixed NaT handling
with tabs[2]:
    st.markdown("<h2 class='section-header'>Tracking History</h2>", unsafe_allow_html=True)
    
    if not st.session_state.tracking_history:
        st.info("No tracking history available yet.")
    else:
        # Convert history to DataFrame
        history_df = pd.DataFrame(st.session_state.tracking_history)
        
        # Format for display with proper NaT handling
        display_df = history_df.copy()
        if 'start_time' in display_df.columns:
            display_df['start_time'] = display_df['start_time'].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else ''
            )
        if 'end_time' in display_df.columns:
            display_df['end_time'] = display_df['end_time'].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else ''
            )
        if 'duration' in display_df.columns:
            display_df['duration'] = display_df['duration'].apply(
                lambda x: f"{x:.1f} minutes" if pd.notna(x) else ''
            )
            
        # Display the table
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                'status': st.column_config.Column('Status', help='Current tracking status', width='medium'),
                'subreddit': st.column_config.Column('Subreddit', help='Tracked subreddit', width='medium'),
                'data_points': st.column_config.Column('Data Points', help='Number of data points collected', width='small'),
                'start_time': st.column_config.Column('Start Time', help='When tracking started', width='medium'),
                'end_time': st.column_config.Column('End Time', help='When tracking ended', width='medium'),
                'duration': st.column_config.Column('Duration', help='Total tracking time', width='small')
            }
        )
        
        # Clean history button
        if st.button("🗑️ Clear History"):
            st.session_state.tracking_history = []
            st.success("History cleared")
            st.rerun()  # Use rerun() instead of experimental_rerun()

# About section in sidebar with disclaimer
with st.sidebar:
    st.image("https://styles.redditmedia.com/t5_6/styles/communityIcon_a8uzjit9bwr21.png", width=80)
    st.title("Reddit User Tracker")
    
    st.markdown("""
    This app tracks the number of online users in subreddits over time.
    
    #### Features
    - ✅ Track multiple subreddits
    - 📈 Visualize user activity
    - 📊 Analyze trends over time
    - 📥 Export data in CSV format
    """)
    
    # Add Reddit disclaimer with attention-grabbing styling
    st.markdown("""
    <div style="background-color: #ffecb3; padding: 10px; border-radius: 5px; border-left: 4px solid #ffa000; margin: 10px 0;">
        <strong>⚠️ DISCLAIMER</strong><br>
        This is NOT an official Reddit product. This application is not affiliated with, endorsed by, or connected to Reddit, Inc. in any way.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("""
    ### Instructions
    
    1. Enter a subreddit name
    2. Set the check interval
    3. Start tracking
    4. View results in the data tab
    
    **To completely exit**: Press CTRL+C in the terminal where you started Streamlit.
    """)

    # Show version info
    st.markdown("---")
    st.caption("Reddit User Tracker v1.0")