import streamlit as st
import pandas as pd
import requests
import time
import os
import plotly.express as px
from dune_client.client import DuneClient
from dune_client.query import QueryBase

# --- 0. Page Configuration ---
st.set_page_config(
    page_title="L2 Dashboard (Arbitrum vs. Optimism)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. Securely Load API Key ---
# Load the API key from environment variables (set in Railway)
DUNE_API_KEY = os.environ.get("DUNE_API_KEY")

if not DUNE_API_KEY:
    st.error("DUNE_API_KEY environment variable not set. Please set it in your deployment settings.")
    # We don't stop the app, but queries will fail
    dune_client = None
else:
    dune_client = DuneClient(DUNE_API_KEY)

# --- 2. Define SQL Queries and Query IDs ---
# Option 1: Use query IDs (works with free tier)
# Create queries manually in Dune Analytics UI and paste the query IDs here
ARBITRUM_QUERY_ID = os.environ.get("ARBITRUM_QUERY_ID")  # Set this in environment variables
OPTIMISM_QUERY_ID = os.environ.get("OPTIMISM_QUERY_ID")  # Set this in environment variables

# Option 2: Raw SQL queries (requires paid plan)
ARBITRUM_SQL_QUERY = """
SELECT
    DATE_TRUNC('day', block_time) AS date,
    COUNT(DISTINCT "from") AS daily_active_users,
    COUNT(hash) AS transaction_count,
    SUM(gas_used * gas_price / 1e18 * p.price) / COUNT(hash) AS avg_gas_fee_usd
FROM arbitrum.transactions t
LEFT JOIN prices.usd p ON p.minute = DATE_TRUNC('minute', t.block_time)
    AND p.symbol = 'ETH'
WHERE
    t.block_time >= NOW() - INTERVAL '90' DAY -- Look back 90 days
GROUP BY 1
ORDER BY 1 DESC
"""

OPTIMISM_SQL_QUERY = """
SELECT
    DATE_TRUNC('day', block_time) AS date,
    COUNT(DISTINCT "from") AS daily_active_users,
    COUNT(hash) AS transaction_count,
    SUM(gas_used * gas_price / 1e18 * p.price) / COUNT(hash) AS avg_gas_fee_usd
FROM optimism.transactions t
LEFT JOIN prices.usd p ON p.minute = DATE_TRUNC('minute', t.block_time)
    AND p.symbol = 'ETH'
WHERE
    t.block_time >= NOW() - INTERVAL '90' DAY -- Look back 90 days
GROUP BY 1
ORDER BY 1 DESC
"""

# --- 3. Cached Data Fetching Functions ---

@st.cache_data(ttl=3600)  # Cache for 1 hour (3600 seconds)
def fetch_defi_llama_tvl(chain_slug):
    """
    Fetches historical TVL data from DefiLlama.
    """
    url = f"https://api.llama.fi/charts/{chain_slug}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        # Fix FutureWarning by converting to numeric first
        df['date'] = pd.to_datetime(pd.to_numeric(df['date']), unit='s').dt.date
        df.rename(columns={'totalLiquidityUSD': 'tvl_usd'}, inplace=True)
        return df
    except requests.exceptions.RequestException as e:
        # Return empty DataFrame, error will be shown outside cached function
        return pd.DataFrame(columns=['date', 'tvl_usd'])

@st.cache_data(ttl=3600)  # Cache for 1 hour
def query_dune_api_by_id(query_id):
    """
    Executes a Dune query by ID (works with free tier).
    """
    if not dune_client:
        return pd.DataFrame()
    
    try:
        query = QueryBase(query_id=query_id, name="query")
        results_df = dune_client.run_query_dataframe(query)
        if not results_df.empty and 'date' in results_df.columns:
            results_df['date'] = pd.to_datetime(results_df['date']).dt.date
        return results_df
    except Exception as e:
        raise Exception(f"Dune API error for query ID {query_id}: {str(e)}")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def query_dune_api_by_sql(query_name, sql_query):
    """
    Executes a SQL query using run_sql (requires paid plan).
    """
    if not dune_client:
        return pd.DataFrame()
        
    try:
        # Use run_sql for raw SQL queries (requires paid plan)
        result = dune_client.run_sql(
            query_sql=sql_query,
            name=query_name,
            is_private=True,
            archive_after=True
        )
        
        # Extract data from result object
        rows = None
        if hasattr(result, 'result') and result.result:
            if hasattr(result.result, 'rows'):
                rows = result.result.rows
            elif hasattr(result.result, 'data') and hasattr(result.result.data, 'rows'):
                rows = result.result.data.rows
        elif hasattr(result, 'get_rows'):
            rows = result.get_rows()
        elif hasattr(result, 'rows'):
            rows = result.rows
        
        if rows:
            results_df = pd.DataFrame(rows)
            if not results_df.empty and 'date' in results_df.columns:
                results_df['date'] = pd.to_datetime(results_df['date']).dt.date
            return results_df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        error_msg = str(e)
        if "paid plan" in error_msg.lower() or "upgrade" in error_msg.lower():
            raise Exception(
                f"Dune API requires a paid plan to create queries programmatically. "
                f"Please create queries manually in Dune Analytics UI and use query IDs instead. "
                f"Set ARBITRUM_QUERY_ID and OPTIMISM_QUERY_ID environment variables."
            )
        raise Exception(f"Dune API error for {query_name}: {error_msg}")

# --- 4. Main Dashboard UI ---

st.title("L2 Showdown: Arbitrum vs. Optimism")

# --- Setup Instructions (if query IDs not set) ---
if not ARBITRUM_QUERY_ID or not OPTIMISM_QUERY_ID:
    with st.expander("ℹ️ Dune API Setup Instructions (Free Tier)", expanded=False):
        st.info("""
        **To use Dune API with a free account:**
        
        1. Go to [Dune Analytics](https://dune.com) and create an account
        2. Create two queries manually in the Dune UI:
           - One for Arbitrum data (use the SQL query in the code)
           - One for Optimism data (use the SQL query in the code)
        3. Copy the query IDs from the URL (e.g., if URL is `dune.com/queries/12345`, the ID is `12345`)
        4. Set environment variables:
           - `ARBITRUM_QUERY_ID=your_arbitrum_query_id`
           - `OPTIMISM_QUERY_ID=your_optimism_query_id`
        
        **Alternative:** If you have a paid Dune plan, the app will automatically use raw SQL queries.
        """)

# --- Load Data ---
with st.spinner("Loading all chain data... This may take a moment on first load."):
    st.toast("Fetching DefiLlama TVL data for arbitrum...")
    arbitrum_tvl_df = fetch_defi_llama_tvl('arbitrum')
    if arbitrum_tvl_df.empty:
        st.error("Error fetching Arbitrum TVL data from DefiLlama")
    
    st.toast("Fetching DefiLlama TVL data for optimism...")
    optimism_tvl_df = fetch_defi_llama_tvl('optimism')
    if optimism_tvl_df.empty:
        st.error("Error fetching Optimism TVL data from DefiLlama")
    
    st.toast("Executing Dune query for arbitrum...")
    arbitrum_dune_df = pd.DataFrame()
    try:
        # Try using query ID first (works with free tier)
        if ARBITRUM_QUERY_ID:
            try:
                arbitrum_dune_df = query_dune_api_by_id(int(ARBITRUM_QUERY_ID))
            except ValueError:
                st.error(f"Invalid ARBITRUM_QUERY_ID: {ARBITRUM_QUERY_ID}. Must be a number.")
        else:
            # Fall back to SQL query (requires paid plan)
            st.warning("⚠️ ARBITRUM_QUERY_ID not set. Attempting to use raw SQL (requires paid Dune plan)...")
            try:
                arbitrum_dune_df = query_dune_api_by_sql('arbitrum', ARBITRUM_SQL_QUERY)
            except Exception as sql_error:
                if "paid plan" in str(sql_error).lower():
                    st.error("❌ Dune API requires a paid plan for raw SQL queries. Please set ARBITRUM_QUERY_ID environment variable. See setup instructions above.")
                else:
                    raise
        
        if arbitrum_dune_df.empty:
            st.warning("Arbitrum Dune query returned no data. This may be normal if the query is still executing.")
    except Exception as e:
        st.error(f"Error querying Dune API for arbitrum: {e}")
        arbitrum_dune_df = pd.DataFrame()
    
    st.toast("Executing Dune query for optimism...")
    optimism_dune_df = pd.DataFrame()
    try:
        # Try using query ID first (works with free tier)
        if OPTIMISM_QUERY_ID:
            try:
                optimism_dune_df = query_dune_api_by_id(int(OPTIMISM_QUERY_ID))
            except ValueError:
                st.error(f"Invalid OPTIMISM_QUERY_ID: {OPTIMISM_QUERY_ID}. Must be a number.")
        else:
            # Fall back to SQL query (requires paid plan)
            st.warning("⚠️ OPTIMISM_QUERY_ID not set. Attempting to use raw SQL (requires paid Dune plan)...")
            try:
                optimism_dune_df = query_dune_api_by_sql('optimism', OPTIMISM_SQL_QUERY)
            except Exception as sql_error:
                if "paid plan" in str(sql_error).lower():
                    st.error("❌ Dune API requires a paid plan for raw SQL queries. Please set OPTIMISM_QUERY_ID environment variable. See setup instructions above.")
                else:
                    raise
        
        if optimism_dune_df.empty:
            st.warning("Optimism Dune query returned no data. This may be normal if the query is still executing.")
    except Exception as e:
        st.error(f"Error querying Dune API for optimism: {e}")
        optimism_dune_df = pd.DataFrame()

# --- Merge Data ---
@st.cache_data
def merge_data(tvl_df, dune_df):
    if tvl_df.empty or dune_df.empty:
        return pd.DataFrame()
    return pd.merge(tvl_df, dune_df, on='date', how='inner')

arbitrum_full_df = merge_data(arbitrum_tvl_df, arbitrum_dune_df)
optimism_full_df = merge_data(optimism_tvl_df, optimism_dune_df)

if arbitrum_full_df.empty or optimism_full_df.empty:
    st.error("Data merging failed. Check if all APIs returned data.")
else:
    st.success("All data loaded and merged successfully!")

    # --- Key Metrics ---
    st.header("At-a-Glance (Latest Data)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Get latest row
    arb_latest = arbitrum_full_df.iloc[-1]
    op_latest = optimism_full_df.iloc[-1]

    col1.metric("Arbitrum TVL", f"${arb_latest['tvl_usd']/1e9:.2f}B")
    col2.metric("Optimism TVL", f"${op_latest['tvl_usd']/1e9:.2f}B")
    col3.metric("Arbitrum Daily Users", f"{arb_latest['daily_active_users']:,}")
    col4.metric("Optimism Daily Users", f"{op_latest['daily_active_users']:,}")

    # --- Visualizations ---
    st.header("Comparative Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Total Value Locked (TVL)")
        fig_tvl = px.line(title="TVL (USD) Over Time")
        fig_tvl.add_scatter(x=arbitrum_full_df['date'], y=arbitrum_full_df['tvl_usd'], name="Arbitrum")
        fig_tvl.add_scatter(x=optimism_full_df['date'], y=optimism_full_df['tvl_usd'], name="Optimism")
        st.plotly_chart(fig_tvl, use_container_width=True)

    with col2:
        st.subheader("Daily Active Users (DAU)")
        fig_dau = px.line(title="Daily Active Users Over Time")
        fig_dau.add_scatter(x=arbitrum_full_df['date'], y=arbitrum_full_df['daily_active_users'], name="Arbitrum")
        fig_dau.add_scatter(x=optimism_full_df['date'], y=optimism_full_df['daily_active_users'], name="Optimism")
        st.plotly_chart(fig_dau, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Transaction Count")
        fig_tx = px.line(title="Daily Transactions Over Time")
        fig_tx.add_scatter(x=arbitrum_full_df['date'], y=arbitrum_full_df['transaction_count'], name="Arbitrum")
        fig_tx.add_scatter(x=optimism_full_df['date'], y=optimism_full_df['transaction_count'], name="Optimism")
        st.plotly_chart(fig_tx, use_container_width=True)

    with col4:
        st.subheader("Average Gas Fee (USD)")
        fig_gas = px.line(title="Average Gas Fee (USD) Over Time")
        fig_gas.add_scatter(x=arbitrum_full_df['date'], y=arbitrum_full_df['avg_gas_fee_usd'], name="Arbitrum")
        fig_gas.add_scatter(x=optimism_full_df['date'], y=optimism_full_df['avg_gas_fee_usd'], name="Optimism")
        st.plotly_chart(fig_gas, use_container_width=True)

    # --- Correlation Analysis ---
    st.header("Correlation Analysis")
    try:
        arb_gas_corr = arbitrum_full_df['avg_gas_fee_usd'].corr(arbitrum_full_df['transaction_count'])
        op_gas_corr = optimism_full_df['avg_gas_fee_usd'].corr(optimism_full_df['transaction_count'])
        
        col1, col2 = st.columns(2)
        col1.metric("Arbitrum: Gas Fee vs. Tx Count Corr.", f"{arb_gas_corr:.2f}")
        col2.metric("Optimism: Gas Fee vs. Tx Count Corr.", f"{op_gas_corr:.2f}")
    except Exception as e:
        st.warning(f"Could not calculate correlation: {e}")

    # --- Raw Data ---
    with st.expander("Show Raw Merged Dataframes"):
        st.subheader("Arbitrum Raw Data")
        st.dataframe(arbitrum_full_df.tail())
        st.subheader("Optimism Raw Data")
        st.dataframe(optimism_full_df.tail())