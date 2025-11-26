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
    # This regex is now more specific to only match the trade rows and exclude the header.
    # It looks for the class that contains 'border-b' and 'last-of-type:border-none'.
    records = soup.find_all('div', class_=re.compile(r'border-grey-300.*border-b.*last-of-type:border-none'))

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

def show_dashboard():
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

    # Reset button logic
    if st.sidebar.button("Reset All Filters"):
        # Clear all session state keys related to filters to reset them
        for key in st.session_state.keys():
            if key.endswith('_filter'):
                del st.session_state[key]
        # Also clear the main dataframe to force reprocessing if needed, or just rerun
        if 'df' in st.session_state:
            del st.session_state['df']
        st.rerun()

    asset_class = st.sidebar.multiselect(
        "Select Asset Class:",
        options=df["Asset Class"].unique(),
        default=df["Asset Class"].unique(),
        key="asset_class_filter" # Add a key to manage state
    )

    start_date, end_date = st.sidebar.date_input(
        "Select Date Range:",
        value=(df["Close Date"].min(), df["Close Date"].max()),
        min_value=df["Close Date"].min(),
        max_value=df["Close Date"].max(),
        key="date_range_filter" # Add a key to manage state
    )
    
    df_selection = df.query( # Compare only the date part of 'Close Date'
        "`Asset Class` == @asset_class & `Close Date`.dt.date >= @start_date & `Close Date`.dt.date <= @end_date"
    )

    # Check if the dataframe is empty
    if df_selection.empty:
        st.warning("No data available for the selected filters. Please adjust your selection.")
        st.stop() # This will halt the app from running further
    
    try:
        # --- Summary Metrics ---
        # Basic Metrics
        total_profit = df_selection["Profit/Loss Amount"].sum()
        num_trades = len(df_selection)
        oldest_date = df_selection["Close Date"].min().strftime("%Y-%m-%d")
        newest_date = df_selection["Close Date"].max().strftime("%Y-%m-%d")
        num_days_in_range = (end_date - start_date).days + 1

        # Advanced Metrics
        winning_trades = df_selection[df_selection["Profit/Loss Amount"] > 0]
        losing_trades = df_selection[df_selection["Profit/Loss Amount"] <= 0]
        win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
        avg_win_percent = winning_trades["Percent"].mean()
        avg_loss_percent = losing_trades["Percent"].mean()
        gross_profit = winning_trades["Profit/Loss Amount"].sum()
        gross_loss = abs(losing_trades["Profit/Loss Amount"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        prifit_by_day = total_profit / num_days_in_range if num_days_in_range > 0 else 0



        # Display metrics
        st.metric("Date range", f"{oldest_date} to {newest_date}")
        
        col1, col2, col3 = st.columns(3)
        row2_col1, row2_col2 = st.columns(2)
        
        col1.metric("Total Profit/Loss", f"${total_profit:,.2f}")
        col2.metric("Win Rate", f"{win_rate:.2f}%")
        col3.metric("Profit Factor", f"{profit_factor:.2f}")
        row2_col1.metric("Total Trades", num_trades)
        row2_col2.metric("Days in Range", f"{num_days_in_range} days")

        st.markdown("---")

        # --- Organize content into tabs ---
        tab1, tab2, tab3 = st.tabs(["📈 Performance Trend", "📊 Asset Breakdown", "🔍 Trade Details"])

        with tab1:
            st.subheader("Performance Over Time")
            # --- Profit Trend Over Time ---
            daily_profit = df_selection.groupby(df_selection["Close Date"].dt.date)["Profit/Loss Amount"].sum()
            cumulative_profit = daily_profit.cumsum()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=daily_profit.index, y=daily_profit.values, name='Daily Profit/Loss',
                yaxis='y2', marker_color=['green' if p >= 0 else 'red' for p in daily_profit.values]
            ))
            fig.add_trace(go.Scatter(x=cumulative_profit.index, y=cumulative_profit.values, name='Cumulative Profit', mode='lines', line=dict(color='blue')))
            fig.update_layout(
                title_text="Cumulative & Daily Profit Trend", xaxis_title="Date",
                yaxis=dict(title="Cumulative Profit ($)", color="blue"),
                yaxis2=dict(title="Daily Profit/Loss ($)", overlaying="y", side="right"),
                legend=dict(title="Metric", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig)

        with tab2:
            st.subheader("Performance by Asset Class")
            # --- Asset Class Breakdown ---
            asset_breakdown = df_selection.groupby("Asset Class")["Profit/Loss Amount"].sum().sort_values(ascending=False)
            fig2 = px.bar(
                asset_breakdown,
                x=asset_breakdown.values,
                y=asset_breakdown.index,
                orientation='h',
                title="Total Profit by Asset Class",
                labels={'x': 'Total Profit/Loss ($)', 'y': 'Asset Class'},
                text=asset_breakdown.values,
            )
            fig2.update_traces(texttemplate='$%{text:,.2f}', textposition='outside')
            st.plotly_chart(fig2)

        with tab3:
            st.subheader("Trade Inspection")
            # --- Top/Bottom Trades ---
            num_display_trades = st.slider("Number of trades to display:", 5, 50, 10)
            st.write(f"**🔥 Top {num_display_trades} Trades**")
            st.dataframe(df_selection.sort_values("Profit/Loss Amount", ascending=False).head(num_display_trades))
            
            st.write(f"**🧊 Bottom {num_display_trades} Trades**")
            st.dataframe(df_selection.sort_values("Profit/Loss Amount", ascending=True).head(num_display_trades))

            # --- Display Original Data Table ---
            with st.expander("View Full Parsed Data Table & Export"):
                st.dataframe(df)
                st.download_button(
                    label="Download data as CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name='parsed_trades.csv',
                    mime='text/csv',
                )

    except KeyError as e:
        st.error(f"An error occurred: The column {e} was not found. Please check the HTML source or the parsing logic.")

# --- Password Protection ---
def check_password():
    """Returns `True` if the user is authenticated."""

    # If user is already authenticated, show dashboard immediately.
    if st.session_state.get("password_correct", False):
        return True

    # Show login form.
    st.title("📊 Trading Dashboard")
    password = st.text_input("Enter Password", type="password")

    if password == st.secrets["PASSWORD"]:
        # If password is correct, set session state and rerun.
        st.session_state["password_correct"] = True
        st.rerun()
    elif password:
        # If a password was entered but it's wrong, show an error.
        st.error("The password you entered is incorrect.")
        return True
    return False

if check_password():
    # Once authenticated, the main app title is set inside show_dashboard
    # or we can set it here if we move the title out of the login form.
    st.title("📊 Trading Dashboard")
    show_dashboard()