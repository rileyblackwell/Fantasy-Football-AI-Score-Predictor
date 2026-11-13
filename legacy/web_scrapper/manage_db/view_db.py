import sqlite3

def fetch_player_skill_score(player):
    try:
        # Connect to the database
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()

        # Fetch the player skill score
        cursor.execute("""
            SELECT data 
            FROM player_skill_scores
            WHERE player_url LIKE ?
        """, (f"%{player}%",))

        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"{row[0]}")
        else:
            print(f"No data found for {player}")

    except sqlite3.Error as e:
        print(f"Error fetching player skill score: {e}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        # Close the connection
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    player = "joe-burrow"
    fetch_player_skill_score(player)