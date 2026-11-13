"""Synthetic NFL data for tests: 4 teams, one player per position per team, a few seasons."""

import numpy as np
import pandas as pd

from predictor.models import POSITIONS, Game, Player, WeeklyStat

TEAMS = ["AAA", "BBB", "CCC", "DDD"]
# Week-by-week pairings: (home, away)
PAIRINGS = [[("AAA", "BBB"), ("CCC", "DDD")], [("AAA", "CCC"), ("BBB", "DDD")], [("AAA", "DDD"), ("BBB", "CCC")]]


def schedule(seasons, weeks, played_through=None):
    """played_through: (season, week) after which games have no score yet."""
    rows = []
    for season in seasons:
        for week in range(1, weeks + 1):
            for home, away in PAIRINGS[(week - 1) % len(PAIRINGS)]:
                final = played_through is None or (season, week) <= played_through
                rows.append(
                    {
                        "game_id": f"{season}_{week:02d}_{away}_{home}",
                        "season": season,
                        "week": week,
                        "gameday": None,
                        "home_team": home,
                        "away_team": away,
                        "home_score": 24 if final else None,
                        "away_score": 20 if final else None,
                        "spread_line": 3.0,
                        "total_line": 45.0,
                    }
                )
    return pd.DataFrame(rows)


def weekly_stats(games: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = {"QB": 18, "RB": 12, "WR": 11, "TE": 7}
    rows = []
    for g in games[games["home_score"].notna()].itertuples():
        for team, opp in [(g.home_team, g.away_team), (g.away_team, g.home_team)]:
            for pos in POSITIONS:
                ppr = max(0.0, base[pos] + TEAMS.index(team) + rng.normal(0, 3))
                rec = 0 if pos == "QB" else int(rng.integers(1, 8))
                rows.append(
                    {
                        "player_id": f"00-{team}-{pos}",
                        "name": f"{team} {pos}",
                        "position": pos,
                        "headshot_url": "",
                        "season": g.season,
                        "week": g.week,
                        "team": team,
                        "opponent": opp,
                        "completions": 20 if pos == "QB" else 0,
                        "attempts": 30 if pos == "QB" else 0,
                        "passing_yards": 250 if pos == "QB" else 0,
                        "passing_tds": 2 if pos == "QB" else 0,
                        "interceptions": 1 if pos == "QB" else 0,
                        "carries": 15 if pos == "RB" else 1,
                        "rushing_yards": 60 if pos == "RB" else 3,
                        "rushing_tds": 0,
                        "targets": rec + 2,
                        "receptions": rec,
                        "receiving_yards": rec * 10,
                        "receiving_tds": 0,
                        "target_share": 0.1 * rec / 4,
                        "fantasy_points_std": round(ppr - rec, 2),
                        "fantasy_points_ppr": round(ppr, 2),
                    }
                )
    return pd.DataFrame(rows)


def populate_db(seasons=(2023, 2024, 2025), weeks=6, played_through=(2025, 3)):
    """Fill the test database; returns (games, stats) frames."""
    from predictor.ingest import store_schedule, store_weekly_stats

    games = schedule(seasons, weeks, played_through)
    stats = weekly_stats(games)
    store_weekly_stats(stats, list(seasons))
    store_schedule(games)
    Player.objects.update(roster_status="ACT")
    assert WeeklyStat.objects.exists() and Game.objects.exists()
    return games, stats
