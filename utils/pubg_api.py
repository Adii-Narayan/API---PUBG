import requests

def fetch_player_matches(username):
    """Fetch match data for a player using their username."""
    player_id_url = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={username}"
    headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJkYTMxMzVhMC1iNWY3LTAxM2QtZGMwZS0wYWY2MzhlNGMzOTIiLCJpc3MiOiJnYW1lbG9ja2VyIiwiaWF0IjoxNzM3MDA0OTcwLCJwdWIiOiJibHVlaG9sZSIsInRpdGxlIjoicHViZyIsImFwcCI6ImNhdG9mZndlYjMifQ.m-Mk0Ln1RMNQcr8kU_P2lr7gHIyRc8z90bzRSXGcU-4",  # Replace with your actual API key
        "Accept": "application/vnd.api+json"
    }

    try:
        response = requests.get(player_id_url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching player data: {response.text}")
            return None

        player_data = response.json()
        if not player_data.get("data"):
            print("No player found for the given username.")
            return None

        player = player_data["data"][0]
        matches = player.get("relationships", {}).get("matches", {}).get("data", [])
        match_details = []

        for match in matches:
            match_id = match["id"]
            match_url = f"https://api.pubg.com/shards/steam/matches/{match_id}"
            match_response = requests.get(match_url, headers=headers)

            if match_response.status_code == 200:
                match_data = match_response.json()
                attributes = match_data.get("data", {}).get("attributes", {})
                match_details.append({
                    "id": match_id,
                    "created_at": attributes.get("createdAt"),
                    "mode": attributes.get("gameMode"),
                    "map": attributes.get("mapName")
                })
            else:
                print(f"Failed to fetch match details for ID {match_id}")

        return match_details
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
