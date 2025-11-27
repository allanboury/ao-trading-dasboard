import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import re
from bs4 import BeautifulSoup
from datetime import datetime, date
import freecurrencyapi
from currency_data import CURRENCY_DATA # Import the currency data

# --- PARSING LOGIC ---

def clean_and_format_number(text):
    if not text:
        return None
    # Removes common currency symbols, codes, and other non-numeric characters.
    cleaned_text = re.sub(r'[$\s,¥+%]|CHF|≈|lots', '', str(text), flags=re.IGNORECASE)
    return pd.to_numeric(cleaned_text, errors='coerce')

def format_close_date(date_str):
    if not date_str:
        return None
    # Handles relative dates like "X minutes ago" by converting them to today's date.
    if 'ago' in date_str.lower():
        return pd.to_datetime(date.today())
    try:
        return pd.to_datetime(datetime.strptime(date_str, '%d %b %Y, %I:%M %p'))
    except ValueError:
        return pd.to_datetime(date_str, errors='coerce')

def parse_html_to_dataframe(html_content):
    # Parses the raw HTML content to extract trade data into a pandas DataFrame.
    soup = BeautifulSoup(html_content, 'html.parser')
    records = soup.find_all('div', class_=re.compile(r'border-grey-300.*border-b.*last-of-type:border-none'))

    if not records:
        return pd.DataFrame()

    parsed_data = []
    # Loop through each trade record found in the HTML.
    for record in records:
        # Find all the necessary components first
        trade_type_span = record.find('div', class_='portfolio-styles_typeColumn__Psx6k').find('span', class_='laptop:flex hidden')
        asset_info_div = record.find('div', title='Asset info')
        pl_div = record.find('div', title='Profit/Loss')
        close_date_div = record.find('div', title='Close date')

        # If any essential part is missing, skip this record
        if not (trade_type_span and asset_info_div and pl_div and close_date_div):
            continue

        try:
            # Extract text from each element, with fallbacks for missing data.
            asset_name_p = asset_info_div.find('p', class_='font-semibold')
            asset_ticker_span = asset_info_div.find('span', class_='text-secondary')
            asset_class_container = asset_info_div.find('div', class_='flex items-center')
            asset_class_div = asset_class_container.find('div', class_=lambda x: x and 'mx-1' in x) if asset_class_container else None
            pl_amount_p = pl_div.find('p', class_='laptop:text-md')
            pl_percent_div = pl_div.find('div', class_='laptop:font-semibold')
            close_date_p = close_date_div.find('p', class_='text-secondary')
            
            # Build a dictionary directly, which is cleaner than a list
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
    # Final data cleaning and type conversion.
    df['Close Date'] = pd.to_datetime(df['Close Date'], errors='coerce')
    df = df.dropna(subset=['Close Date', 'Profit/Loss Amount']) # Drop rows where essential data is missing
    return df

# --- CURRENCY CONVERSION LOGIC ---
@st.cache_data(ttl=3600) # Cache the results for 1 hour to avoid excessive API calls.
def get_exchange_rates(api_key):
    # Fetches latest exchange rates from FreeCurrencyAPI and returns the data.
    try:
        client = freecurrencyapi.Client(api_key)
        rates = client.latest(base_currency='USD')
        return rates['data']
    except Exception as e:
        st.sidebar.error(f"Could not fetch exchange rates: {e}")
        st.sidebar.error(f"Could not fetch rates: {e}")
        return None


def show_dashboard():
    # --- Data Input Sidebar ---
    # This section handles the user input for the raw HTML data.
    st.sidebar.header("Data Input")
    html_input = st.sidebar.text_area("Paste HTML content here", height=250)

    if st.sidebar.button("Process HTML"):
        if html_input:
            with st.spinner("Processing data..."):
                df = parse_html_to_dataframe(html_input)
                if not df.empty:
                    # Store the parsed DataFrame in the session state to persist it across reruns.
                    st.session_state['df'] = df # Store the dataframe in session state
                    st.sidebar.success(f"Successfully parsed {len(df)} trades!")
                else:
                    st.sidebar.error("Could not find any valid trade data in the HTML.")
        else:
            st.sidebar.warning("Please paste HTML content before processing.")

    # Only show the dashboard if data has been processed and stored
    # This prevents errors if the user hasn't pasted any data yet.
    if 'df' not in st.session_state:
        st.info("Please paste your trading data HTML into the sidebar and click 'Process HTML' to view the dashboard.")
        st.stop()

    df = st.session_state['df']

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")

    # Reset button logic
    if st.sidebar.button("Reset All Filters"):
        # To reset, we delete the keys from session_state. On the next rerun,
        # the widgets will use their default values.
        for key in st.session_state.keys():
            if key.endswith('_filter'):
                del st.session_state[key]
        # Also clear the main dataframe to force reprocessing.
        if 'df' in st.session_state:
            del st.session_state['df']
        st.rerun()

    asset_class = st.sidebar.multiselect(
        "Select Asset Class:",
        options=df["Asset Class"].unique(),
        default=df["Asset Class"].unique(),
        key="asset_class_filter" # Add a key to manage state
    )

    # --- Dynamic Currency Selector from Hardcoded Data ---
    # Create a list of currency codes for the selectbox, sorted alphabetically.
    currency_options = sorted(list(CURRENCY_DATA.keys()))
    # Create a dictionary to map currency codes to their native symbols.
    currency_symbols = {code: details.get('symbol_native', '$') for code, details in CURRENCY_DATA.items()}
    
    # Function to format the display in the selectbox (e.g., "USD - US Dollar").
    def format_currency(code):
        return f"{code} - {CURRENCY_DATA[code]['name']}"

    # Find the index of 'USD' to set it as the default in the selectbox.
    try:
        default_ix = currency_options.index("USD")
    except ValueError:
        default_ix = 0 # Fallback to the first currency if USD is not in the list
    
    selected_currency = st.sidebar.selectbox(
        "Select Currency:",
        options=currency_options,
        index=default_ix, # Set default to USD
        key="currency_filter",
        format_func=format_currency
    )
    
    # --- Date Range Selector Widget ---
    start_date, end_date = st.sidebar.date_input(
        "Select Date Range:",
        value=(df["Close Date"].min(), df["Close Date"].max()),
        min_value=df["Close Date"].min(),
        max_value=df["Close Date"].max(),
        key="date_range_filter" # Add a key to manage state
    )
    
    # --- Filtering DataFrame ---
    df_selection = df.query( # Compare only the date part of 'Close Date'
        "`Asset Class` == @asset_class & `Close Date`.dt.date >= @start_date & `Close Date`.dt.date <= @end_date"
    )

    # Check if the dataframe is empty
    if df_selection.empty:
        st.warning("No data available for the selected filters. Please adjust your selection.")
        st.stop() # This will halt the app from running further
    
    # --- Handle Currency Conversion ---
    # This is done *after* filtering to ensure we only convert the data being displayed.
    currency_symbol = currency_symbols.get(selected_currency, "$")
    if selected_currency == "USD":
        # If the selected currency is the default (USD), no conversion is needed.
        df_selection["Converted P/L"] = df_selection["Profit/Loss Amount"]
    else:
        # For other currencies, fetch live exchange rates and apply conversion.
        rates = get_exchange_rates(st.secrets["CURRENCY_API_KEY"])
        conversion_rate = rates.get(selected_currency, 1) if rates else 1
        df_selection["Converted P/L"] = df_selection["Profit/Loss Amount"] * conversion_rate

    try:
        # --- Summary Metrics ---
        # Basic Metrics
        # All monetary calculations now use the "Converted P/L" column
        total_profit = df_selection["Converted P/L"].sum()
        num_trades = len(df_selection)
        oldest_date = df_selection["Close Date"].min().strftime("%Y-%m-%d")
        newest_date = df_selection["Close Date"].max().strftime("%Y-%m-%d")
        num_days_in_range = (end_date - start_date).days + 1

        # Advanced Metrics
        winning_trades = df_selection[df_selection["Profit/Loss Amount"] > 0] # Win/loss is based on original USD profit.
        losing_trades = df_selection[df_selection["Profit/Loss Amount"] <= 0] # Win/Loss is based on original data
        win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
        avg_win_percent = winning_trades["Percent"].mean() # Percent return is independent of currency.
        avg_loss_percent = losing_trades["Percent"].mean()
        gross_profit = winning_trades["Converted P/L"].sum()
        gross_loss = abs(losing_trades["Converted P/L"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        profit_by_day = total_profit / num_days_in_range if num_days_in_range > 0 else 0



        # Display metrics in a two-row layout.
        st.metric("Date range", f"{oldest_date} to {newest_date}")
        
        col1, col2, col3 = st.columns(3)
        row2_col1, row2_col2, row2_col3 = st.columns(3)
        
        col1.metric("Total Profit/Loss", f"{currency_symbol}{total_profit:,.2f}")
        col2.metric("Win Rate", f"{win_rate:.2f}%")
        col3.metric("Profit Factor", f"{profit_factor:.2f}")
        row2_col1.metric("Total Trades", num_trades)
        row2_col2.metric("Days in Range", f"{num_days_in_range} days")
        row2_col3.metric("Profit by Day", f"{currency_symbol}{profit_by_day:,.2f}")

        st.markdown("---")

        # --- Organize content into tabs ---
        tab1, tab2, tab3 = st.tabs(["📈 Performance Trend", "📊 Asset Breakdown", "🔍 Trade Details"])

        # --- Tab 1: Performance Trend Chart ---
        with tab1:
            st.subheader("Performance Over Time")
            daily_profit = df_selection.groupby(df_selection["Close Date"].dt.date)["Converted P/L"].sum()
            cumulative_profit = daily_profit.cumsum()

            # Create a combo chart with bars for daily P/L and a line for cumulative P/L.
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=daily_profit.index, y=daily_profit.values, name='Daily Profit/Loss',
                yaxis='y2', marker_color=['green' if p >= 0 else 'red' for p in daily_profit.values]
            ))
            fig.add_trace(go.Scatter(x=cumulative_profit.index, y=cumulative_profit.values, name='Cumulative Profit', mode='lines', line=dict(color='blue')))
            fig.update_layout(
                # Use a secondary y-axis for daily profit to improve readability.
                title_text="Cumulative & Daily Profit Trend", xaxis_title="Date",
                yaxis=dict(title=f"Cumulative Profit ({currency_symbol})", color="blue"),
                yaxis2=dict(title=f"Daily Profit/Loss ({currency_symbol})", overlaying="y", side="right"),
                legend=dict(title="Metric", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig)

        # --- Tab 2: Asset Breakdown Chart ---
        with tab2:
            st.subheader("Performance by Asset Class")
            asset_breakdown = df_selection.groupby("Asset Class")["Converted P/L"].sum().sort_values(ascending=False)
            fig2 = px.bar(
                asset_breakdown,
                x=asset_breakdown.values,
                y=asset_breakdown.index,
                orientation='h',
                title="Total Profit by Asset Class",
                labels={'x': f'Total Profit/Loss ({currency_symbol})', 'y': 'Asset Class'},
                text=asset_breakdown.values,
            )
            fig2.update_traces(texttemplate=f'{currency_symbol}%{{text:,.2f}}', textposition='outside')
            st.plotly_chart(fig2)

        # --- Tab 3: Trade Details and Data Export ---
        with tab3:
            st.subheader("Trade Inspection")
            # A slider allows the user to dynamically select how many trades to view.
            num_display_trades = st.slider("Number of trades to display:", 5, 50, 10)
            st.write(f"**🔥 Top {num_display_trades} Trades**")
            st.dataframe(df_selection.sort_values("Converted P/L", ascending=False).head(num_display_trades))
            
            st.write(f"**🧊 Bottom {num_display_trades} Trades**")
            st.dataframe(df_selection.sort_values("Converted P/L", ascending=True).head(num_display_trades))

            # An expander provides access to the full raw data and an export button.
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
    # Returns `True` if the user is authenticated, `False` otherwise
    # If user is already authenticated, show dashboard immediately.
    if st.session_state.get("password_correct", False):
        return True

    # Show login form if not authenticated.
    st.title("📊 Trading Dashboard")
    password = st.text_input("Enter Password", type="password")

    if password == st.secrets["PASSWORD"]:
        # If password is correct, set a flag in session state and rerun the script.
        # On the next run, the check at the top of this function will pass.
        st.session_state["password_correct"] = True
        st.rerun()
    elif password:
        # If a password was entered but it's wrong, show an error.
        st.error("The password you entered is incorrect.")
        return False # Return False to prevent the dashboard from showing.
    return False

# --- Main App Execution ---
# The app will only proceed to show the dashboard if the password check is successful.
if check_password():
    st.title("📊 Trading Dashboard")
    show_dashboard()