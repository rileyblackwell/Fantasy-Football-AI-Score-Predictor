import sqlite3

def read_player_urls_from_db():
    """Reads player urls from the database and returns it as a list of rows."""
    try:
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM player_urls")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except sqlite3.Error as e:
        print(f"Error reading from database: {e}")
        return []
    
def read_player_weekly_data_from_db(player_url):
    """Reads player weekly data from the database and returns it as a list of rows."""
    try:
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM player_weekly_data WHERE player_url = '{player_url}'")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except sqlite3.Error as e:
        print(f"Error reading from database: {e}")
        return []   
    
def read_player_position_from_db(player_url):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    cursor.execute("SELECT data FROM player_positions WHERE player_url = ?", (player_url,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]
    else:
        return None