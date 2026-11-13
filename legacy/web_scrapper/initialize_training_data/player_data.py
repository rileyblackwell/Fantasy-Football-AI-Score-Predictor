from initialize_params import create_game_average

from database import (
    read_player_weekly_data_from_db,
    read_player_position_from_db,
)
from player_data_utils import (
    initialize_params,
    add_player_data,
    player_missed_season,
    process_player_data,
)

def write_player_urls_to_file(player_urls):
    with open('../../fantasy_football/players.txt', 'w') as f:
        for player_url in player_urls:
            f.write(player_url[0] + '\n')

def initialize_player_data(num_params):
    params = initialize_params(num_params)
    player_data = []
    return params, player_data

def process_player_season_data(data, player, season, params, dst_rankings, dst_ids, 
                               skill_scores, seasons_played, teams_ids, position):
    week = 1
    for row in data[1:]:
        if row[0] == '':
            week = 1
            season += 1
            if season == 4:
                params = update_game_averages(params)
                return params
            continue

        if row[0][:34] == 'Player does not have any game data':
            params = player_missed_season(params)
        else:
            dst = row[1][1:].replace('@ ', '').replace('vs. ', '')
            try:
                dst_rank = dst_rankings[(season, week, dst)]
                dst_id = dst_ids[dst]
            except KeyError:
                continue

            params = update_params(params, row, week, season, player, dst_rank, dst_id, 
                                   skill_scores, seasons_played, teams_ids, position)
            week += 1
    return params

def update_params(params, row, week, season, player, dst_rank, dst_id, 
                  skill_scores, seasons_played, teams_ids, position):
    params[2] += f'{week}, '
    params[1] += f'{season}, '
    fantasy_points = get_fantasy_points(row)
    params[5] += f'{get_skill_score(skill_scores, player)}, '
    params[6] += f'{get_seasons_played(seasons_played, player, season)}, '
    params[7] += f'{player + 1}, '
    params[15] += f'{get_team_id(teams_ids, player, season)}, '
    params[16] += f'{position}, '
    
    if fantasy_points == '-' or fantasy_points == '0.0':
        params = handle_missing_fantasy_points(params)
    else:
        params[0] += fantasy_points + ', '
        params[3] += dst_rank + ', '
        params[4] += dst_id + ', '
    return params

def update_game_averages(params):
    for i in range(3, 10):
        params[i + 5] = create_game_average(params[0], i)
    return params

def get_fantasy_points(row):
    if len(row) == 20:
        return row[17][1:]
    elif len(row) == 23: # qb has 3 more columns
        return row[20][1:]
    else:
        return '-'

def get_skill_score(skill_scores, player):
    try:
        return skill_scores[player]
    except IndexError:
        return 0

def get_seasons_played(seasons_played, player, season):
    try:
        return seasons_played[player][season - 1]
    except IndexError:
        return 0

def get_team_id(teams_ids, player, season):
    try:
        return teams_ids[player][season]
    except (KeyError, IndexError):
        return 0

def get_depth_chart(depth_chart, player, season, week):
    try:
        return depth_chart[(player + 1, season)][week - 1]
    except KeyError:
        return 0

def handle_missing_fantasy_points(params):
    for i in (0, 3, 4):
        params[i] += '0, '
    return params

def get_player_position(player_url):
    position = read_player_position_from_db(player_url)
    if position == 'rb':
        return 1.0
    elif position == 'wr':
        return 2.0
    elif position == 'te':
        return 3.0
    elif position == 'qb':
        return 4.0
    else:
        return 0.0

def create_player_data(player_urls, dst_rankings, dst_ids, skill_scores, 
                       seasons_played, teams_ids, num_params):
    
    params, player_data = initialize_player_data(num_params)
    write_player_urls_to_file(player_urls)
    player = 0
    season = 1
    for player_url in player_urls:
        rows = read_player_weekly_data_from_db(player_url[0])
        data = process_player_data(rows)
        params = process_player_season_data(data, player, season, params, dst_rankings, 
                                            dst_ids, skill_scores, seasons_played, 
                                            teams_ids, get_player_position(player_url[0]))
        player_data = add_player_data(player_data, params)
        params = initialize_params(num_params)
        player += 1
        season = 1
    return player_data