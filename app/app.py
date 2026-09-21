import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Ensure voltpulse package can be resolved
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from voltpulse.utils.config import get_config
from voltpulse.optimization.bess_model import BESSOptimizer

st.set_page_config(
    page_title="VoltPulse - 电力现货与储能分析平台",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    config = get_config()
    prices_path = config.get_path("spot_prices_parquet")
    metrics_path = config.get_path("results_dir") / "daily_metrics.parquet"
    backtest_path = config.get_path("results_dir") / "backtest_results.parquet"

    df_prices = pd.read_parquet(prices_path) if prices_path.exists() else pd.DataFrame()
    df_metrics = pd.read_parquet(metrics_path) if metrics_path.exists() else pd.DataFrame()
    df_backtest = pd.read_parquet(backtest_path) if backtest_path.exists() else pd.DataFrame()

    return df_prices, df_metrics, df_backtest


df_prices, df_metrics, df_backtest = load_data()

st.title("⚡ VoltPulse — 中国电力现货市场与储能优化平台")
st.caption("开源自动化研究平台 | 追踪真实电价特征与 100MW/200MWh 储能套利价值")

if df_prices.empty or df_metrics.empty:
    st.warning("暂无处理后的数据，请先运行数据流水线: `python scripts/pipeline.py`")
    st.stop()

# Sidebar controls
st.sidebar.header("🕹️ 控制面板")
available_markets = df_prices["market"].unique().tolist()
selected_market = st.sidebar.selectbox("选择现货市场", available_markets, index=0)

market_prices = df_prices[df_prices["market"] == selected_market]
available_dates = sorted(market_prices["date"].unique().tolist(), reverse=True)
selected_date = st.sidebar.selectbox("选择交易日", available_dates, index=0)

# Overview KPIs
st.subheader(f"📊 市场概览 ({selected_market.upper()} - {selected_date})")

day_metrics = df_metrics[(df_metrics["market"] == selected_market) & (df_metrics["date"] == selected_date)]
if not day_metrics.empty:
    m = day_metrics.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("今日均价", f"{m['mean_price']} RMB/MWh", f"最低 {m['min_price']} ~ 最高 {m['max_price']}")
    col2.metric("峰谷综合价差", f"{m['peak_valley_spread']} RMB/MWh")
    col3.metric("负电价时段", f"{m['negative_price_count']} 点", f"{m['negative_price_count']*0.25:.2f} 小时")

    day_bt = df_backtest[(df_backtest["market"] == selected_market) & (df_backtest["date"] == selected_date) & (df_backtest["strategy"] == "perfect_foresight")]
    if not day_bt.empty:
        pnl = day_bt.iloc[0]["net_profit"]
        efc = day_bt.iloc[0]["efc"]
        col4.metric("储能日净收益 (LP最优)", f"¥ {pnl:,.2f}", f"EFC 循环: {efc:.2f} 次")

# 1. 24h Spot Price Curve
st.markdown("### 📈 96 点分时现货出清价格")
day_prices = market_prices[market_prices["date"] == selected_date].sort_values(by="timestamp")

fig_price = px.line(
    day_prices,
    x="timestamp",
    y="price_rmb_mwh",
    title=f"{selected_date} 出清电价曲线 (RMB/MWh)",
    labels={"timestamp": "时间", "price_rmb_mwh": "出清价格 (RMB/MWh)"}
)
fig_price.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="零电价基准")
st.plotly_chart(fig_price, use_container_width=True)

# 2. BESS Dispatch & SOC
st.markdown("### 🔋 100MW / 200MWh 储能充放电与 SOC 曲线")
prices_arr = day_prices["price_rmb_mwh"].values
optimizer = BESSOptimizer()
bess_res = optimizer.optimize_dispatch(prices_arr, interval_minutes=15)

df_dispatch = pd.DataFrame({
    "timestamp": day_prices["timestamp"],
    "充电功率(MW)": bess_res["p_charge_mw"],
    "放电功率(MW)": bess_res["p_discharge_mw"],
    "SOC (%)": [v * 100 for v in bess_res["soc"]]
})

fig_dispatch = go.Figure()
fig_dispatch.add_trace(go.Bar(x=df_dispatch["timestamp"], y=df_dispatch["充电功率(MW)"], name="充电功率 (MW)", marker_color="#10b981"))
fig_dispatch.add_trace(go.Bar(x=df_dispatch["timestamp"], y=df_dispatch["放电功率(MW)"], name="放电功率 (MW)", marker_color="#f59e0b"))
fig_dispatch.add_trace(go.Scatter(x=df_dispatch["timestamp"], y=df_dispatch["SOC (%)"], name="SOC (%)", yaxis="y2", line=dict(color="#a855f7", width=2)))

fig_dispatch.update_layout(
    title="储能充放电调度与荷电状态联动",
    yaxis=dict(title="充放功率 (MW)", range=[0, 100]),
    yaxis2=dict(title="SOC (%)", overlaying="y", side="right", range=[0, 100]),
    barmode="stack"
)
st.plotly_chart(fig_dispatch, use_container_width=True)

# 3. Backtest History
st.markdown("### 🏆 历史回测策略收益对比")
if not df_backtest.empty:
    mkt_bt = df_backtest[df_backtest["market"] == selected_market]
    fig_bt = px.line(
        mkt_bt,
        x="date",
        y="cumulative_pnl",
        color="strategy",
        title="累计净收益曲线对比 (Cumulative PnL, RMB)",
        labels={"date": "日期", "cumulative_pnl": "累计净收益 (RMB)", "strategy": "策略"}
    )
    st.plotly_chart(fig_bt, use_container_width=True)
