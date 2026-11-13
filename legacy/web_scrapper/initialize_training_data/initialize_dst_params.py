def initialize_dst_rankings_dictionary():
    """
    Creates a dictionary of DST (Defense/Special Teams) rankings for each season and week.

    Returns:
        dict: A dictionary with keys as tuples (season, week, team_name) and values as rankings.
    """
    with open('../dst_id_and_rankings/dst_rankings.out') as f:
        data = f.readlines()
        data = [line.strip() for line in data]
        data = [line.split(',') for line in data]

    dst_rankings = {}
    week, season = 1, 1
    for line in data:
        if line[0] == '':
            week += 1
        elif line[0] == 'end of season':
            season += 1
            week = 1
        else:
            dst_rankings[(season, week, line[1][1:])] = line[0]
    return dst_rankings


def initialize_dst_id_dictionary():
    """
    Creates a dictionary of DST (Defense/Special Teams) names their corresponding IDs.

    Returns:
        dict: A dictionary with keys as DST names and values as IDs.
    """
    with open('../dst_id_and_rankings/dst_id.out') as f:
        data = f.readlines()
        data = [line.strip() for line in data]
        data = [line.split(',') for line in data]

    dst_ids = {}
    for line in data:
        dst_ids[line[1][1:]] = line[0]
    return dst_ids