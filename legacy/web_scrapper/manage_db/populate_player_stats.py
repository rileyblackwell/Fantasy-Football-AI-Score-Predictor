import sqlite3

def populate_player_urls():
    try:
        # Connect to the database
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()

        # Open the player_urls files and read their contents
        positions = ['rb', 'wr', 'te', 'qb']
        player_urls = {}
        for position in positions:
            with open(f"../player_urls/player_urls_{position}.out", "r") as f:
                player_urls[position] = [line.strip() for line in f.readlines()]

        # Insert each player URL into the player_urls table
        # and insert the corresponding position into the player_positions table
        for position, urls in player_urls.items():
            for url in urls:
                cursor.execute("INSERT OR IGNORE INTO player_urls (player_url) VALUES (?)", (url,))
                cursor.execute("INSERT OR IGNORE INTO player_positions (player_url, data) VALUES (?, ?)", (url, position))

        # Commit the changes
        conn.commit()

        print("Player URLs and positions populated successfully!")

    except sqlite3.Error as e:
        print(f"Error populating player URLs and positions: {e}")

    except FileNotFoundError:
        print("Error: one or more of the player_urls files not found")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        # Close the connection
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    populate_player_urls()