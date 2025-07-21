"""
Project Victoria Dashboard - Main Streamlit Application
Real-time visualization of OBU localization using RSSI trilateration
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json

# Import project modules
from config import config
from mqtt_handler import MQTTHandler
from dashboard.trilateration import RSSITrilaterationSolver
from field_config import validate_rsu_positions
from data_processing import format_rssi_for_display, calculate_data_rate

# Page configuration
st.set_page_config(
    page_title="Project Victoria Dashboard",
    page_icon="🚧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #2E86AB;
        margin-bottom: 1rem;
    }
    .status-connected {
        color: #28a745;
        font-weight: bold;
    }
    .status-disconnected {
        color: #dc3545;
        font-weight: bold;
    }
    .metric-box {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2E86AB;
    }
    .rssi-bar {
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize Streamlit session state"""
    if 'mqtt_handler' not in st.session_state:
        st.session_state.mqtt_handler = None
    
    if 'position_data' not in st.session_state:
        st.session_state.position_data = []
    
    if 'rssi_data' not in st.session_state:
        st.session_state.rssi_data = {}
    
    if 'field_width' not in st.session_state:
        st.session_state.field_width = config.field.width
    
    if 'field_height' not in st.session_state:
        st.session_state.field_height = config.field.height
    
    if 'rsu_positions' not in st.session_state:
        st.session_state.rsu_positions = dict(config.field.rsu_positions)
    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    
    if 'show_trail' not in st.session_state:
        st.session_state.show_trail = True
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    
    if 'connection_mode' not in st.session_state:
        st.session_state.connection_mode = None  # None, 'aws_iot', 'demo'

def data_callback(position_data):
    """Callback function for new position data"""
    # Don't access st.session_state from background thread
    # Just pass the data through - it will be picked up by get_latest_data()
    pass

def create_field_plot():
    """Create the main field visualization plot"""
    fig = go.Figure()
    
    # Field boundary
    fig.add_shape(
        type="rect",
        x0=0, y0=0,
        x1=st.session_state.field_width,
        y1=st.session_state.field_height,
        line=dict(color="black", width=2),
        fillcolor="rgba(240, 248, 255, 0.1)"
    )
    
    # RSU positions
    rsu_x = [pos[0] for pos in st.session_state.rsu_positions.values()]
    rsu_y = [pos[1] for pos in st.session_state.rsu_positions.values()]
    rsu_names = list(st.session_state.rsu_positions.keys())
    
    fig.add_trace(go.Scatter(
        x=rsu_x, y=rsu_y,
        mode='markers+text',
        marker=dict(size=15, color='red', symbol='diamond'),
        text=rsu_names,
        textposition="top center",
        name='RSUs',
        hovertemplate='<b>%{text}</b><br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
    ))
    
    # Position trail
    if st.session_state.show_trail and st.session_state.position_data:
        trail_x = [pos['x'] for pos in st.session_state.position_data]
        trail_y = [pos['y'] for pos in st.session_state.position_data]
        
        # Trail line
        fig.add_trace(go.Scatter(
            x=trail_x, y=trail_y,
            mode='lines',
            line=dict(color='blue', width=2, dash='dot'),
            name='Trail',
            opacity=0.6,
            hoverinfo='skip'
        ))
        
        # Current position
        if trail_x and trail_y:
            fig.add_trace(go.Scatter(
                x=[trail_x[-1]], y=[trail_y[-1]],
                mode='markers',
                marker=dict(size=20, color='blue', symbol='circle'),
                name='Current Position',
                hovertemplate='<b>Current Position</b><br>X: %{x:.2f}m<br>Y: %{y:.2f}m<extra></extra>'
            ))
    
    # Layout
    fig.update_layout(
        title="Construction Site Field View",
        xaxis_title="X Position (meters)",
        yaxis_title="Y Position (meters)",
        xaxis=dict(range=[-5, st.session_state.field_width + 5]),
        yaxis=dict(range=[-5, st.session_state.field_height + 5]),
        showlegend=True,
        height=500,
        template="plotly_white"
    )
    
    # Equal aspect ratio
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    
    return fig

def create_rssi_chart():
    """Create RSSI strength visualization"""
    if not st.session_state.rssi_data:
        return go.Figure().add_annotation(
            text="No RSSI data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
    
    rsu_ids = list(st.session_state.rssi_data.keys())
    rssi_values = [data['rssi'] for data in st.session_state.rssi_data.values()]
    
    # Color coding based on signal strength
    colors = []
    for rssi in rssi_values:
        if rssi >= -60:
            colors.append('green')
        elif rssi >= -80:
            colors.append('orange')
        else:
            colors.append('red')
    
    fig = go.Figure(data=[
        go.Bar(
            x=rsu_ids,
            y=rssi_values,
            marker_color=colors,
            text=[f"{rssi:.1f} dBm" for rssi in rssi_values],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="RSSI Signal Strength",
        xaxis_title="RSU ID",
        yaxis_title="RSSI (dBm)",
        yaxis=dict(range=[-100, -30]),
        height=300,
        template="plotly_white"
    )
    
    return fig

def sidebar_configuration():
    """Sidebar configuration panel"""
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Connection controls
        st.subheader("Connection")
        
        if st.session_state.mqtt_handler is None:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔌 AWS IoT", type="primary", use_container_width=True):
                    with st.spinner("Connecting to AWS IoT..."):
                        st.session_state.mqtt_handler = MQTTHandler(data_callback, demo_mode=False)
                        st.session_state.connection_mode = 'aws_iot'
                        if st.session_state.mqtt_handler.connect():
                            st.session_state.mqtt_handler.start_background_processing()
                            st.success("Connected to AWS IoT!")
                            st.rerun()
                        else:
                            st.error("AWS IoT connection failed!")
                            st.session_state.mqtt_handler = None
                            st.session_state.connection_mode = None
            
            with col2:
                if st.button("🎮 Demo Mode", type="secondary", use_container_width=True):
                    with st.spinner("Starting demo mode..."):
                        st.session_state.mqtt_handler = MQTTHandler(data_callback, demo_mode=True)
                        st.session_state.connection_mode = 'demo'
                        if st.session_state.mqtt_handler.connect():
                            st.session_state.mqtt_handler.start_background_processing()
                            st.success("Demo mode started!")
                            st.rerun()
                        else:
                            st.error("Demo mode failed to start!")
                            st.session_state.mqtt_handler = None
                            st.session_state.connection_mode = None
        else:
            status = st.session_state.mqtt_handler.get_connection_status()
            if status['connected']:
                st.success(f"✅ Connected: {status['client_type']}")
                
                if st.button("🔌 Disconnect"):
                    st.session_state.mqtt_handler.stop_background_processing()
                    st.session_state.mqtt_handler.disconnect()
                    st.session_state.mqtt_handler = None
                    st.session_state.connection_mode = None
                    st.rerun()
            else:
                st.error("❌ Disconnected")
                if st.button("🔄 Reconnect"):
                    if st.session_state.mqtt_handler.connect():
                        st.session_state.mqtt_handler.start_background_processing()
                        st.success("Reconnected!")
                        st.rerun()
        
        st.divider()
        
        # Field configuration
        st.subheader("Field Settings")
        
        new_width = st.number_input(
            "Field Width (m)",
            min_value=10.0,
            max_value=1000.0,
            value=st.session_state.field_width,
            step=5.0
        )
        
        new_height = st.number_input(
            "Field Height (m)",
            min_value=10.0,
            max_value=1000.0,
            value=st.session_state.field_height,
            step=5.0
        )
        
        st.divider()
        
        # RSU positions
        st.subheader("RSU Positions")
        
        new_rsu_positions = {}
        
        for rsu_id in ['RSU1', 'RSU2', 'RSU3']:
            col1, col2 = st.columns(2)
            with col1:
                x = st.number_input(
                    f"{rsu_id} X",
                    min_value=0.0,
                    max_value=new_width,
                    value=st.session_state.rsu_positions.get(rsu_id, (0, 0))[0],
                    step=1.0,
                    key=f"{rsu_id}_x"
                )
            with col2:
                y = st.number_input(
                    f"{rsu_id} Y",
                    min_value=0.0,
                    max_value=new_height,
                    value=st.session_state.rsu_positions.get(rsu_id, (0, 0))[1],
                    step=1.0,
                    key=f"{rsu_id}_y"
                )
            
            new_rsu_positions[rsu_id] = (x, y)
        
        if st.button("📍 Apply Configuration", type="primary"):
            st.session_state.field_width = new_width
            st.session_state.field_height = new_height
            st.session_state.rsu_positions = new_rsu_positions
            
            # Validate positions
            errors = validate_rsu_positions(new_rsu_positions, new_width, new_height)
            if errors:
                for rsu_id, error in errors.items():
                    st.error(f"{rsu_id}: {error}")
            else:
                st.success("Configuration applied successfully!")
                st.rerun()
        
        st.divider()
        
        # Display options
        st.subheader("Display Options")
        
        st.session_state.show_trail = st.checkbox(
            "Show Position Trail",
            value=st.session_state.show_trail
        )
        
        st.session_state.auto_refresh = st.checkbox(
            "Auto Refresh",
            value=st.session_state.auto_refresh
        )
        
        if st.button("🗑️ Clear Trail"):
            st.session_state.position_data = []
            if st.session_state.mqtt_handler:
                st.session_state.mqtt_handler.clear_history()
            st.success("Trail cleared!")
            st.rerun()

def main_dashboard():
    """Main dashboard content"""
    # Header
    st.markdown('<div class="main-header">🚧 Project Victoria Dashboard</div>', unsafe_allow_html=True)
    
    # Update data from MQTT handler
    if st.session_state.mqtt_handler:
        latest_data = st.session_state.mqtt_handler.get_latest_data()
        if latest_data['position']:
            # Update session state with latest data
            st.session_state.rssi_data = latest_data['rssi_data']
            st.session_state.position_data = latest_data['position_history']
            st.session_state.last_update = datetime.now()
    
    # Main content area
    col1, col2 = st.columns([0.7, 0.3])
    
    with col1:
        # Field visualization
        st.subheader("📍 Field Visualization")
        field_plot = create_field_plot()
        st.plotly_chart(field_plot, use_container_width=True)
    
    with col2:
        # Current position info
        st.subheader("📊 Current Status")
        
        if st.session_state.position_data:
            latest_pos = st.session_state.position_data[-1]
            
            col2a, col2b = st.columns(2)
            with col2a:
                st.metric("X Position", f"{latest_pos['x']:.2f} m")
                st.metric("Y Position", f"{latest_pos['y']:.2f} m")
            with col2b:
                st.metric("Accuracy", f"±{latest_pos['accuracy']:.1f} m")
                data_rate = calculate_data_rate(st.session_state.position_data)
                st.metric("Data Rate", f"{data_rate:.1f} Hz")
        else:
            st.info("No position data available")
        
        # RSSI display
        st.subheader("📡 RSSI Values")
        if st.session_state.rssi_data:
            for rsu_id, data in st.session_state.rssi_data.items():
                rssi_str = format_rssi_for_display(data['rssi'])
                st.markdown(f"**{rsu_id}:** `{rssi_str}`")
        else:
            st.info("No RSSI data available")
    
    # RSSI chart
    st.subheader("📈 Signal Strength")
    rssi_chart = create_rssi_chart()
    st.plotly_chart(rssi_chart, use_container_width=True)
    
    # Status bar
    st.divider()
    
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        if st.session_state.mqtt_handler:
            status = st.session_state.mqtt_handler.get_connection_status()
            if status['connected']:
                st.markdown(f'<span class="status-connected">● Connected to {status["client_type"]}</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-disconnected">● Disconnected</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-disconnected">● Not Connected</span>', unsafe_allow_html=True)
    
    with status_col2:
        if st.session_state.last_update:
            st.text(f"Last Update: {st.session_state.last_update.strftime('%H:%M:%S')}")
        else:
            st.text("Last Update: Never")
    
    with status_col3:
        data_points = len(st.session_state.position_data)
        st.text(f"Data Points: {data_points}")

def main():
    """Main application function"""
    init_session_state()
    
    # Sidebar configuration
    sidebar_configuration()
    
    # Main dashboard
    main_dashboard()
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(config.dashboard.update_interval)
        st.rerun()

if __name__ == "__main__":
    main()