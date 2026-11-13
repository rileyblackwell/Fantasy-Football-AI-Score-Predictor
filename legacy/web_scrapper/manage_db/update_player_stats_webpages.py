import sqlite3
import requests
import sys
from datetime import datetime, timedelta

def fetch_and_store_player_stats_html(position=None):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    if position:
        cursor.execute("SELECT player_url FROM player_positions WHERE data = ?", (position,))
    else:
        cursor.execute("SELECT player_url FROM player_positions")
    player_urls = cursor.fetchall()

    for url in player_urls:
        player_url = url[0]

        # Check if the webpage is up to date
        cursor.execute("SELECT date_created FROM player_stats_html WHERE player_url = ?", (player_url,))
        result = cursor.fetchone()

        if result:
            date_created = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            if date_created > datetime.now() - timedelta(days=365):
                print(f"Player stats HTML webpage is up to date for {player_url}, skipping")
                continue

        # Fetch and store the webpage
        webpage_url = f"https://www.fantasypros.com/nfl/stats/{player_url}.php"
        try:
            response = requests.get(webpage_url)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            webpage = response.text
    
            cursor.execute("INSERT OR REPLACE INTO player_stats_html (player_url, stats_html, date_created) VALUES (?, ?, CURRENT_TIMESTAMP)", (player_url, webpage))
            conn.commit()
            print(f"Player stats HTML webpage fetched and stored for {player_url}")
    
        except requests.exceptions.RequestException as e:
            print(f"Error fetching player stats HTML webpage for {player_url}: {e}")
    
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <position>")
        sys.exit(1)

    position = sys.argv[1].lower()
    if position == 'all':
        fetch_and_store_player_stats_html()
    elif position in ['wr', 'rb', 'te', 'qb']:
        fetch_and_store_player_stats_html(position)
    else:
        print("Invalid position. Must be one of: wr, rb, te, qb, all")
        sys.exit(1)