import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from scipy.optimize import curve_fit

st.set_page_config(
    page_title="Production Forecasting Tool",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
st.sidebar.title("🛢️ Production Forecasting Tool")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["Dashboard", "Upload Data", "Forecasting", "Type Curves", "Saved Results"])
st.sidebar.markdown("---")
st.sidebar.caption(f"User: Partha | {datetime.now().strftime('%d %b %Y')}")

# Session state
if 'df' not in st.session_state:
    st.session_state.df = None

# ==================== HELPER FUNCTIONS ====================
def exponential_decline(t, qi, di):
    return qi * np.exp(-di * t)

def hyperbolic_decline(t, qi, di, b):
    return qi / (1 + b * di * t) ** (1/b)

def fit_decline(dates, rates, model='exponential'):
    """Simple DCA fit"""
    t = np.arange(len(rates))
    rates = np.array(rates, dtype=float)
    
    # Remove zeros and negatives for fitting
    mask = rates > 0
    if mask.sum() < 3:
        return None, None, None
    
    t_fit = t[mask]
    r_fit = rates[mask]
    
    try:
        if model == 'exponential':
            popt, _ = curve_fit(exponential_decline, t_fit, r_fit, 
                              p0=[r_fit[0], 0.05], bounds=(0, [np.inf, 2]), maxfev=5000)
            qi, di = popt
            b = 0
        else:  # hyperbolic
            popt, _ = curve_fit(hyperbolic_decline, t_fit, r_fit,
                              p0=[r_fit[0], 0.05, 0.5], 
                              bounds=(0, [np.inf, 2, 2]), maxfev=5000)
            qi, di, b = popt
        return qi, di, b
    except:
        return None, None, None

def generate_forecast(dates, rates, months_ahead=24, model='exponential'):
    """Generate forecast"""
    qi, di, b = fit_decline(dates, rates, model)
    if qi is None:
        return None, None
    
    t_hist = np.arange(len(rates))
    t_future = np.arange(len(rates), len(rates) + months_ahead)
    
    if model == 'exponential' or b == 0:
        hist_fit = exponential_decline(t_hist, qi, di)
        future = exponential_decline(t_future, qi, di)
    else:
        hist_fit = hyperbolic_decline(t_hist, qi, di, b)
        future = hyperbolic_decline(t_future, qi, di, b)
    
    last_date = pd.to_datetime(dates.iloc[-1])
    future_dates = [last_date + pd.DateOffset(months=i+1) for i in range(months_ahead)]
    
    return future_dates, future, hist_fit, qi, di, b

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
        st.info("Please upload data from the Upload Data page.")

# ==================== UPLOAD DATA ====================
elif page == "Upload Data":
    st.title("Upload Production Data")
    
    with st.expander("📋 Required Data Format", expanded=True):
        st.markdown("""
        **Excel / CSV must contain these columns:**
        
        | Column Name | Required | Example | Description |
        |-------------|----------|---------|-------------|
        | `Field` | Yes | RAVVA | Field or Well name |
        | `Date` | Yes | 2024-01-01 | Month start date |
        | `Oil_bbl` | Yes | 252161 | Monthly oil production (barrels) |
        | `Oil_MT` | Optional | 33796 | Monthly oil (metric tonnes) |
        | `Associated_Gas_m3` | Optional | 6054304 | Associated gas (m³) |
        | `NonAssociated_Gas_m3` | Optional | 0 | Non-associated gas (m³) |
        
        **Notes:**
        - Date format: YYYY-MM-DD preferred
        - Multiple fields can be in one file
        - Minimum 6 months of data recommended for forecasting
        """)
    
    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            df.columns = df.columns.str.strip()
            
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            elif 'ACTIVITY_MONTH' in df.columns:
                df['Date'] = pd.to_datetime(df['ACTIVITY_MONTH'], errors='coerce')
                if 'FIELD_NAME' in df.columns:
                    df = df.rename(columns={'FIELD_NAME': 'Field'})
                if 'OIL_BBL' in df.columns:
                    df = df.rename(columns={'OIL_BBL': 'Oil_bbl'})
            
            missing = []
            if 'Field' not in df.columns: missing.append('Field')
            if 'Date' not in df.columns: missing.append('Date')
            if 'Oil_bbl' not in df.columns: missing.append('Oil_bbl')
            
            if missing:
                st.error(f"Missing required columns: {', '.join(missing)}")
            else:
                st.session_state.df = df.dropna(subset=['Date', 'Field'])
                st.success(f"File loaded successfully: {uploaded_file.name}")
                st.dataframe(df.head(12), use_container_width=True)
                if 'Field' in df.columns:
                    st.write(f"**Fields found:** {', '.join(df['Field'].dropna().unique()[:8])}")
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ==================== FORECASTING ====================
elif page == "Forecasting":
    st.title("Decline Curve Forecasting")
    
    if st.session_state.df is None:
        st.warning("Please upload data first from the Upload Data page.")
    else:
        df = st.session_state.df.copy()
        
        col_left, col_center = st.columns([1, 2.2])
        
        with col_left:
            st.subheader("Controls")
            fields = sorted(df['Field'].dropna().unique())
            selected_field = st.selectbox("Select Field", fields)
            
            field_data = df[df['Field'] == selected_field].sort_values('Date').reset_index(drop=True)
            
            st.write(f"**Records:** {len(field_data)}")
            if len(field_data) > 0:
                st.write(f"**From:** {field_data['Date'].min().strftime('%b %Y')}")
                st.write(f"**To:** {field_data['Date'].max().strftime('%b %Y')}")
            
            model = st.selectbox("Decline Model", ["Exponential", "Hyperbolic"])
            months_ahead = st.slider("Forecast Months Ahead", 6, 60, 24)
            
            if st.button("Generate Forecast", type="primary"):
                st.session_state.do_forecast = True
                st.session_state.selected_field = selected_field
                st.session_state.model = model
                st.session_state.months = months_ahead
        
        with col_center:
            if st.session_state.get('do_forecast', False):
                field = st.session_state.selected_field
                field_data = df[df['Field'] == field].sort_values('Date').reset_index(drop=True)
                
                rates = field_data['Oil_bbl'].fillna(0).values
                dates = field_data['Date']
                
                result = generate_forecast(dates, rates, 
                                         months_ahead=st.session_state.months,
                                         model=st.session_state.model.lower())
                
                if result[0] is None:
                    st.error("Could not fit decline curve. Need more non-zero data points.")
                else:
                    future_dates, future_rates, hist_fit, qi, di, b = result
                    
                    fig = go.Figure()
                    # Historical
                    fig.add_trace(go.Scatter(
                        x=dates, y=rates, mode='markers', name='Historical',
                        marker=dict(size=6, color='#1f77b4')
                    ))
                    # Fitted
                    fig.add_trace(go.Scatter(
                        x=dates, y=hist_fit, mode='lines', name='Fitted',
                        line=dict(color='orange', width=2)
                    ))
                    # Forecast
                    fig.add_trace(go.Scatter(
                        x=future_dates, y=future_rates, mode='lines', name='Forecast',
                        line=dict(color='red', width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title=f"{field} — Oil Forecast ({st.session_state.model})",
                        xaxis_title="Date",
                        yaxis_title="Oil (bbl/month)",
                        height=520,
                        hovermode='x unified',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Parameters
                    st.subheader("Decline Parameters")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("qi (bbl/month)", f"{qi:,.0f}")
                    c2.metric("Di (nominal)", f"{di:.4f}")
                    if st.session_state.model == "Hyperbolic":
                        c3.metric("b-factor", f"{b:.3f}")
                    else:
                        c3.metric("b-factor", "0 (Exponential)")

# ==================== TYPE CURVES ====================
elif page == "Type Curves":
    st.title("Type Curve Generation")
    
    if st.session_state.df is None:
        st.warning("Please upload data first.")
    else:
        df = st.session_state.df.copy()
        fields = sorted(df['Field'].dropna().unique())
        
        selected_fields = st.multiselect("Select Fields for Type Curve", fields, default=fields[:3] if len(fields)>=3 else fields)
        
        if st.button("Generate Type Curves", type="primary") and selected_fields:
            # Normalize each field to start from peak or first point
            all_curves = []
            for f in selected_fields:
                fdata = df[df['Field']==f].sort_values('Date')
                rates = fdata['Oil_bbl'].fillna(0).values
                if len(rates) < 6 or rates.max() == 0:
                    continue
                # Normalize by max rate
                norm = rates / rates.max()
                all_curves.append(norm[:36])  # first 36 months
            
            if len(all_curves) < 2:
                st.error("Need at least 2 fields with sufficient data.")
            else:
                # Pad to same length
                max_len = max(len(c) for c in all_curves)
                padded = [np.pad(c, (0, max_len-len(c)), constant_values=np.nan) for c in all_curves]
                arr = np.array(padded)
                
                p10 = np.nanpercentile(arr, 90, axis=0)  # higher is P10 in production
                p50 = np.nanpercentile(arr, 50, axis=0)
                p90 = np.nanpercentile(arr, 10, axis=0)
                
                months = np.arange(1, max_len+1)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=months, y=p10, name='P10', line=dict(color='green', width=2)))
                fig.add_trace(go.Scatter(x=months, y=p50, name='P50', line=dict(color='blue', width=3)))
                fig.add_trace(go.Scatter(x=months, y=p90, name='P90', line=dict(color='red', width=2)))
                
                fig.update_layout(
                    title="Normalized Type Curves (P10 / P50 / P90)",
                    xaxis_title="Months from Start",
                    yaxis_title="Normalized Rate",
                    height=500,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Based on {len(all_curves)} fields. Rates normalized to each field's maximum.")

# ==================== SAVED RESULTS ====================
elif page == "Saved Results":
    st.title("Saved Forecasts")
    st.info("Save and compare feature will be added in the next version.")
