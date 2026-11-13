import sqlite3
import os

def create_database():
    # Define the database path
    db_path = os.path.join(os.getcwd(), "..", "player_stats.db")

    try:
        # Connect to the database (create if it doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create the tables
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS player_urls (
                player_url TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS webpage_html (
                player_url TEXT,
                webpage_year INTEGER,
                webpage_html TEXT,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (player_url, webpage_year),
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_weekly_data (
                player_url TEXT PRIMARY KEY,
                data TEXT,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_skill_scores (
                player_url TEXT PRIMARY KEY,
                data TEXT,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_rookie_season (
                player_url TEXT PRIMARY KEY,
                data TEXT,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_stats_html (
                player_url TEXT PRIMARY KEY,
                stats_html TEXT,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_positions (
                player_url TEXT PRIMARY KEY,
                data TEXT,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );

            CREATE TABLE IF NOT EXISTS player_team_id (
                player_url TEXT PRIMARY KEY,
                data TEXT,
                FOREIGN KEY (player_url) REFERENCES player_urls (player_url)
            );
        ''')

        # Commit the changes
        conn.commit()

        print("Database created/updated successfully!")

    except sqlite3.Error as e:
        print(f"Error creating/updating database: {e}")

    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == '__main__':
    create_database()