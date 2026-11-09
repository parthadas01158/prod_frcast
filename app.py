import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Production Forecasting Tool",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
st.sidebar.title("🛢️ Forecasting Tool")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["Dashboard", "Upload Data", "Forecasting", "Type Curves", "Saved Results"])
st.sidebar.markdown("---")
st.sidebar.caption(f"User: Partha | {datetime.now().strftime('%d %b %Y')}")

# Session state
if 'df' not in st.session_state:
    st.session_state.df = None

# ==================== DASHBOARD ====================
if page == "Dashboard":
    st.title("Dashboard")
    if st.session_state.df is not None:
        df = st.session_state.df
        st.success(f"Data loaded: {len(df)} rows | {df['Field'].nunique()} fields")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Fields", df['Field'].nunique())
        col2.metric("Date Range", f"{df['Date'].min().strftime('%b %Y')} – {df['Date'].max().strftime('%b %Y')}")
        col3.metric("Total Oil (bbl)", f"{df['Oil_bbl'].sum():,.0f}")
    else:
        st.info("Pehle Upload Data page se file load karo.")

# ==================== UPLOAD DATA ====================
elif page == "Upload Data":
    st.title("Upload Production Data")
    
    # Format instructions
    with st.expander("📋 Required Data Format (Click to expand)", expanded=True):
        st.markdown("""
        **Excel / CSV mein yeh columns hone chahiye:**
        
        | Column Name | Required | Example | Description |
        |-------------|----------|---------|-------------|
        | `Field` | Yes | RAVVA | Field / Well name |
        | `Date` | Yes | 2024-01-01 | Month start date (YYYY-MM-DD) |
        | `Oil_bbl` | Yes | 252161 | Monthly oil production (barrels) |
        | `Oil_MT` | Optional | 33796 | Monthly oil (metric tonnes) |
        | `Associated_Gas_m3` | Optional | 6054304 | Associated gas (m³) |
        | `NonAssociated_Gas_m3` | Optional | 0 | Non-associated gas (m³) |
        
        **Notes:**
        - Date format: `YYYY-MM-DD` or `DD-MM-YYYY` dono chalega
        - Numbers mein comma mat daalo
        - Empty cells allowed hain (optional columns mein)
        - Multiple fields ek hi file mein ho sakte hain
        """)
        
        st.info("Sample file download karke dekh sakte ho format samajhne ke liye.")
    
    uploaded_file = st.file_uploader(
        "Upload Excel or CSV",
        type=["xlsx", "xls", "csv"],
        help="Columns: Field, Date, Oil_bbl (minimum required)"
    )
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            df.columns = df.columns.str.strip()
            
            # Flexible date handling
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
            elif 'ACTIVITY_MONTH' in df.columns:
                df['Date'] = pd.to_datetime(df['ACTIVITY_MONTH'], errors='coerce')
                if 'FIELD_NAME' in df.columns:
                    df = df.rename(columns={'FIELD_NAME': 'Field'})
                if 'OIL_BBL' in df.columns:
                    df = df.rename(columns={'OIL_BBL': 'Oil_bbl'})
            
            # Basic validation
            missing = []
            if 'Field' not in df.columns:
                missing.append('Field')
            if 'Date' not in df.columns:
                missing.append('Date')
            if 'Oil_bbl' not in df.columns and 'OIL_BBL' not in df.columns:
                missing.append('Oil_bbl')
            
            if missing:
                st.error(f"Missing required columns: {', '.join(missing)}")
            else:
                st.session_state.df = df
                st.success(f"✅ File loaded successfully: {uploaded_file.name}")
                st.subheader("Data Preview")
                st.dataframe(df.head(15), use_container_width=True)
                
                if 'Field' in df.columns:
                    st.write(f"**Fields found:** {', '.join(df['Field'].dropna().unique()[:10])}")
                
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ==================== FORECASTING ====================
elif page == "Forecasting":
    st.title("Decline Curve Forecasting")
    
    if st.session_state.df is None:
        st.warning("Pehle Upload Data page se file load karo.")
    else:
        df = st.session_state.df.copy()
        
        col_left, col_center = st.columns([1, 2])
        
        with col_left:
            st.subheader("Controls")
            fields = sorted(df['Field'].dropna().unique())
            selected_field = st.selectbox("Select Field", fields)
            
            field_data = df[df['Field'] == selected_field].sort_values('Date')
            
            st.write(f"**Records:** {len(field_data)}")
            if len(field_data) > 0:
                st.write(f"**From:** {field_data['Date'].min().strftime('%b %Y')}")
                st.write(f"**To:** {field_data['Date'].max().strftime('%b %Y')}")
            
            available_cols = [c for c in ['Oil_bbl', 'Oil_MT', 'Associated_Gas_m3', 'NonAssociated_Gas_m3'] if c in field_data.columns]
            fluid = st.selectbox("Plot", available_cols if available_cols else ['Oil_bbl'])
            
            if st.button("Show Chart", type="primary"):
                st.session_state.show_chart = True
        
        with col_center:
            if st.session_state.get('show_chart', False) and selected_field:
                field_data = df[df['Field'] == selected_field].sort_values('Date')
                y_col = fluid if fluid in field_data.columns else 'Oil_bbl'
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=field_data['Date'],
                    y=field_data[y_col],
                    mode='lines+markers',
                    name=selected_field,
                    line=dict(width=2)
                ))
                fig.update_layout(
                    title=f"{selected_field} — {y_col}",
                    xaxis_title="Date",
                    yaxis_title=y_col,
                    height=500,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.subheader("Quick Stats")
                c1, c2, c3 = st.columns(3)
                c1.metric("Max", f"{field_data[y_col].max():,.0f}")
                c2.metric("Min", f"{field_data[y_col].min():,.0f}")
                c3.metric("Latest", f"{field_data[y_col].iloc[-1]:,.0f}")

# ==================== TYPE CURVES ====================
elif page == "Type Curves":
    st.title("Type Curve Generation")
    st.info("Coming in next version — multi-field comparison.")

# ==================== SAVED RESULTS ====================
elif page == "Saved Results":
    st.title("Saved Forecasts")
    st.info("Save feature will be added after DCA engine.")
