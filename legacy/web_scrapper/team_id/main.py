import sqlite3
from html.parser import HTMLParser

class PlayerTeamIdRBParser(HTMLParser):
    def __init__(self):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.teams = []
        self.counter = 0
         
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):
        if self.in_td_tag:
            if self.counter % 10 == 0 or self.counter % 10 == 1:
                self.teams.append(f"{data}, ") 
            self.counter += 1 

class PlayerTeamIdWRTEParser(HTMLParser):
    def __init__(self):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.teams = []
        self.counter = 0
         
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):
        if self.in_td_tag:
            if self.counter % 9 == 0 or self.counter % 9 == 1:
                self.teams.append(f"{data}, ") 
            self.counter += 1

class PlayerTeamIdQBParser(HTMLParser):
    def __init__(self):
        super().__init__()     
        self.in_td_tag = False
        self.in_span_tag = False
        self.teams = []
        self.counter = 0
         
    def handle_starttag(self, tag, attrs):         
        if tag == 'td':
            self.in_td_tag = True
         
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td_tag = False    

    def handle_data(self, data):
        if self.in_td_tag:
            if self.counter % 12 == 0 or self.counter % 12 == 1:
                self.teams.append(f"{data}, ") 
            self.counter += 1
             
def get_player_stats_html_from_db(player):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    cursor.execute("SELECT stats_html FROM player_stats_html WHERE player_url = ?", (player,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return result[0]
    else:
        return None

def write_player_team_id_to_db(player, team_id):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    cursor.execute("INSERT OR REPLACE INTO player_team_id (player_url, data) VALUES (?, ?)", (player, team_id))
    conn.commit()
    
    conn.close()

def get_player_urls_from_db(position):
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    cursor.execute("SELECT player_url FROM player_positions WHERE data = ?", (position,))
    results = cursor.fetchall()
    
    conn.close()
    
    return [result[0] for result in results]

def main():
    # Process RB players
    parser = PlayerTeamIdRBParser()
    rb_player_urls = get_player_urls_from_db("rb")
    for player in rb_player_urls:
        stats_html = get_player_stats_html_from_db(player)
        if stats_html:
            parser.feed(stats_html)
        else:
            print(f"No stats found for player {player}")
            continue
        
        teams = parser.teams[:len(parser.teams) // 2]
        if len(teams) % 2 == 1:
            teams = parser.teams[:(len(parser.teams) + 2) // 2]
      
        # outputs the team id for the last 3 seasons   
        if len(teams) >= 8:
            team_id = ''.join(teams[-8:-2])
        elif len(teams) == 6:
            team_id = ''.join(teams[-6:-2])
        elif len(teams) == 4:
            team_id = ''.join(teams[-4:-2])
        else:
            team_id = ''
        
        write_player_team_id_to_db(player, team_id)
        parser.counter = 0 # resets the counter for the next player
        parser.teams.clear() # clears the list for the next player

    # Process WR and TE players
    parser = PlayerTeamIdWRTEParser()
    wr_te_player_urls = get_player_urls_from_db("wr") + get_player_urls_from_db("te")
    for player in wr_te_player_urls:
        stats_html = get_player_stats_html_from_db(player)
        if stats_html:
            parser.feed(stats_html)
        else:
            print(f"No stats found for player {player}")
            continue
        
        teams = parser.teams[:len(parser.teams) // 2]
        if len(teams) % 2 == 1:
            teams = parser.teams[:(len(parser.teams) + 2) // 2]
      
        # outputs the team id for the last 3 seasons   
        if len(teams) >= 8:
            team_id = ''.join(teams[-10:-4]) 
        elif len(teams) == 6:
            team_id = ''.join(teams[-8:-4])
        elif len(teams) == 4:
            team_id = ''.join(teams[-6:-4])
        else:
            team_id = ''
        
        write_player_team_id_to_db(player, team_id)
        parser.counter = 0 # resets the counter for the next player
        parser.teams.clear() # clears the list for the next player

    # Process QB players
    parser = PlayerTeamIdQBParser()
    qb_player_urls = get_player_urls_from_db("qb")
    for player in qb_player_urls:
        stats_html = get_player_stats_html_from_db(player)
        if stats_html:
            parser.feed(stats_html)
        else:
            print(f"No stats found for player {player}")
            continue
        
        teams = parser.teams[:len(parser.teams) // 2]
        if len(teams) % 2 == 1:
            teams = parser.teams[:(len(parser.teams) + 2) // 2]
      
        # outputs the team id for the last 3 seasons   
        if len(teams) >= 8:
            team_id = ''.join(teams[-8:-2]) 
        elif len(teams) == 6:
            team_id = ''.join(teams[-6:-2])
        elif len(teams) == 4:
            team_id = ''.join(teams[-4:-2])
        else:
            team_id = ''
        
        write_player_team_id_to_db(player, team_id)
        parser.counter = 0 # resets the counter for the next player
        parser.teams.clear() # clears the list for the next player

if __name__ == '__main__':
    main()