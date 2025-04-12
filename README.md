# Crypto Trailing Stop Loss Project - Backend

A Python-based backend service for managing cryptocurrency trailing stop loss orders.

## Description

This project provides a backend service that implements trailing stop loss functionality for cryptocurrency trading. It monitors crypto prices and automatically executes sell orders based on trailing stop loss rules.

## Prerequisites

- Python 3.13 or higher
- uv package manager

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/jsoladur/crypto-trailing-stop-loss-project.git
   cd crypto-trailing-stop-loss-project/backend
   ```

2. Set up a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate  # On Unix/macOS
   # OR
   .venv\Scripts\activate     # On Windows
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Create a `.env` file in the root directory and add your configuration:
   ```
    # CORS enabled
    CORS_ENABLED=false
    # Bit2Me API configuration
    bit2me_api_base_url=
    bit2me_api_key=
    bit2me_api_secret=
   ```

6. Run the service:
   ```
   task start
   ```  
