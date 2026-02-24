from nba_api.stats.endpoints import commonallplayers
import pandas as pd

def test():
    print("Testing CommonAllPlayers...")
    try:
        # get all players for current season
        df = commonallplayers.CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
        print("Total players found:", len(df))
        print("Columns:", df.columns.tolist())
        print("Head:")
        print(df.head())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
