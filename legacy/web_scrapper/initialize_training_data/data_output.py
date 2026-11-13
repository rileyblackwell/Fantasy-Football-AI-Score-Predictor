def create_data_csv(player_data, filename='../../fantasy_football/data.csv'):
    """
    Creates a text file with player data.

    Args:
        player_data (list): List of player data lines, where each line is a string.
        filename (str): The name of the output text file (default is 'data.txt').

    Writes:
        A text file with player data.

    """
    with open(filename, 'w') as output:
        player_data = [line.split() for line in player_data]
        for line in player_data:
            for item in line:
                output.write(item + ' ')
            output.write('\n')