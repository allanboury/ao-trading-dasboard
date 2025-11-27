# 📊 Trading Performance Dashboard

This is an interactive web application built with Streamlit for analyzing and visualizing personal trading performance. The dashboard allows users to paste raw HTML data from their trading platform's closed positions page, parses the data in real-time, and presents a comprehensive overview of trading metrics and trends.

---

## ✨ Features

-   **Secure Access:** Password-protected entry to ensure data privacy.
-   **Dynamic HTML Parsing:** No need for manual data entry. Simply paste the HTML source of your closed trades page.
-   **Interactive Filtering:** Filter your performance data by asset class (e.g., Stocks, Forex, Crypto) and by a specific date range.
-   **Multi-Currency Support:** View all monetary values in your preferred currency (e.g., USD, EUR, BRL), with real-time exchange rates.
-   **Comprehensive Metrics:** Includes key performance indicators such as:
    -   Total Profit/Loss
    -   Win Rate (%)
    -   Profit Factor
    -   Total Number of Trades
    -   Average Profit per Day
-   **Rich Visualizations:**
    -   A combo chart showing cumulative profit trend (line) and daily profit/loss (bars).
    -   A horizontal bar chart breaking down profit by asset class.
    -   Interactive tables for inspecting the top and bottom performing trades.
-   **Data Export:** Download your parsed and cleaned trading data as a `.csv` file for further analysis.

---

## 🚀 How to Use the Deployed App

1.  **Navigate to the App URL:** Access the live application via its Streamlit Community Cloud URL.
2.  **Enter Password:** Provide the password to gain access to the dashboard.
3.  **Get Your Data:**
    -   Log in to your trading platform.
    -   Navigate to the page that lists your closed trading positions.
    -   Open your browser's "View Page Source" tool (usually by right-clicking on the page and selecting the option, or pressing `Ctrl+U`).
    -   Copy the **entire** HTML content (`Ctrl+A`, then `Ctrl+C`).
4.  **Process in Dashboard:**
    -   In the dashboard's sidebar, paste the copied HTML into the text area under "Data Input".
    -   Click the **"Process HTML"** button.
5.  **Analyze:** The dashboard will instantly update with your data. Use the filters in the sidebar to explore your performance.

---

## 🛠️ Local Development Setup

To run this application on your local machine, follow these steps.

### Prerequisites

-   Python 3.8+
-   Git

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YourUsername/ao-trading-dashboard.git
    cd ao-trading-dashboard
    ```
    *(Replace `YourUsername` with your actual GitHub username)*

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your secrets:**
    -   Create a folder named `.streamlit` in the project root.
    -   Inside `.streamlit`, create a file named `secrets.toml`.
    -   Add your secrets to this file in the following format:
        ```toml
        PASSWORD = "your_chosen_dashboard_password"
        CURRENCY_API_KEY = "your_api_key_from_freecurrencyapi.com"
        ```

### Running the App

Once set up, you can run the Streamlit app with the following command:

```bash
streamlit run dashboard.py
