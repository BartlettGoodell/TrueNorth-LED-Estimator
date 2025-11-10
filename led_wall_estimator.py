
# led_wall_estimator.py
# Streamlit app: LED Video Wall Estimator with cabinet-snapped sizing and full cost math
#
# Usage:
#   1) pip install streamlit pandas numpy plotly
#   2) streamlit run led_wall_estimator.py
#
# Notes:
# - "Drag" behavior is simulated with a simple interactive grid preview and two sliders for columns/rows.
# - The sizing snaps to 0.5 m x 0.5 m cabinets (each 0.25 m²), which matches your .25 m² increment request.
# - You can override per-m² pricing, controller cost, shipping/duty markup, and add optional line items.
# - Includes a quantity scaler (single unit vs multi-unit order) with linear interpolation between tier endpoints.

import math
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="LED Video Wall Estimator", layout="wide")

# -----------------------
# Helpers
# -----------------------

def linear_price_per_m2(qty: int, low_qty=1, low_price=3400.0, high_qty=25, high_price=2720.0):
    """
    Returns a per-m² price for a given quantity using linear interpolation
    between (low_qty, low_price) and (high_qty, high_price).
    Clamps below/above the endpoints.
    """
    if qty <= low_qty:
        return float(low_price)
    if qty >= high_qty:
        return float(high_price)
    # Linear interpolation
    frac = (qty - low_qty) / (high_qty - low_qty)
    return float(low_price + frac * (high_price - low_price))


def compute_costs(cols, rows, qty, price_mode, custom_price_m2, controller_cost, shipping_pct, extra_items):
    cabinet_w = 0.5  # meters
    cabinet_h = 0.5  # meters
    area_per_cab = cabinet_w * cabinet_h  # 0.25 m²
    cabinets = int(cols * rows)
    area_m2 = cabinets * area_per_cab

    # Resolve per-m² base price
    if price_mode == "Tiered (linear 1→25)":
        base_price_m2 = linear_price_per_m2(qty)
    else:
        base_price_m2 = float(custom_price_m2)

    # Base hardware price
    base_hardware = area_m2 * base_price_m2

    # Controller (one per screen) — can be changed in sidebar
    controller_total = controller_cost

    # Extras (line items, per-screen)
    extras_total = sum([float(x.get("cost", 0)) for x in extra_items])

    # Subtotal before shipping/duties
    subtotal = base_hardware + controller_total + extras_total

    # Shipping/duties markup
    shipping_amount = subtotal * (shipping_pct / 100.0)

    # Grand total
    grand_total = subtotal + shipping_amount

    # Per-unit (screen) breakdown
    per_m2 = grand_total / area_m2 if area_m2 > 0 else 0.0
    per_cab = grand_total / cabinets if cabinets > 0 else 0.0

    # Per-order totals for QTY>1 (just multiply screens)
    order_total = grand_total * qty

    return {
        "area_m2": area_m2,
        "cabinets": cabinets,
        "width_m": cols * cabinet_w,
        "height_m": rows * cabinet_h,
        "base_price_m2": base_price_m2,
        "base_hardware": base_hardware,
        "controller_total": controller_total,
        "extras_total": extras_total,
        "shipping_pct": shipping_pct,
        "shipping_amount": shipping_amount,
        "grand_total": grand_total,
        "per_m2": per_m2,
        "per_cabinet": per_cab,
        "order_total": order_total,
    }


def grid_figure(cols, rows):
    """Draw a simple cabinet grid using Plotly, with 0.5m x 0.5m tiles."""
    cabinet_w = 0.5
    cabinet_h = 0.5
    width_m = cols * cabinet_w
    height_m = rows * cabinet_h

    fig = go.Figure()
    # Draw outer rectangle
    fig.add_shape(type="rect",
                  x0=0, y0=0, x1=width_m, y1=height_m,
                  line=dict(width=2))

    # Grid lines (vertical)
    for c in range(1, cols):
        x = c * cabinet_w
        fig.add_shape(type="line", x0=x, y0=0, x1=x, y1=height_m, line=dict(width=1))

    # Grid lines (horizontal)
    for r in range(1, rows):
        y = r * cabinet_h
        fig.add_shape(type="line", x0=0, y0=y, x1=width_m, y1=y, line=dict(width=1))

    # Labels
    fig.update_xaxes(range=[-0.05, max(0.5, width_m + 0.05)],
                     title_text="Width (m)",
                     showgrid=False,
                     zeroline=False)
    fig.update_yaxes(range=[-0.05, max(0.5, height_m + 0.05)],
                     title_text="Height (m)",
                     scaleanchor="x",
                     scaleratio=1,
                     showgrid=False,
                     zeroline=False)

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=420,
        dragmode=False
    )
    return fig


def money(x):
    return f"${x:,.0f}"


# -----------------------
# Sidebar Controls
# -----------------------

st.sidebar.title("Estimator Controls")

st.sidebar.subheader("Quantity (Screens)")
qty = st.sidebar.number_input("Order quantity", min_value=1, step=1, value=1)

st.sidebar.subheader("Pricing Model")
price_mode = st.sidebar.selectbox("Per‑m² pricing mode",
                                  ["Tiered (linear 1→25)", "Custom fixed per‑m²"])
custom_price_m2 = st.sidebar.number_input("Custom per‑m² price (if using custom)",
                                          min_value=0.0, step=50.0, value=3400.0, format="%.2f")

st.sidebar.subheader("Controller & Shipping")
controller_cost = st.sidebar.number_input("Controller cost (per screen)",
                                          min_value=0.0, step=25.0, value=325.0, format="%.2f")
shipping_pct = st.sidebar.slider("Shipping & duty markup (%)", min_value=0, max_value=40, value=15, step=1)

st.sidebar.subheader("Optional Line Items (per screen)")
extra_items_data = st.sidebar.text_area(
    "Enter extras as 'Label:Cost' one per line",
    value="Spare modules bundle:300\nSpare PSUs & receiving cards:250\nVacuum tool & rails:200"
)
extras = []
if extra_items_data.strip():
    for line in extra_items_data.splitlines():
        if ":" in line:
            label, cost = line.split(":", 1)
            try:
                extras.append({"label": label.strip(), "cost": float(cost.strip())})
            except ValueError:
                pass

# -----------------------
# Main: Sizing & Preview
# -----------------------

st.title("LED Video Wall Estimator")
st.caption("Snapped to 0.5 m × 0.5 m cabinets (0.25 m² each). Use sliders to size the array.")

left, right = st.columns([1, 1])

with left:
    st.subheader("Size by Cabinets")
    cols = st.slider("Columns (0.5 m increments)", min_value=1, max_value=40, value=10, step=1)
    rows = st.slider("Rows (0.5 m increments)", min_value=1, max_value=20, value=3, step=1)

    st.write("Each cabinet is 0.5 m × 0.5 m. Drag the sliders to resize. This simulates a drag‑to‑size flow while keeping exact snaps to 0.25 m² increments.")

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

    # Compute costs
    result = compute_costs(cols, rows, qty, price_mode, custom_price_m2, controller_cost, shipping_pct, extras)

    st.subheader("Pricing")
    st.write(f"Per‑m² base price: **{money(result['base_price_m2'])}**")
    st.write(f"Base hardware (panels only): **{money(result['base_hardware'])}**")
    st.write(f"Controller: **{money(result['controller_total'])}**")
    if extras:
        st.write(f"Extras: **{money(result['extras_total'])}**")
    st.write(f"Shipping/Duties ({result['shipping_pct']}%): **{money(result['shipping_amount'])}**")

    st.markdown("---")
    st.metric("Total (per screen)", money(result["grand_total"]))
    st.metric("Per m² (all‑in)", money(result["per_m2"]))
    st.metric("Per cabinet (all‑in)", money(result["per_cabinet"]))
    if qty and qty > 1:
        st.metric("Order total (all screens)", money(result["order_total"]))

    # Detail table
    data = {
        "Metric": ["Width (m)", "Height (m)", "Area (m²)", "Cabinets",
                   "Per‑m² base price", "Panels base $", "Controller $", "Extras $",
                   "Shipping/Duty %", "Shipping/Duty $", "Total per screen $",
                   "Per m² all‑in $", "Per cabinet all‑in $", "Order qty", "Order total $"],
        "Value": [f"{result['width_m']:.2f}", f"{result['height_m']:.2f}", f"{result['area_m2']:.2f}", f"{result['cabinets']}",
                  money(result["base_price_m2"]), money(result["base_hardware"]), money(result["controller_total"]), money(result["extras_total"]),
                  f"{result['shipping_pct']}%", money(result["shipping_amount"]), money(result["grand_total"]),
                  money(result["per_m2"]), money(result["per_cabinet"]), f"{qty}", money(result["order_total"])]
    }
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

st.markdown("---")
st.caption("Tip: Use the 'Tiered (linear 1→25)' mode for quick quotes based on earlier vendor guidance; switch to 'Custom fixed per‑m²' to match a specific quote.')

st.caption("Tip: Use the 'Tiered (linear 1→25)' mode for quick quotes based on earlier vendor guidance; switch to 'Custom fixed per-m²' to match a specific quote.")
