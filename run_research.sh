#!/bin/bash

source .venv/bin/activate

# --- CONFIGURATION ---
# Define the "SYMBOL:EXCHANGE" pairs you want to test.
PAIRS=(
    "DOGE/USDT:mexc"
    "HYPE/USDT:mexc"
    "LINK/USDT:mexc"
    "SUI/USDT:mexc"
    "DOT/USDT:mexc"
    "SOL/USDT:mexc"
    "ADA/USDT:mexc"
    "ETH/USDT:mexc"
    # Current trading
    # New coins
    # "PEPE/USDT:mexc"
    # "PENGU/USDT:mexc"
    # "NEAR/USDT:mexc"
    # "EGLD/USDT:mexc"
    # "BNB/USDT:mexc"
    # Divergence coins
    # "GALA/USDT:mexc"
    # "SHIB/USDT:mexc"
    # "XLM/USDT:mexc"
    # Deprecated
    "XRP/USDT:mexc"
    "RENDER/USDT:mexc"
)

# Define the directory where the result logs will be saved.
OUTPUT_DIR="out"

# --- SCRIPT LOGIC ---
echo "🚀 Starting backtesting research for all pairs..."

# Create the output directory if it doesn't exist.
mkdir -p "$OUTPUT_DIR"
echo "Output will be saved in the '$OUTPUT_DIR' directory."
echo "--------------------------------------------------"

# Loop through each pair in the array.
for pair in "${PAIRS[@]}"; do
    # 1. Extract the symbol and exchange from the pair.
    symbol=$(echo "$pair" | cut -d':' -f1)
    exchange=$(echo "$pair" | cut -d':' -f2)

    echo "Processing pair: ${symbol} on ${exchange}"

    # 2. Prepare the log file names.
    filename_symbol=$(echo "$symbol" | sed 's/\//_/g')
    log_file="${OUTPUT_DIR}/${filename_symbol}_${exchange}_research.log"
    progress_file="${OUTPUT_DIR}/${filename_symbol}_${exchange}_progress.log"

    echo "   -> Running research... Log file: ${log_file}, Error file: ${progress_file}"

    # 3. Execute the 'research' command, passing the exchange.
    #    Redirect stdout to log_file and stderr to progress_file.
    cli research "$symbol" --exchange="$exchange" --min-sqn=1.8 --min-profit-factor=1.5 "$@" > "$log_file" 2> "$progress_file"

    echo "✅ Finished research for ${symbol} on ${exchange}."
    echo "--------------------------------------------------"
done

echo "🎉 All backtesting research is complete."
