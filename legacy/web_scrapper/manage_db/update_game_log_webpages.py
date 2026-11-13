import sqlite3
import requests
import sys

def fetch_and_store_webpages(position=None):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    if position:
        cursor.execute("SELECT player_url FROM player_positions WHERE data = ?", (position,))
    else:
        cursor.execute("SELECT player_url FROM player_positions")
    player_urls = cursor.fetchall()

    for season in range(2018, 2024):
        for url in player_urls:
            player_url = url[0]
            webpage_url = f"https://www.fantasypros.com/nfl/games/{player_url}.php?season={season}"

            # Check if the webpage already exists in the database
            cursor.execute("SELECT * FROM webpage_html WHERE player_url = ? AND webpage_year = ?", (player_url, season))
            existing_webpage = cursor.fetchone()

            if not existing_webpage:
                try:
                    response = requests.get(webpage_url)
                    response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
                    webpage = response.text

                    cursor.execute("INSERT INTO webpage_html (player_url, webpage_year, webpage_html) VALUES (?, ?, ?)", (player_url, season, webpage))
                    conn.commit()
                    print(f"Webpage fetched and stored for {player_url} - {season}")

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching webpage for {player_url}: {e}")
            else:
                print(f"Webpage already exists for {player_url} - {season}, skipping")

    conn.close()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <position>")
        sys.exit(1)

    position = sys.argv[1].lower()
    if position == 'all':
        fetch_and_store_webpages()
    elif position in ['wr', 'rb', 'te', 'qb']:
        fetch_and_store_webpages(position)
    else:
        print("Invalid position. Must be one of: wr, rb, te, qb, all")
        sys.exit(1)