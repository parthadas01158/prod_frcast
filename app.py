import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from scipy.optimize import curve_fit

st.set_page_config(page_title="Production Forecasting Tool", page_icon="🛢️", layout="wide")

st.sidebar.title("🛢️ Production Forecasting Tool")
page = st.sidebar.radio("Navigate", ["Dashboard", "Upload Data", "Forecasting", "Future Events"])

if 'df' not in st.session_state:
    st.session_state.df = None
if 'events' not in st.session_state:
    st.session_state.events = []

# ==================== HELPERS ====================
def exp_decline(t, qi, di):
    return qi * np.exp(-di * t)

def fit_base_decline(rates):
    t = np.arange(len(rates))
    rates = np.array(rates, dtype=float)
    mask = rates > 0
    if mask.sum() < 4:
        return None, None
    try:
        popt, _ = curve_fit(exp_decline, t[mask], rates[mask],
                          p0=[max(rates[mask]), 0.03], bounds=(0, [np.inf, 1]), maxfev=2000)
        return float(popt[0]), float(popt[1])
    except:
        return None, None

def build_forecast(hist_dates, hist_rates, events, months=36):
    qi, di = fit_base_decline(hist_rates)
    if qi is None:
        return None
    
    last_date = pd.to_datetime(hist_dates.iloc[-1])
    future_dates = pd.date_range(last_date + pd.DateOffset(months=1), periods=months, freq='MS')
    t = np.arange(len(hist_rates), len(hist_rates) + months)
    base = exp_decline(t, qi, di)
    
    df_f = pd.DataFrame({'Date': future_dates, 'Base': base, 'Total': base.copy()})
    
    for ev in events:
        start = pd.to_datetime(ev['start'])
        if ev['type'] == 'New Well':
            qi_w = ev['qi']
            di_w = ev['di']
            # Months since well start
            months_on = ((df_f['Date'] - start).dt.days / 30.44).clip(lower=0)
            well_rate = np.where(df_f['Date'] >= start, exp_decline(months_on, qi_w, di_w), 0)
            df_f['Total'] += well_rate
        
        elif ev['type'] == 'Water Injection':
            # Simple response: oil uplift proportional to injection (with lag)
            inj_start = start
            inj_rate = ev.get('inj_rate', 5000)  # bbl/month water
            response_factor = ev.get('response', 0.08)  # oil bbl per water bbl
            lag = ev.get('lag', 3)
            
            months_since = ((df_f['Date'] - inj_start).dt.days / 30.44)
            active = months_since >= lag
            # Ramp up injection effect over 6 months
            ramp = np.clip((months_since - lag) / 6, 0, 1)
            uplift = np.where(active, inj_rate * response_factor * ramp, 0)
            df_f['Total'] += uplift
    
    return df_f, qi, di

# ==================== UPLOAD ====================
if page == "Upload Data":
    st.title("Upload Production Data")
    st.markdown("**Required columns:** `Field`, `Date`, `Oil_bbl`")
    f = st.file_uploader("Upload file", type=["xlsx", "csv"])
    if f:
        df = pd.read_excel(f) if str(f.name).endswith('xlsx') else pd.read_csv(f)
        df.columns = df.columns.str.strip()
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        st.session_state.df = df.dropna(subset=['Date', 'Field'])
        st.success(f"Loaded {len(df)} rows")
        st.dataframe(df.head(8))

# ==================== FUTURE EVENTS ====================
elif page == "Future Events":
    st.title("Future Development Plan")
    
    tab1, tab2 = st.tabs(["Add New Well", "Add Water Injection"])
    
    with tab1:
        st.subheader("New Well")
        with st.form("new_well"):
            c1, c2, c3 = st.columns(3)
            start = c1.date_input("Production Start Date")
            qi = c2.number_input("Initial Rate qi (bbl/month)", value=18000, step=1000)
            di = c3.number_input("Decline Rate Di (monthly)", value=0.025, step=0.005, format="%.3f")
            name = st.text_input("Well Name (optional)", value=f"Well-{len(st.session_state.events)+1}")
            if st.form_submit_button("Add New Well"):
                st.session_state.events.append({
                    'type': 'New Well', 'name': name,
                    'start': str(start), 'qi': qi, 'di': di
                })
                st.success(f"Added {name}")
    
    with tab2:
        st.subheader("Water Injection")
        with st.form("water_inj"):
            c1, c2, c3 = st.columns(3)
            start = c1.date_input("Injection Start Date", key="inj_start")
            inj_rate = c2.number_input("Injection Rate (bbl water/month)", value=30000, step=5000)
            response = c3.number_input("Oil Response Factor", value=0.06, step=0.01, format="%.2f",
                                     help="Expected oil bbl per bbl water injected")
            lag = st.slider("Response Lag (months)", 1, 12, 4)
            if st.form_submit_button("Add Water Injection"):
                st.session_state.events.append({
                    'type': 'Water Injection',
                    'start': str(start),
                    'inj_rate': inj_rate,
                    'response': response,
                    'lag': lag
                })
                st.success("Water injection plan added")
    
    if st.session_state.events:
        st.subheader("Current Plan")
        st.dataframe(pd.DataFrame(st.session_state.events), use_container_width=True)
        if st.button("Clear All"):
            st.session_state.events = []
            st.rerun()

# ==================== FORECASTING ====================
elif page == "Forecasting":
    st.title("Forecast")
    
    if st.session_state.df is None:
        st.warning("Upload data first")
    else:
        df = st.session_state.df
        field = st.selectbox("Select Field", sorted(df['Field'].unique()))
        fdata = df[df['Field']==field].sort_values('Date')
        
        months = st.slider("Forecast Horizon (months)", 12, 72, 36)
        
        if st.button("Run Forecast", type="primary"):
            result = build_forecast(fdata['Date'], fdata['Oil_bbl'].fillna(0).values,
                                  st.session_state.events, months)
            if result:
                fcast, qi, di = result
                st.session_state.last_forecast = (fdata, fcast, field)
        
        if 'last_forecast' in st.session_state:
            fdata, fcast, field = st.session_state.last_forecast
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=fdata['Date'], y=fdata['Oil_bbl'],
                                   mode='markers', name='Historical', marker=dict(size=5)))
            fig.add_trace(go.Scatter(x=fcast['Date'], y=fcast['Base'],
                                   mode='lines', name='Base Decline', line=dict(dash='dot', color='gray')))
            fig.add_trace(go.Scatter(x=fcast['Date'], y=fcast['Total'],
                                   mode='lines', name='With Development', line=dict(color='red', width=2.5)))
            fig.update_layout(height=520, title=f"{field} — Forecast with FDP",
                            yaxis_title="Oil (bbl/month)", hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption(f"Base decline: qi ≈ {qi:,.0f} bbl/month, Di ≈ {di:.4f}")

elif page == "Dashboard":
    st.title("Dashboard")
    if st.session_state.df is not None:
        st.metric("Fields Loaded", st.session_state.df['Field'].nunique())
        st.metric("Events Planned", len(st.session_state.events))
    else:
        st.info("Upload production data to start")
