# Crypto Stop Loss Bot

A Python-based backend service for managing cryptocurrency stuff, especially trailing stop loss orders in Bit2Me.

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
    BIT2ME_API_BASE_URL=
    BIT2ME_API_KEY=
    BIT2ME_API_SECRET=
   ```

6. Run the service:
   ```
   task start
   ```  

## Project Structure

The backend follows Clean Architecture principles, organizing code into layers:

...