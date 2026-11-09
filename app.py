import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Production Forecasting Tool",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar Navigation
st.sidebar.title("🛢️ Forecasting Tool")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Upload Data", "Forecasting", "Type Curves", "Saved Results"]
)

st.sidebar.markdown("---")
st.sidebar.caption(f"User: Partha | {datetime.now().strftime('%d %b %Y')}")

# ==================== DASHBOARD ====================
if page == "Dashboard":
    st.title("Dashboard")
    st.markdown("### Production Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Wells", "128", "+4")
    col2.metric("Active Wells", "96", "-2")
    col3.metric("Last Month Oil (bbl)", "18,450", "+3.2%")
    col4.metric("Last Month Gas (MMscf)", "245", "+1.8%")
    
    st.markdown("### Recent Activity")
    st.info("No recent forecasts yet. Start by uploading data.")

# ==================== UPLOAD DATA ====================
elif page == "Upload Data":
    st.title("Upload Production Data")
    
    uploaded_file = st.file_uploader(
        "Upload Excel or CSV file",
        type=["xlsx", "xls", "csv"],
        help="Required columns: Well_Name, Date, Oil_Rate, Gas_Rate, Water_Rate"
    )
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success("File uploaded successfully!")
            st.subheader("Data Preview")
            st.dataframe(df.head(20), use_container_width=True)
            
            st.subheader("Column Mapping")
            cols = df.columns.tolist()
            c1, c2, c3 = st.columns(3)
            well_col = c1.selectbox("Well Name", cols)
            date_col = c2.selectbox("Date", cols)
            oil_col = c3.selectbox("Oil Rate", cols)
            
            if st.button("Save to Database", type="primary"):
                st.success("Data saved successfully! (Placeholder)")
                
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ==================== FORECASTING ====================
elif page == "Forecasting":
    st.title("Decline Curve Forecasting")
    
    col_left, col_center, col_right = st.columns([1, 2, 1])
    
    with col_left:
        st.subheader("Controls")
        wells = st.multiselect("Select Wells", ["Well-A1", "Well-B2", "Well-C3", "Well-D4"])
        fluid = st.selectbox("Fluid", ["Oil", "Gas", "Water"])
        model = st.selectbox("Decline Model", ["Exponential", "Hyperbolic", "Harmonic", "Multi-segment"])
        
        st.markdown("**Manual Parameters**")
        qi = st.number_input("qi (Initial Rate)", value=500.0)
        di = st.number_input("Di (Decline Rate)", value=0.15, format="%.3f")
        b = st.number_input("b-factor", value=0.8, min_value=0.0, max_value=2.0)
        
        if st.button("Auto Fit", type="primary"):
            st.success("Auto-fit completed (Placeholder)")
        
        if st.button("Generate Forecast"):
            st.session_state['forecast_ready'] = True
    
    with col_center:
        st.subheader("Forecast Chart")
        # Dummy chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1,2,3,4,5], y=[500,420,360,310,270], mode='markers', name='Historical'))
        fig.add_trace(go.Scatter(x=[1,2,3,4,5,6,7,8], y=[500,420,360,310,270,235,205,180], mode='lines', name='Forecast'))
        fig.update_layout(height=450, margin=dict(l=20,r=20,t=30,b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        st.subheader("Results")
        st.metric("EUR", "1,245,000 bbl")
        st.metric("Remaining", "385,000 bbl")
        st.metric("End Date", "Mar 2032")
        
        if st.button("Save Forecast"):
            st.success("Forecast saved!")
        if st.button("Export Excel"):
            st.info("Export feature coming soon")

# ==================== TYPE CURVES ====================
elif page == "Type Curves":
    st.title("Type Curve Generation")
    
    c1, c2 = st.columns(2)
    area = c1.selectbox("Select Area / Field", ["Field-A", "Field-B", "Block-X"])
    fluid_tc = c2.selectbox("Fluid", ["Oil", "Gas"])
    
    st.subheader("P10 / P50 / P90 Type Curves")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(range(1,25)), y=[1000/(i**0.3) for i in range(1,25)], name="P10"))
    fig2.add_trace(go.Scatter(x=list(range(1,25)), y=[800/(i**0.4) for i in range(1,25)], name="P50"))
    fig2.add_trace(go.Scatter(x=list(range(1,25)), y=[600/(i**0.5) for i in range(1,25)], name="P90"))
    fig2.update_layout(height=500)
    st.plotly_chart(fig2, use_container_width=True)

# ==================== SAVED RESULTS ====================
elif page == "Saved Results":
    st.title("Saved Forecasts")
    
    data = {
        "Well": ["Well-A1", "Well-B2", "Well-C3"],
        "Date Saved": ["05 Nov 2026", "03 Nov 2026", "28 Oct 2026"],
        "EUR": ["1.24 MMbbl", "0.87 MMbbl", "2.15 MMbbl"],
        "Model": ["Hyperbolic", "Exponential", "Multi-segment"]
    }
    st.dataframe(pd.DataFrame(data), use_container_width=True)