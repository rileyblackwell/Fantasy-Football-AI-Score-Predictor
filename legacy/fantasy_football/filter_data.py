import csv

def group_player_data(file_name):
    with open(file_name, 'r') as file:
        reader = csv.reader(file)
        data = list(reader)
    
    player_data = []
    for i in range(0, len(data), 17):
        player_data.append(data[i:i+17])
    
    return player_data

def check_zero_player(player_data):
    for row in player_data:
        for value in row:
            try:
                if float(value) != 0.0:
                    return False
            except ValueError:
                raise ValueError(f"Unable to convert value '{value}' to float")
    return True

def remove_zero_players(file_name):
    player_data = group_player_data(file_name)
    zero_players_removed = 0
    non_zero_players = []
    
    for player in player_data:
        if check_zero_player(player):
            zero_players_removed += 1
        else:
            non_zero_players.append(player)
    
    with open(file_name, 'w', newline='') as file:
        writer = csv.writer(file)
        for player in non_zero_players:
            writer.writerows(player)
    
    return zero_players_removed

def main():
    file_name = 'data.csv'
    print("Removing zero players from", file_name)
    try:
        zero_players_removed = remove_zero_players(file_name)
        print(f"Done! Removed {zero_players_removed} players with no data.")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()