# L2 Showdown: Arbitrum vs. Optimism Dashboard

A real-time Streamlit dashboard comparing key metrics between Arbitrum and Optimism Layer 2 blockchain networks.

## Features

- **Total Value Locked (TVL)**: Historical TVL comparison from DefiLlama
- **Daily Active Users**: User activity metrics from Dune Analytics
- **Transaction Count**: Daily transaction volume comparison
- **Average Gas Fees**: Gas fee trends in USD
- **Correlation Analysis**: Gas fee vs transaction count correlations
- **Interactive Visualizations**: Plotly charts for all metrics

## Prerequisites

- Python 3.8+
- Dune Analytics account (free tier works)
- Dune API key

## Installation

1. Clone this repository or navigate to the project directory

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Get Dune API Key

1. Go to [Dune Analytics](https://dune.com) and create an account
2. Navigate to Settings → API Keys
3. Create a new API key and copy it

### 2. Create Dune Queries

You need to create two queries in Dune Analytics:

**Arbitrum Query:**
```sql
SELECT
    DATE_TRUNC('day', block_time) AS date,
    COUNT(DISTINCT "from") AS daily_active_users,
    COUNT(hash) AS transaction_count,
    SUM(gas_used * gas_price / 1e18 * p.price) / COUNT(hash) AS avg_gas_fee_usd
FROM arbitrum.transactions t
LEFT JOIN prices.usd p ON p.minute = DATE_TRUNC('minute', t.block_time)
    AND p.symbol = 'ETH'
WHERE
    t.block_time >= NOW() - INTERVAL '90' DAY
GROUP BY 1
ORDER BY 1 DESC
```

**Optimism Query:**
```sql
SELECT
    DATE_TRUNC('day', block_time) AS date,
    COUNT(DISTINCT "from") AS daily_active_users,
    COUNT(hash) AS transaction_count,
    SUM(gas_used * gas_price / 1e18 * p.price) / COUNT(hash) AS avg_gas_fee_usd
FROM optimism.transactions t
LEFT JOIN prices.usd p ON p.minute = DATE_TRUNC('minute', t.block_time)
    AND p.symbol = 'ETH'
WHERE
    t.block_time >= NOW() - INTERVAL '90' DAY
GROUP BY 1
ORDER BY 1 DESC
```

After creating each query, save it and copy the Query ID from the URL (e.g., `dune.com/queries/1234567` → ID is `1234567`).

📖 **Detailed setup instructions**: See [DUNE_SETUP_GUIDE.md](DUNE_SETUP_GUIDE.md)

### 3. Set Environment Variables

**Local Development:**

Create a `.env` file or export in terminal:
```bash
export DUNE_API_KEY="your_dune_api_key"
export ARBITRUM_QUERY_ID="your_arbitrum_query_id"
export OPTIMISM_QUERY_ID="your_optimism_query_id"
```

**Deployment (Railway, Heroku, etc.):**

Add these as environment variables in your platform's settings.

## Usage

Run the Streamlit app:

```bash
streamlit run main.py
```

The app will open in your browser at `http://localhost:8501`

## How It Works

1. **Data Sources:**
   - TVL data: Fetched from DefiLlama API
   - Chain metrics: Fetched from Dune Analytics using pre-created queries

2. **Caching:**
   - Data is cached for 1 hour to reduce API calls
   - Cache is automatically refreshed after TTL expires

3. **Free Tier Support:**
   - Uses query IDs (works with free Dune accounts)
   - Falls back to raw SQL if query IDs aren't set (requires paid plan)

## Project Structure

```
.
├── main.py                 # Main Streamlit application
├── DUNE_SETUP_GUIDE.md    # Detailed Dune Analytics setup guide
└── README.md              # This file
```

## Troubleshooting

- **"Query ID not found"**: Verify your query IDs are correct and queries are saved in Dune
- **"API key invalid"**: Regenerate your API key in Dune settings
- **"Paid plan required"**: Set `ARBITRUM_QUERY_ID` and `OPTIMISM_QUERY_ID` environment variables
- **Empty data**: Ensure queries ran successfully in Dune first


## Contributing

Feel free to submit issues or pull requests!

