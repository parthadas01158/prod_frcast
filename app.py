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
    """Exponential decline: q = qi * exp(-di * t)"""
    return qi * np.exp(-di * t)

def fit_base_decline(rates):
    """Fit exponential decline to historical rates"""
    rates = np.array(rates, dtype=float)
    t = np.arange(len(rates))
    mask = rates > 0
    if mask.sum() < 4:
        return None, None
    try:
        popt, _ = curve_fit(
            exp_decline, t[mask], rates[mask],
            p0=[np.max(rates[mask]), 0.03],
            bounds=(0, [np.inf, 1.0]),
            maxfev=3000
        )
        return float(popt[0]), float(popt[1])
    except Exception:
        return None, None

def build_forecast(hist_dates, hist_rates, events, months=36):
    """Build base decline + apply future events"""
    qi, di = fit_base_decline(hist_rates)
    if qi is None:
        return None

    last_date = pd.to_datetime(hist_dates.iloc[-1])
    future_dates = pd.date_range(
        last_date + pd.DateOffset(months=1), periods=months, freq='MS'
    )
    t_future = np.arange(len(hist_rates), len(hist_rates) + months)
    base = exp_decline(t_future, qi, di)

    df_f = pd.DataFrame({
        'Date': future_dates,
        'Base': base,
        'Total': base.copy()
    })

    for ev in events:
        start = pd.to_datetime(ev['start'])

        if ev['type'] == 'New Well':
            qi_w = float(ev['qi'])
            di_w = float(ev['di'])
            # Months on production
            months_on = ((df_f['Date'] - start).dt.days / 30.44).clip(lower=0)
            well_contrib = np.where(
                df_f['Date'] >= start,
                exp_decline(months_on, qi_w, di_w),
                0.0
            )
            df_f['Total'] += well_contrib

        elif ev['type'] == 'Water Injection':
            inj_rate = float(ev.get('inj_rate', 10000))
            response = float(ev.get('response', 0.05))
            lag = int(ev.get('lag', 3))

            months_since = (df_f['Date'] - start).dt.days / 30.44
            # Ramp over 6 months after lag
            ramp = np.clip((months_since - lag) / 6.0, 0, 1)
            uplift = np.where(months_since >= lag, inj_rate * response * ramp, 0.0)
            df_f['Total'] += uplift

    return df_f, qi, di

# ==================== UPLOAD DATA ====================
if page == "Upload Data":
    st.title("Upload Production Data")
    st.markdown("**Required columns:** `Field`, `Date`, `Oil_bbl`")

    uploaded = st.file_uploader("Upload Excel or CSV", type=["xlsx", "xls", "csv"])
    if uploaded is not None:
        try:
            if uploaded.name.endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            df.columns = df.columns.str.strip()
            if 'Date' not in df.columns:
                st.error("Column 'Date' not found")
            else:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date', 'Field'])
                st.session_state.df = df
                st.success(f"Loaded {len(df)} rows | {df['Field'].nunique()} fields")
                st.dataframe(df.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")

# ==================== FUTURE EVENTS ====================
elif page == "Future Events":
    st.title("Future Development Plan")

    tab1, tab2 = st.tabs(["New Well", "Water Injection"])

    with tab1:
        st.subheader("Add New Well")
        with st.form("form_well", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            w_start = c1.date_input("Production Start Date")
            w_qi = c2.number_input("Initial Rate qi (bbl/month)", min_value=0, value=15000, step=500)
            w_di = c3.number_input("Decline Rate Di", min_value=0.0, value=0.025, step=0.005, format="%.3f")
            w_name = st.text_input("Well Name", value=f"NW-{len([e for e in st.session_state.events if e['type']=='New Well'])+1}")
            if st.form_submit_button("Add Well"):
                st.session_state.events.append({
                    'type': 'New Well',
                    'name': w_name,
                    'start': str(w_start),
                    'qi': w_qi,
                    'di': w_di
                })
                st.success(f"Added {w_name}")

    with tab2:
        st.subheader("Add Water Injection")
        with st.form("form_inj", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            i_start = c1.date_input("Injection Start Date")
            i_rate = c2.number_input("Injection Rate (bbl/month)", min_value=0, value=25000, step=1000)
            i_resp = c3.number_input("Response Factor (oil/water)", min_value=0.0, value=0.06, step=0.01, format="%.2f")
            i_lag = st.slider("Response Lag (months)", 0, 18, 3)
            if st.form_submit_button("Add Injection"):
                st.session_state.events.append({
                    'type': 'Water Injection',
                    'start': str(i_start),
                    'inj_rate': i_rate,
                    'response': i_resp,
                    'lag': i_lag
                })
                st.success("Injection plan added")

    st.markdown("---")
    if st.session_state.events:
        st.subheader("Planned Events")
        st.dataframe(pd.DataFrame(st.session_state.events), use_container_width=True)
        if st.button("Clear All Events"):
            st.session_state.events = []
            st.rerun()
    else:
        st.info("No events added yet.")

# ==================== FORECASTING ====================
elif page == "Forecasting":
    st.title("Production Forecast")

    if st.session_state.df is None:
        st.warning("Please upload data first.")
    else:
        df = st.session_state.df
        field = st.selectbox("Select Field", sorted(df['Field'].dropna().unique()))
        fdata = df[df['Field'] == field].sort_values('Date').reset_index(drop=True)

        st.write(f"**History:** {fdata['Date'].min().strftime('%b %Y')} → {fdata['Date'].max().strftime('%b %Y')} ({len(fdata)} months)")

        horizon = st.slider("Forecast Horizon (months)", 12, 60, 36)

        if st.button("Run Forecast", type="primary"):
            res = build_forecast(
                fdata['Date'],
                fdata['Oil_bbl'].fillna(0).values,
                st.session_state.events,
                horizon
            )
            if res is None:
                st.error("Could not fit decline. Need more non-zero production data.")
            else:
                fcast, qi, di = res
                st.session_state.forecast = {
                    'hist': fdata,
                    'fcast': fcast,
                    'field': field,
                    'qi': qi,
                    'di': di
                }

        if 'forecast' in st.session_state and st.session_state.forecast.get('field') == field:
            fc = st.session_state.forecast
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=fc['hist']['Date'], y=fc['hist']['Oil_bbl'],
                mode='markers', name='Historical',
                marker=dict(size=5, color='#1f77b4')
            ))
            fig.add_trace(go.Scatter(
                x=fc['fcast']['Date'], y=fc['fcast']['Base'],
                mode='lines', name='Base Decline',
                line=dict(dash='dot', color='gray', width=1.5)
            ))
            fig.add_trace(go.Scatter(
                x=fc['fcast']['Date'], y=fc['fcast']['Total'],
                mode='lines', name='With Development',
                line=dict(color='crimson', width=2.5)
            ))
            fig.update_layout(
                height=540,
                title=f"{field} — Forecast",
                yaxis_title="Oil Rate (bbl/month)",
                hovermode='x unified',
                legend=dict(orientation="h", y=1.05)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Base fit → qi: {fc['qi']:,.0f} bbl/month | Di: {fc['di']:.4f}")

# ==================== DASHBOARD ====================
elif page == "Dashboard":
    st.title("Dashboard")
    if st.session_state.df is not None:
        c1, c2 = st.columns(2)
        c1.metric("Fields", st.session_state.df['Field'].nunique())
        c2.metric("Planned Events", len(st.session_state.events))
    else:
        st.info("Upload production data to get started.")
