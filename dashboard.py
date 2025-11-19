import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import re
from bs4 import BeautifulSoup
from datetime import datetime, date

# --- PARSING LOGIC MOVED FROM parse_trades.py ---

def clean_and_format_number(text):
    if not text:
        return None
    cleaned_text = re.sub(r'[$\s,¥+%]|CHF|≈|lots', '', text, flags=re.IGNORECASE)
    return pd.to_numeric(cleaned_text, errors='coerce')

def format_close_date(date_str):
    if not date_str:
        return None
    if 'ago' in date_str.lower():
        return pd.to_datetime(date.today())
    try:
        return pd.to_datetime(datetime.strptime(date_str, '%d %b %Y, %I:%M %p'))
    except ValueError:
        return pd.to_datetime(date_str, errors='coerce')

def parse_html_to_dataframe(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    records = soup.find_all('div', class_=re.compile(r'border-grey-300.*flex.*items-center'))

    if not records:
        return pd.DataFrame()

    parsed_data = []
    for record in records:
        try:
            trade_type_span = record.find('div', class_='portfolio-styles_typeColumn__Psx6k').find('span', class_='laptop:flex hidden')
            asset_info_div = record.find('div', title='Asset info')
            pl_div = record.find('div', title='Profit/Loss')
            close_date_div = record.find('div', title='Close date')

            if not (trade_type_span and asset_info_div and pl_div and close_date_div):
                continue

            asset_name_p = asset_info_div.find('p', class_='font-semibold')
            asset_ticker_span = asset_info_div.find('span', class_='text-secondary')
            asset_class_container = asset_info_div.find('div', class_='flex items-center')
            asset_class_div = asset_class_container.find('div', class_=lambda x: x and 'mx-1' in x) if asset_class_container else None
            pl_amount_p = pl_div.find('p', class_='laptop:text-md')
            pl_percent_div = pl_div.find('div', class_='laptop:font-semibold')
            close_date_p = close_date_div.find('p', class_='text-secondary')

            row_data = {
                "Type": trade_type_span.get_text(strip=True) if trade_type_span else None,
                "Asset Name": asset_name_p.get_text(strip=True) if asset_name_p else None,
                "Asset Ticker": asset_ticker_span.get_text(strip=True) if asset_ticker_span else None,
                "Asset Class": asset_class_div.get_text(strip=True) if asset_class_div else 'Other',
                "Profit/Loss Amount": clean_and_format_number(pl_amount_p.get_text(strip=True)) if pl_amount_p else None,
                "Percent": clean_and_format_number(pl_percent_div.get_text(strip=True)) if pl_percent_div else None,
                "Close Date": format_close_date(close_date_p.get_text(strip=True)) if close_date_p else None
            }
            parsed_data.append(row_data)
        except Exception:
            continue # Skip records that fail to parse

    df = pd.DataFrame(parsed_data)
    # Ensure data types are correct
    df['Close Date'] = pd.to_datetime(df['Close Date'], errors='coerce')
    df = df.dropna(subset=['Close Date', 'Profit/Loss Amount']) # Drop rows where essential data is missing
    return df

# --- UI AND DASHBOARD LOGIC ---

# --- Dashboard Title ---
st.title("📊 Trading Dashboard")

# --- Data Input Sidebar ---
st.sidebar.header("Data Input")
html_input = st.sidebar.text_area("Paste HTML content here", height=250)

if st.sidebar.button("Process HTML"):
    if html_input:
        with st.spinner("Processing data..."):
            df = parse_html_to_dataframe(html_input)
            if not df.empty:
                st.session_state['df'] = df # Store the dataframe in session state
                st.sidebar.success(f"Successfully parsed {len(df)} trades!")
            else:
                st.sidebar.error("Could not find any valid trade data in the HTML.")
    else:
        st.sidebar.warning("Please paste HTML content before processing.")

# Only show the dashboard if data has been processed and stored
if 'df' not in st.session_state:
    st.info("Please paste your trading data HTML into the sidebar and click 'Process HTML' to view the dashboard.")
    st.stop()

df = st.session_state['df']

# --- Sidebar Filters ---
st.sidebar.header("Filters")
asset_class = st.sidebar.multiselect(
    "Select Asset Class:",
    options=df["Asset Class"].unique(),
    default=df["Asset Class"].unique()
)

df_selection = df.query(
    "`Asset Class` == @asset_class"
)

# Check if the dataframe is empty
if df_selection.empty:
    st.warning("No data available for the selected filters. Please select at least one asset class.")
    st.stop() # This will halt the app from running further

try:
    # --- Summary Metrics ---
    total_profit = df_selection["Profit/Loss Amount"].sum()
    avg_return = df_selection["Percent"].mean()
    num_trades = len(df_selection)
    oldest_date = df_selection["Close Date"].min().strftime("%Y-%m-%d")
    newest_date = df_selection["Close Date"].max().strftime("%Y-%m-%d")

    # Display metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Profit/Loss", f"${total_profit:,.2f}")
    col2.metric("Average Return", f"{avg_return:.2f}%")
    col3.metric("Number of Trades", num_trades)
    st.metric("Date range", f"{oldest_date} to {newest_date}")

    # --- Profit Trend Over Time ---
    # Prepare data for combo chart
    daily_profit = df_selection.groupby(df_selection["Close Date"].dt.date)["Profit/Loss Amount"].sum()
    cumulative_profit = daily_profit.cumsum()

    # Create a figure with graph_objects
    fig = go.Figure()

    # Add the daily profit as a bar chart
    fig.add_trace(go.Bar(
        x=daily_profit.index,
        y=daily_profit.values,
        name='Daily Profit/Loss',
        yaxis='y2',  # Assign this trace to the secondary y-axis
        marker_color=['green' if p >= 0 else 'red' for p in daily_profit.values] # Color bars based on profit/loss
    ))

    # Add the cumulative profit as a line chart
    fig.add_trace(go.Scatter(x=cumulative_profit.index, y=cumulative_profit.values, name='Cumulative Profit', mode='lines', line=dict(color='blue')))

    # Update layout to include a secondary y-axis
    fig.update_layout(
        title_text="Cumulative & Daily Profit Trend",
        xaxis_title="Date",
        yaxis=dict(title="Cumulative Profit ($)", color="blue"),
        yaxis2=dict(
            title="Daily Profit/Loss ($)",
            overlaying="y",
            side="right"
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig)

    # --- Asset Class Breakdown ---
    asset_breakdown = df_selection.groupby("Asset Class")["Profit/Loss Amount"].sum().reset_index()
    fig2 = px.pie(asset_breakdown, names="Asset Class", values="Profit/Loss Amount", title="Profit by Asset Class")
    st.plotly_chart(fig2)

    # --- Top Trades ---
    top_trades = df_selection.sort_values("Profit/Loss Amount", ascending=False).head(10)
    st.subheader("🔥 Top 10 Trades")
    st.dataframe(top_trades[["Asset Name", "Asset Ticker", "Profit/Loss Amount", "Close Date", "Asset Class"]])

except KeyError as e:
    st.error(f"An error occurred: The column {e} was not found in your Excel file. Please check the column names printed above and update your script accordingly.")