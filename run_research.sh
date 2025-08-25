#!/bin/bash

source .venv/bin/activate

# --- CONFIGURATION ---
# Define the "SYMBOL:EXCHANGE" pairs you want to test.
PAIRS=(
    "SUI/EUR:binance"
    "LINK/EUR:binance"
    "ETH/EUR:binance"
    "RENDER/EUR:binance"
    "SOL/EUR:binance"
    "XRP/EUR:binance"
    "AAVE/EUR:kraken"
    "ENA/EUR:kraken"
    # "FIL/EUR:kraken"
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

    # 2. Prepare the log file name.
    filename_symbol=$(echo "$symbol" | sed 's/\//_/g')
    log_file="${OUTPUT_DIR}/${filename_symbol}_${exchange}_research.log"

    echo "   -> Running research... Log file: ${log_file}"

    # 3. Execute the 'research' command, passing the exchange.
    # The 'research' command will handle the data download itself.
    cli research "$symbol" --exchange "$exchange" "$@" &> "$log_file"

    echo "✅ Finished research for ${symbol} on ${exchange}."
    echo "--------------------------------------------------"
done

echo "🎉 All backtesting research is complete."