# led_wall_estimator_profit.py
# Streamlit app: LED Video Wall Estimator (Markup Masked + Admin Tier Control)

import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# -------------------------------------------------
# Page setup
# -------------------------------------------------
st.set_page_config(page_title="LED Video Wall Estimator", layout="wide")

# -------------------------------------------------
# Branding + CSS
# -------------------------------------------------
st.markdown(
    """
    <style>
        body, .main {
            background-color: #F7F8FA;
            color: #111111;
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        }

        [data-testid="stSidebar"] {
            background-color: #E8EBEE;
        }

        div[data-testid="stMetricValue"] {
            color: #004080 !important;
        }

        .stSlider > div > div > div[role="slider"] {
            background-color: #004080 !important;
        }

        .app-header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #00408020;
            margin-bottom: 10px;
        }

        img {
            max-width: 100%;
            height: auto;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Header block
# -------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <img src="https://raw.githubusercontent.com/BartlettGoodell/TrueNorth-LED-Estimator/main/TrueNorth_Logo.svg"
             alt="TN Logo" width="60">
        <div>
            <h2 style="margin:0; color:#004080; line-height:0.9; font-weight:700;">
                TrueNorth<br>
                <span style="font-size:0.8em; font-weight:600;">LED WALL ESTIMATOR</span>
            </h2>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def linear_price_per_m2(qty: int, low_qty=1, low_price=3400.0, high_qty=25, high_price=2720.0):
    if qty <= low_qty:
        return float(low_price)
    if qty >= high_qty:
        return float(high_price)
    frac = (qty - low_qty) / (high_qty - low_qty)
    return float(low_price + frac * (high_price - low_price))


def compute_costs(cols, rows, qty, price_mode, custom_price_m2, controller_cost, markup_pct):
    cabinet_w = 0.5
    cabinet_h = 0.5
    area_per_cab = cabinet_w * cabinet_h
    cabinets = int(cols * rows)
    area_m2 = cabinets * area_per_cab

    if price_mode == "Tiered (linear 1→25)":
        base_price_m2 = linear_price_per_m2(qty)
    else:
        base_price_m2 = float(custom_price_m2)

    base_hardware = area_m2 * base_price_m2
    controller_total = controller_cost

    # Markup stays SILENT
    subtotal = base_hardware + controller_total
    markup_amount = subtotal * (markup_pct / 100.0)
    grand_total = subtotal + markup_amount

    per_m2 = grand_total / area_m2 if area_m2 > 0 else 0.0
    per_cab = grand_total / cabinets if cabinets > 0 else 0.0
    order_total = grand_total * qty

    return {
        "area_m2": area_m2,
        "cabinets": cabinets,
        "width_m": cols * cabinet_w,
        "height_m": rows * cabinet_h,
        "base_price_m2": base_price_m2,
        "base_hardware": base_hardware,
        "controller_total": controller_total,
        "grand_total": grand_total,
        "per_m2": per_m2,
        "per_cabinet": per_cab,
        "order_total": order_total
    }


def grid_figure(cols, rows):
    cabinet_w = 0.5
    cabinet_h = 0.5
    width_m = cols * cabinet_w
    height_m = rows * cabinet_h

    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=width_m, y1=height_m, line=dict(width=2))

    for c in range(1, cols):
        fig.add_shape(
            type="line",
            x0=c * cabinet_w, y0=0,
            x1=c * cabinet_w, y1=height_m,
            line=dict(width=1)
        )

    for r in range(1, rows):
        fig.add_shape(
            type="line",
            x0=0, y0=r * cabinet_h,
            x1=width_m, y1=r * cabinet_h,
            line=dict(width=1)
        )

    fig.update_xaxes(range=[-0.05, width_m + 0.05], title="Width (m)", showgrid=False, zeroline=False)
    fig.update_yaxes(range=[-0.05, height_m + 0.05], title="Height (m)", scaleanchor="x", scaleratio=1,
                     showgrid=False, zeroline=False)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420, dragmode=False)
    return fig


def money(x):
    return f"${x:,.0f}"

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
st.sidebar.title("Estimator Controls")

# Quantity
st.sidebar.subheader("Quantity (Screens)")
qty = st.sidebar.number_input("Order quantity", min_value=1, step=1, value=1)

# Pricing mode
st.sidebar.subheader("Pricing Model")
price_mode = st.sidebar.selectbox("Per-m² pricing mode", ["Tiered (linear 1→25)", "Custom fixed per-m²"])
custom_price_m2 = st.sidebar.number_input("Custom per-m² price", min_value=0.0, step=50.0, value=3400.0, format="%.2f")

# Controller
st.sidebar.subheader("Controller")
controller_cost = st.sidebar.number_input("Controller cost (per screen)", min_value=0.0, step=25.0,
                                          value=325.0, format="%.2f")

# -------------------------------------------------
# ADMIN MODE (TNX)
# -------------------------------------------------
st.sidebar.subheader("Admin Access")
admin_key = st.sidebar.text_input("Enter admin key", type="password")

if admin_key == "TNX":
    pricing_tier = st.sidebar.selectbox("Project Tier (Admin Only)", ["Level A", "Level B", "Level C"], index=1)
    st.sidebar.success("Admin mode enabled")
else:
    pricing_tier = "Level B"  # Hidden default for clients

# Internal-only tier mapping
_tier_to_markup = {"Level A": 10, "Level B": 20, "Level C": 30}
markup_pct = _tier_to_markup.get(pricing_tier, 20)

# -------------------------------------------------
# Main layout
# -------------------------------------------------
st.caption("Sized in 0.5 m × 0.5 m cabinet increments.")

left, right = st.columns([1, 1])

with left:
    st.subheader("Size by Cabinets")
    cols = st.slider("Columns (0.5 m increments)", 1, 40, 10)
    rows = st.slider("Rows (0.5 m increments)", 1, 20, 3)
    fig = grid_figure(cols, rows)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Specs")

    cabinet_w, cabinet_h = 0.5, 0.5
    width_m = cols * cabinet_w
    height_m = rows * cabinet_h
    area_m2 = cols * rows * cabinet_w * cabinet_h
    cabinets = cols * rows

    st.metric("Width (m)", f"{width_m:.2f}")
    st.metric("Height (m)", f"{height_m:.2f}")
    st.metric("Area (m²)", f"{area_m2:.2f}")
    st.metric("Cabinets", f"{cabinets}")

    result = compute_costs(cols, rows, qty, price_mode, custom_price_m2, controller_cost, markup_pct)

    st.subheader("Pricing Summary")
    st.metric("Total (per screen)", money(result["grand_total"]))
    st.metric("Per m² (all-in)", money(result["per_m2"]))
    st.metric("Per cabinet (all-in)", money(result["per_cabinet"]))

    if qty > 1:
        st.metric("Order total", money(result["order_total"]))

    # SAFE DATA TABLE (no base pricing, no markup, no back-solvable numbers)
    data = {
        "Metric": [
            "Width (m)", "Height (m)", "Area (m²)", "Cabinets",
            "Project Tier", "Total per screen $", "Per m² all-in $",
            "Per cabinet all-in $", "Order qty", "Order total $"
        ],
        "Value": [
            f"{result['width_m']:.2f}", f"{result['height_m']:.2f}",
            f"{result['area_m2']:.2f}", f"{result['cabinets']}",
            pricing_tier, money(result["grand_total"]), money(result["per_m2"]),
            money(result["per_cabinet"]), f"{qty}", money(result["order_total"])
        ]
    }

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, height=400)


st.markdown("---")
st.caption("For rapid estimating purposes only.")
