"""Streamlit view of computed artifacts, with cohort-safe descriptive filters."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.calculate_statistics import conclusion

st.set_page_config(page_title="Driver Reactivation", page_icon="🚘", layout="wide")
st.title("Driver Reactivation")
st.caption("A/B Testing & Product Analytics · Synthetic data only · Seven-day intention-to-treat analysis")
folder = ROOT / "data/dashboard"
if not (folder / "statistical_results.csv").exists():
    st.info("Run python -m src.run_pipeline first to build the analytics artifacts.")
    st.stop()
drivers = pd.read_csv(folder / "driver_metrics.csv", parse_dates=["assigned_at"])
results = pd.read_csv(folder / "statistical_results.csv")
daily = pd.read_csv(folder / "daily_metrics.csv")
calendar = pd.read_csv(folder / "calendar_activity.csv", parse_dates=["activity_date"])
scenarios = pd.read_csv(folder / "economic_scenarios.csv")
st.sidebar.header("Descriptive cohort filters")
country = st.sidebar.selectbox("Country", ["ALL"] + sorted(drivers.country.unique().tolist()))
variant = st.sidebar.multiselect("Experiment group", ["control", "treatment"], default=["control", "treatment"])
dates = st.sidebar.date_input("Assignment date (UTC)", value=(drivers.assigned_at.min().date(), drivers.assigned_at.max().date()),
                              min_value=drivers.assigned_at.min().date(), max_value=drivers.assigned_at.max().date())
st.sidebar.caption("Date selects assignment cohorts and preserves their full seven-day follow-up. Inferential cards remain precomputed for the complete selected country; group/date filters affect descriptive charts only.")
r = results.loc[results.scope == country].iloc[0]
st.subheader("Precomputed experiment result" + (" · exploratory country" if country != "ALL" else " · complete cohort"))
cols = st.columns(4)
cols[0].metric("Total assigned", f"{int(r.n_control+r.n_treatment):,}")
cols[1].metric("Reactivation · control", f"{r.rate_control:.2%}")
cols[2].metric("Reactivation · treatment", f"{r.rate_treatment:.2%}")
cols[3].metric("Absolute uplift", f"{r.absolute_uplift*100:.2f} pp")
cols = st.columns(4)
cols[0].metric("Relative uplift", f"{r.relative_uplift:.1%}" if pd.notna(r.relative_uplift) else "Undefined")
cols[1].metric("p-value · two-sided", f"{r.p_value:.4g}")
cols[2].metric("Bonus cost · RUB eq.", f"{r.bonus_cost:,.0f}")
cols[3].metric("Net incremental · RUB eq.", f"{r.net_incremental_contribution:,.0f}")
st.info(conclusion(r.to_dict()))
st.caption(f"Newcombe 95% CI: [{r.ci_low*100:.2f}, {r.ci_high*100:.2f}] pp. Net contribution 95% CI: [{r.net_ci_low:,.0f}, {r.net_ci_high:,.0f}]. Country and secondary tests are exploratory and unadjusted.")
mask = drivers.variant.isin(variant)
if country != "ALL":
    mask &= drivers.country.eq(country)
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    mask &= drivers.assigned_at.dt.date.between(dates[0], dates[1])
selected = drivers.loc[mask]
st.subheader("Descriptive cohort view")
st.caption(f"{len(selected):,} assigned drivers selected. A zero-ride driver remains in the denominator.")
if selected.empty:
    st.warning("No drivers match these filters.")
else:
    grouped = selected.groupby("variant", as_index=False).agg(reactivation_rate=("reactivated", "mean"), assigned=("driver_id", "size"))
    left, right = st.columns(2)
    left.plotly_chart(px.bar(grouped, x="variant", y="reactivation_rate", color="variant", title="7-day reactivation rate", range_y=[0, max(.2, grouped.reactivation_rate.max()*1.2)]), width="stretch")
    # Country/group filters apply here; daily marts do not have assignment date grain.
    day = daily[daily.variant.isin(variant)]
    if country != "ALL":
        day = day[day.country.eq(country)]
    right.plotly_chart(px.line(day.groupby(["day_number", "variant"], as_index=False).completed_rides.sum(), x="day_number", y="completed_rides", color="variant", markers=True, title="Daily rides · full assignment dates"), width="stretch")
    segments = selected.groupby(["country", "variant"], as_index=False).agg(assigned=("driver_id", "size"), reactivated=("reactivated", "sum"), reactivation_rate=("reactivated", "mean"), avg_rides=("completed_rides", "mean"), revenue=("revenue", "sum"), bonus_cost=("bonus_cost", "sum"), contribution_after_bonus=("contribution_after_bonus", "sum"))
    left, right = st.columns(2)
    left.plotly_chart(px.bar(segments, x="country", y="reactivation_rate", color="variant", barmode="group", title="Country reactivation · exploratory"), width="stretch")
    ci = go.Figure(go.Scatter(x=[r.absolute_uplift*100], y=["Uplift"], mode="markers", error_x=dict(type="data", symmetric=False, array=[(r.ci_high-r.absolute_uplift)*100], arrayminus=[(r.absolute_uplift-r.ci_low)*100])))
    ci.add_vline(x=0, line_dash="dash")
    ci.update_layout(title="Precomputed uplift · 95% CI", xaxis_title="Percentage points")
    right.plotly_chart(ci, width="stretch")
    st.dataframe(segments, hide_index=True, width="stretch")
    st.download_button("Download selected driver metrics", selected.to_csv(index=False), "selected_driver_metrics.csv", "text/csv")
st.subheader("Economic sensitivity · complete global cohort")
st.caption("Revenue means platform commission. Contribution = revenue × margin − bonus. Behavior is held fixed; alternative bonuses require a new experiment.")
st.plotly_chart(px.bar(scenarios.assign(bonus_amount=scenarios.bonus_amount.astype(str)), x="bonus_amount", y="net_incremental_contribution", color="margin_rate", barmode="group", title="Net incremental contribution · RUB-equivalent"), width="stretch")
with st.expander("Calendar activity · complete assignment dates"):
    st.caption("Descriptive event-date series only; never filter primary inference by ride date.")
    st.plotly_chart(px.line(calendar.groupby(["activity_date", "variant"], as_index=False).completed_rides.sum(), x="activity_date", y="completed_rides", color="variant"), width="stretch")
