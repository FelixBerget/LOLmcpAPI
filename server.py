from typing import Any
import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("riot")

# Constants
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

REGIONAL_URLS = {
    "na": "https://americas.api.riotgames.com",
    "euw": "https://europe.api.riotgames.com",
    "eune": "https://europe.api.riotgames.com",
    "kr": "https://asia.api.riotgames.com",
    "jp": "https://asia.api.riotgames.com",
}

PLATFORM_URLS = {
    "na": "https://na1.api.riotgames.com",
    "euw": "https://euw1.api.riotgames.com",
    "eune": "https://eun1.api.riotgames.com",
    "kr": "https://kr.api.riotgames.com",
    "jp": "https://jp1.api.riotgames.com",
}

async def riot_req(url: str) ->dict[str,Any]|None:
    headers = {"X-Riot-Token": RIOT_API_KEY}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url,headers=headers,timeout=30.0)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                return {"error": True, "message":f"Rate limit hit. Retry after {retry_after} seconds."}
            elif response.status_code == 404:
                return {"error":True,"message":"Resource not found"}
            elif response.status_code == 403:
                return {"error": True, "message": "Invalid or expired API key."}
            elif response.status_code == 401:
                return {"error": True, "message": "Unauthorized. Check your API key."}

            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            return {"error":True,"message":"Request timeout"}
        except httpx.RequestError as e:
            return {"error":True,"message":f"Network error {str(e)}"}
            
        
@mcp.tool()
async def get_player_id(region: str,name: str, tag_line: str) -> str:
    """
    Remember urls are always in lowercase
    Tries to find the id of a player by looking up their name and tag.
    """
    url = f"{REGIONAL_URLS[region]}/riot/account/v1/accounts/by-riot-id/{name}/{tag_line}"
    data = await riot_req(url)
    if not data:
        return "Found no account with that name in the server"
    if data.get("error"):
        return data["message"]
    return f"Name:{data['gameName']}#{data['tagLine']} PUUID: {data['puuid']}"

@mcp.tool()
async def get_champion_masteries(uuid: str, region: str) -> str:
    """
    Remember urls are always in lowercase
    Tries to find masteries of champions on account based on id and region
    """
    url = f"{PLATFORM_URLS[region]}/lol/champion-mastery/v4/champion-masteries/by-puuid/{uuid}"
    data = await riot_req(url)
    if isinstance(data, dict) and data.get("error"):
        return data["message"]
    if not data:
        return "Account does not exist on region"
    
    results = []
    for mastery in data[:10]:  # top 10 so we don't flood Claude
        results.append(f"Champion {mastery['championId']}: Level {mastery['championLevel']} - {mastery['championPoints']} pts")
    
    return "\n".join(results)

@mcp.tool()
async def get_newest_matches(region:str, uuid:str, numberOfGames: int) -> str:
    """
    Remember urls are always in lowercase
    Tries to find newest matches for player based on ID
    """
    url = f"{REGIONAL_URLS[region]}/lol/match/v5/matches/by-puuid/{uuid}/ids?count={numberOfGames}"
    data = await riot_req(url)
    if isinstance(data, dict) and data.get("error"):
        return data["message"]
    if not data:
        return "Account has no matches or does not exist"
    results = []
    for match_id in data[:numberOfGames]:
        results.append(match_id)
    return "\n".join(results)

@mcp.tool()
async def get_match_by_id(region: str,match_id:str):
    """
    Remember urls are always in lowercase usernames and champion names to refer to players
    Finds match by ID and finds stats
    """
    url = f"{REGIONAL_URLS[region]}/lol/match/v5/matches/{match_id}"
    data = await riot_req(url)
    if not data:
        return "Match does not exist"
    if data.get("error"):
        return data["message"]
    info = data["info"]
    results = [f"Mode: {info['gameMode']} - Duration: {info['gameDuration'] // 60}min"]

    for p in info["participants"]:
        results.append(
            f"{p['riotIdGameName']} - {p['championName']} - "
            f"{p['kills']}/{p['deaths']}/{p['assists']} time spent dead{p['totalTimeSpentDead']} - "
            f"{'Win' if p['win'] else 'Loss'} -{p['timePlayed']}"
        )
    return "\n".join(results)

@mcp.tool()
async def get_match_timeline_by_id(region: str,match_id:str):
    """
    Remember urls are always in lowercase use usernames and champion names to refer to players
    Finds match timeline by ID, returning key events (kills, building destroys, elite monsters, items and level ups)
    """
    url = f"{REGIONAL_URLS[region]}/lol/match/v5/matches/{match_id}/timeline"
    data = await riot_req(url)
    if not data:
        return "Match does not exist"
    if data.get("error"):
        return data["message"]

    info = data.get("info", {})
    frames = info.get("frames", [])
    participant_map = {}
    for p in info.get("participants"):
        pid=p["participantId"]
        participant_map[pid]={
            "name": p.get("riotIdGameName") or p.get("summonerName") or f"Player {pid}",
            "champion": p.get("championName", "Unknown")
        }
    def get_label(pid):
        p = participant_map.get(pid,{})
        return f"{p.get('name', '?')}({p.get('champion','?')})"

    results = [f"Match: {match_id} - Frame interval: {info.get('frameInterval', 0) // 1000}s"]

    for frame in frames:
        timestamp = frame.get("timestamp", 0) // 1000
        minutes = timestamp // 60
        seconds = timestamp % 60
        for event in frame.get("events", []):
            etype = event.get("type")
            if etype == "CHAMPION_KILL":
                killer = event.get("killerId", 0)
                victim = event.get("victimId", 0)
                assists = event.get("assistingParticipantIds", [])
                results.append(
                    f"[{minutes:02d}:{seconds:02d}] KILL - Player {get_label(killer)} killed Player {get_label(victim)} "
                    f"(assists: {assists})"
                )
            elif etype == "BUILDING_KILL":
                team = event.get("teamId", 0)
                team_map = {100: "Blue Team", 200: "Red Team"}
                building = event.get("buildingType", "")
                lane = event.get("laneType", "")
                results.append(
                    f"[{minutes:02d}:{seconds:02d}] BUILDING - Team {team_map[team]} lost {building} ({lane})"
                )
            elif etype == "ELITE_MONSTER_KILL":
                killer = event.get("killerId", 0)
                monster = event.get("monsterType", "")
                subtype = event.get("monsterSubType", "")
                results.append(
                    f"[{minutes:02d}:{seconds:02d}] MONSTER - Player {get_label(killer)} killed {monster} {subtype}"
                )
            elif etype == "ITEM_PURCHASED":
                participant = event.get("participantId", 0)
                item_id = event.get("itemId", 0)
                results.append(
                    f"[{minutes:02d}:{seconds:02d}] ITEM - Player {get_label(participant)} purchased item {item_id}"
                )
            elif etype == "SKILL_LEVEL_UP":
                participant = event.get("participantId", 0)
                skill_slot = event.get("skillSlot",0)
                slot_map = {1: "Q",2: "W", 3:"E", 4:"R"}
                skill_name = slot_map.get(skill_slot,str(skill_slot))
                results.append(
                    f"[{minutes:02d}:{seconds:02d}] SKILL - Player {get_label(participant)} leveled up {skill_name}"
                )

    return "\n".join(results)


if __name__ == "__main__":
    mcp.run(transport="stdio")

