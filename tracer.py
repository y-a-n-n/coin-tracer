import requests
import csv
import time
import json
import os

CACHE_FILE = 'cache.json'

# Load the cache from the cache file
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save the cache to the cache file
def save_cache(cache):
    with open(CACHE_FILE, 'w') as file:
        json.dump(cache, file, indent=4)

# Function to get cached response or make a request and cache the result
def get_cached_response(url):
    cache = load_cache()

    # Check if the URL is already cached
    if url in cache:
        print(f"Using cached response for {url}")
        return cache[url]

    # If not cached, make the API request
    print(f"Making API request for {url}")
    response = requests.get(url)
    if response.status_code == 200:
        cache[url] = response.json()

        # Save the updated cache to the file
        save_cache(cache)

        return cache[url]
    else:
        raise Exception(f"Failed to fetch data from {url}, Status Code: {response.status_code}")

# Function to get details of a single transaction using the Blockchain.info API
def get_transaction_details(tx_hash):
    api_url = f"https://blockchain.info/rawtx/{tx_hash}"
    return get_cached_response(api_url)

# Function to get Bitcoin to AUD conversion rate at the time of transaction
def get_btc_to_aud_rate(timestamp):
    date_str = time.strftime('%d-%m-%Y', time.gmtime(timestamp))
    api_url = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={date_str}&localization=false"
    data = get_cached_response(api_url)
    return data['market_data']['current_price']['aud']

# Check if the wallet belongs to a terminating wallet (Binance, Coinbase, or other known wallet)
def is_terminating_wallet(wallet_address, terminating_wallets):
    return wallet_address in terminating_wallets

# Recursive function to trace transactions back from a starting wallet
def trace_transactions(tx_hash, starting_wallet_id, csv_writer, terminating_wallets):
    tx_data = get_transaction_details(tx_hash)

    for tx_input in tx_data['inputs']:
        source_wallet = tx_input['prev_out']['addr']  # Source wallet
        coin_amount = int(tx_input['prev_out']['value'])  # Value in satoshis

        for tx_output in tx_data['out']:
            dest_wallet = tx_output['addr']  # Destination wallet
            dest_value = int(tx_output['value'])  # Destination value in satoshis

            fees = sum(int(out['value']) for out in tx_data['out']) - coin_amount  # Fees are input - output
            tx_hash = tx_data['hash']
            timestamp = int(time.time())  # No timestamp in response, using current time as a placeholder

            # Convert values from satoshis to BTC (1 BTC = 100,000,000 satoshis)
            coin_amount_btc = coin_amount / 100000000
            dest_value_btc = dest_value / 100000000
            fees_btc = fees / 100000000

            # Get the AUD equivalent
            btc_to_aud_rate = get_btc_to_aud_rate(timestamp)
            coin_amount_aud = coin_amount_btc * btc_to_aud_rate
            fees_aud = fees_btc * btc_to_aud_rate

            # Write to CSV, with transaction ID linked to starting wallet
            csv_writer.writerow([starting_wallet_id, source_wallet, dest_wallet, dest_value_btc, fees_btc,
                                 dest_value_btc * btc_to_aud_rate, fees_aud, tx_hash])

            # Recursively trace back the source wallet unless it's a terminating wallet
            if not is_terminating_wallet(source_wallet, terminating_wallets):
                try:
                    txs = get_wallet_transactions(dest_wallet)
                    for txn in txs:
                        trace_transactions(txn, starting_wallet_id, csv_writer, terminating_wallets)  # Recur with source transaction
                except Exception as e:
                    print(f"Failed to trace transaction from {source_wallet}: {e}")
            else:
                print(f"Reached a terminating wallet: {source_wallet}")
                return

def get_wallet_transactions(wallet_address):
    """
    Fetches transactions for the given Bitcoin wallet address.

    Parameters:
    - wallet_address (str): The Bitcoin wallet address.

    Returns:
    - dict: The first transaction from the wallet's history (to begin tracing).
    """
    api_url = f"https://blockchain.info/rawaddr/{wallet_address}"
    data = get_cached_response(api_url)

    # Return all transactions for this wallet
    if 'txs' in data and len(data['txs']) > 0:
        # Return the first transaction (or handle this differently as needed)
        return data['txs'][0]  # You could modify this to handle multiple transactions
    else:
        raise Exception(f"No transactions found for wallet {wallet_address}")

# Main function to handle multiple starting and terminating wallets
def main(starting_wallets, terminating_wallets):
    # Open CSV file to write results
    with open('transaction_trace.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write the headers
        writer.writerow(['Starting Wallet ID', 'Source Wallet', 'Dest Wallet', 'Coin Amount (BTC)', 'Fees (BTC)',
                         'AUD Equivalent of Coin Amount', 'AUD Equivalent of Fees', 'Transaction Hash'])

        # Loop through all starting wallets
        for starting_wallet in starting_wallets:
            try:
                # Fetch the initial transaction hash to start tracing from the starting wallet
                initial_tx = get_wallet_transactions(starting_wallet)  # You need to implement this function
                trace_transactions(initial_tx['hash'], starting_wallet, writer, terminating_wallets)
            except Exception as e:
                print(f"Error tracing transactions for wallet {starting_wallet}: {e}")

if __name__ == "__main__":
    # Example lists of starting and terminating wallets
    starting_wallets = []  # Replace with actual starting wallet addresses
    terminating_wallets = []  # Replace with actual known terminating wallet addresses

    main(starting_wallets, terminating_wallets)
