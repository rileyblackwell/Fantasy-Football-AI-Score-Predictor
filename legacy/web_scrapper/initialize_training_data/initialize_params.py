import sqlite3


def create_team_ids(dst_ids, player_urls):
    """
    Creates a list of dictionaries containing team IDs for each season.

    Args:
        dst_ids (dict): Dictionary of DST IDs.
        player_urls (list): List of player URLs.

    Returns:
        list: A list of dictionaries, each containing season-wise team IDs.
    """
    dst_ids['ALL'] = '33'  # ID if player played for multiple teams in a season

    team_ids = []
    for player_url in player_urls:
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM player_team_id WHERE player_url = ?", player_url)
        result = cursor.fetchone()
        conn.close()

        if result:
            data = result[0].split('\n')
            player_team_ids = {}
            for line in data:
                line = line.split(',')
                for i in range(0, len(line), 2):
                    season = get_season(line[i])
                    if season:
                        player_team_ids[season] = dst_ids[line[i + 1].strip()]
            team_ids.append(player_team_ids)
        else:
            team_ids.append({})

    return team_ids

def get_season(year):
    """
    Maps the year to the corresponding season.

    Args:
        year (str): The year.

    Returns:
        int: The season.
    """
    season_map = {'2021': 1, '2022': 2, '2023': 3}
    return season_map.get(year.strip(), None)


def create_skill_score(player_urls):
    """
    Creates a list of skill scores.

    Args:
        player_urls (list): List of player URLs.

    Returns:
        list: A list of skill scores.
    """
    skill_scores = []
    for player_url in player_urls:
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM player_skill_scores WHERE player_url = ?", player_url)
        result = cursor.fetchone()
        conn.close()

        if result:
            data = result[0].split('\n')
            player_skill_score = 0
            seasons = 0
            for line in data:
                line = line.split(',')
                if len(line) > 1:
                    try:
                        player_skill_score += float(line[1]) / float(line[0])
                    except ValueError:
                        player_skill_score += 0.0
                    except ZeroDivisionError:
                        if float(line[0]) != 0 and float(line[1]) != 0:  # Error occurs when dividing 0 points scored / 0 games played
                            raise ZeroDivisionError
                    seasons += 1
            try:
                skill_scores.append(str(round(player_skill_score / seasons, 2)))
            except ZeroDivisionError:
                skill_scores.append('0.0')
        else:
            skill_scores.append('0.0')

    return skill_scores


def create_seasons_played(player_urls):
    """
    Creates a list of number of seasons played for each player.

    Args:
        player_urls (list): List of player URLs.

    Returns:
        list: A list of number of seasons played for each player.
    """
    seasons_played = []
    for player_url in player_urls:
        conn = sqlite3.connect("../player_stats.db")
        cursor = conn.cursor()

        cursor.execute("SELECT data FROM player_rookie_season WHERE player_url = ?", player_url)
        result = cursor.fetchone()

        if result:
            rookie_season = result[0][2:4]
            seasons = []
            for i in range(2, -1, -1):
                try:
                    current_season = max(24 - int(rookie_season) - i, 0) # current_season - rookie_season - (2, 1, 0) = seasons played
                except ValueError:
                    current_season = 0
                seasons.append(str(current_season))
            seasons_played.append(seasons)
        else:
            seasons_played.append(['0', '0', '0']) # default to 0 seasons played if no data is found

        conn.close()

    return seasons_played


# NOTE: Game average will also include games from the previous season
def create_game_average(fantasy_points, num_games):
    """
    Creates a string containing game averages for fantasy points.

    Args:
        fantasy_points (str): Comma-separated string of fantasy points.
        num_games (int): Number of games to calculate the average over.

    Returns:
        str: A comma-separated string of game averages.
    """
    games = fantasy_points[:-2].split(', ')
    games = [0.0 if game == '' else float(game) for game in games]

    game_data = ''
    for i in range(len(games)):
        games_played = 0
        game_average = 0.0
        for j in range(i - num_games, i):
            if j >= 0:
                game_average += games[j]
                if games[j] != 0.0:
                    games_played += 1
        if games_played != 0:
            game_data += str(round(game_average / games_played, 2)) + ', '
        else:
            game_data += '0.0' + ', '
    return game_data


def create_fantasy_points():
    """
    Creates a list of fantasy points for each player.

    Args:
        filename (str): Path to the file containing weekly data.

    Returns:
        dict: A dictionary with keys as tuples (player_id, season) and values as fantasy points.
    """
    conn = sqlite3.connect("../player_stats.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM player_weekly_data")
    rows = cursor.fetchall()
    
    conn.close()

    data = []
    for row in rows:
        row_str = row[1].split('\n')
        data.append([''])
        for row in row_str:
            data.append(row.split(','))
    data.append([''])

    fantasy_points = {}
    player_fantasy_points = []
    season = 1
    player_id = 1

    # Ignore the first blank line. Data for first player starts at data[1]. 
    for line in data[1:]:
        if line[0] == '':
            season += 1
            fantasy_points[(player_id, season - 1)] = player_fantasy_points
            player_fantasy_points = []
            if season == 4:
                season = 1
                player_id += 1
        
        if line[0][:34] == 'Player does not have any game data':         
            num_games = 17
            for _  in range(num_games):
                player_fantasy_points.append('0.0')
        else: 
            if line[0] == 'Totals':
                pass
            else:
                try:
                    player_fantasy_points.append(line[17][1:])
                except IndexError: # bye week
                    pass
    return fantasy_points


def create_roster(team_ids):
    """
    Creates a list of players on each team.

    Args:
        team_ids (list): A list of dictionaries, each containing season-wise team IDs.

    Returns: roster (dict): A dictionary with keys as tuples (season, team_id) and values as lists of player_ids.
    """
    player_id = 1
    roster = {}
    season = 1
    for player in team_ids:
        for season in player:
            
            current_roster = roster.get((season, player[season]))  
            if current_roster is None:
                roster[(season, player[season])] = [player_id] # (season, team_id) : [player_id]
            else:
                roster[(season, player[season])].append(player_id)

            season += 1
        player_id += 1

    return roster 


def fantasy_points_list_to_string(fantasy_points):
        """
        Converts fantasy points from a list to a string.

        Args:
            fantasy_points (list): A list of fantasy points.

        Returns:
            str: A comma-separated string of fantasy points.
        """
        fantasy_points_str = ''
        for points in fantasy_points:
            if points == '-':
                fantasy_points_str += '0.0, '
            else:
                fantasy_points_str += points + ', '
        return fantasy_points_str  


def get_games_in_season(team_game_averages):
    """
    Gets the number of games in a season.
    Args: 
        team_game_averages (dict): A dictionary with keys as player_ids and values as game averages.
    Returns:
        int: The number of games in a season.
    """
    for average in team_game_averages.values():
        game_average = average[:-2].split(', ')
        return len(game_average)   


def calculate_team_game_averages(fantasy_points, players, season_id, skill_scores):
    """
    Calculates the 4 game averages for each player on the team.
    Args:
        players (list): A list of player_ids.
        season_id (int): The season.
    Returns:
        dict: A dictionary with keys as player_ids and values as game averages.
    """
    def set_game_average_as_skill_score(game_average, player_id, skill_scores):
        """
        When game average = 0.0, sets the game average as the player's skill score.
        Args:
            game_average (list): A list of game averages.
            player_id (int): The player_id.
            skill_scores (list): A direct access array of skill scores. i.e. skill_scores[0] = player id 1 
        Returns:
            str: A comma-separated string of game averages.
        """
        for week, average in enumerate(game_average):
            if float(average) == 0.0:
                game_average[week] = skill_scores[player_id - 1]
        
        game_average_str = ''        
        for average in game_average:
            game_average_str += str(average) + ', '
        
        return game_average_str       
         
    team_game_averages = {}
    for player_id in players:
        player_fantasy_points = fantasy_points[(player_id, season_id)]
        fantasy_points_str = fantasy_points_list_to_string(player_fantasy_points)
        game_average = create_game_average(fantasy_points_str, 4)
        game_average = set_game_average_as_skill_score(game_average[:-2].split(', '), player_id, skill_scores)
        team_game_averages[player_id] = game_average
    return team_game_averages


def check_if_player_missed_games(player_id, game_averages, fantasy_points, season_id):
    """
    Checks if a player missed a game and if True sets their game average for the week to 0.
    Args:
        team_game_averages (dict): A dictionary with keys as player_ids and values as game averages.
        fantasy_points (dict): A dictionary with keys as tuples (player_id, season) and values as fantasy points.
        season_id (int): The season.
    Modifies:
        team_game_averages so that weeks were a player didn't play are set to 0.
    Returns:
        dict: A dictionary with keys as player_ids and values as game averages.
    """
    for week, weekly_fantasy_points in enumerate(fantasy_points[(player_id, season_id)]):
        if weekly_fantasy_points == '-':
            game_averages[week] = '0.0'
    return game_averages


def verify_depth_chart_ranking(player, rank):
    """ 
    Verifies that the depth chart ranking is correct.
    Args:
        player (tuple): A tuple containing player_id, team_id, and game average.
        rank (int): The current depth chart rank.
    Returns:
        int: The current depth chart rank.
    """
    game_average = player[2]      
    if rank == 1:
        if game_average < 3.0:
            rank += 1
    
    # if rank == 2:
    #     if game_average < 1.0:
    #         rank += 1
    return rank


def check_for_players_tied_on_depth_chart(game_averages_rankings, player_id, rank):
    """
    Checks if there are players tied on the depth chart.
    Args:
        game_averages_rankings (list): A list of tuples containing player_ids, team_ids, and game averages.
        players_on_team (int): The number of players on the team.
        rank (int): The current depth chart rank.
    Returns:
        int: The current depth chart rank.
    """
    tolerance = 1
    if player_id - 1 >= 0: 
        if game_averages_rankings[player_id - 1][2] - game_averages_rankings[player_id][2] < tolerance: 
            rank -= .5
        elif game_averages_rankings[player_id - 1][2] - game_averages_rankings[player_id][2] < tolerance + 2: 
            rank -= .25
    if player_id + 1 < len(game_averages_rankings):
        if game_averages_rankings[player_id][2] - game_averages_rankings[player_id + 1][2] < tolerance:
            rank += .5
        elif game_averages_rankings[player_id][2] - game_averages_rankings[player_id + 1][2] < tolerance + 2:
            rank += .25
    return rank
 
  
def create_depth_chart(rosters, fantasy_points, skill_scores):
    """
    Creates a weekly depth chart ranking for each player.

    Args:
        rosters (dict): A dictionary with keys as tuples (season, team_id) and values as lists of player_ids.
        fantasy_points (dict): A dictionary with keys as tuples (player_id, season) and values as fantasy points.
    
    Returns:
        dict: A dictionary with keys as tuples (player_id, season, team_id) and values as lists of depth chart rankings.
    """
    depth_chart = {}
    for team in rosters.items():
        team_id = team[0][1]
        season_id = team[0][0]
        players = team[1]
        
        team_game_averages = calculate_team_game_averages(fantasy_points, players, season_id, skill_scores)
         
        for week in range(get_games_in_season(team_game_averages)):
            game_averages_rankings = []
            for player_game_averages in team_game_averages.items():
                game_averages = check_if_player_missed_games(player_game_averages[0], player_game_averages[1][:-2].split(', '), 
                                                             fantasy_points, season_id)
                try:
                    game_averages_rankings.append((player_game_averages[0], team_id, float(game_averages[week])))
                except IndexError:
                    game_averages_rankings.append((player_game_averages[0], team_id, 0.0))
            # rank players on the depth chart by highest to lowest 3 game averages    
            game_averages_rankings.sort(key=lambda x: x[2], reverse=True)
            
            rank = 1 
            for player in game_averages_rankings:
                rank = verify_depth_chart_ranking(player, rank)
                if week == 0:
                    depth_chart[(player[0], season_id)] = [rank] # (player_id, season, team_id) : [rank]
                else:
                    depth_chart[(player[0], season_id)].append(rank)  
                rank += 1      

    return depth_chart