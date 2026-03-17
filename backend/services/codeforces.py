import httpx
import asyncio
import time

# Codeforces API base URL
CF_API_BASE = "https://codeforces.com/api"

# In-memory cache for contest list (refreshed every 24 hours)
_contest_cache = {"data": {}, "fetched_at": 0}
CONTEST_CACHE_TTL = 86400  # 24 hours in seconds

async def fetch_user_info(handle: str):
    """Fetches basic profile info and current/max ratings."""
    url = f"{CF_API_BASE}/user.info?handles={handle}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        
        if data["status"] == "OK":
            return data["result"][0]
        else:
            raise Exception(f"Codeforces API Error: {data.get('comment')}")

# async def fetch_user_submissions(handle: str):
#     """Fetches all raw submissions for the user."""
#     url = f"{CF_API_BASE}/user.status?handle={handle}"
#     async with httpx.AsyncClient() as client:
#         response = await client.get(url)
#         data = response.json()
        
#         if data["status"] == "OK":
#             return data["result"]
#         else:
#             raise Exception(f"Codeforces API Error: {data.get('comment')}")
import httpx
import asyncio

CF_API = "https://codeforces.com/api"


async def fetch_user_submissions(handle: str):

    url = f"{CF_API}/user.status?handle={handle}"

    retries = 3

    for attempt in range(retries):

        try:

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)

            data = response.json()

            if data["status"] != "OK":
                raise Exception("Codeforces API error")

            return data["result"]

        except httpx.ReadTimeout:

            print(f"Timeout for {handle}, retrying ({attempt+1}/{retries})")

            await asyncio.sleep(2)

    print(f"Failed fetching {handle}")

    return []


async def fetch_user_contests(handle: str):
    """Fetches rating changes and contest participation history."""
    url = f"{CF_API_BASE}/user.rating?handle={handle}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        
        if data["status"] == "OK":
            return data["result"]
        else:
            raise Exception(f"Codeforces API Error: {data.get('comment')}")


async def fetch_user_rating_changes(handle: str):
    """
    Fetches rating change history. Returns list of dicts with:
    contestId, contestName, oldRating, newRating, ratingChange
    """
    url = f"{CF_API}/user.rating?handle={handle}"
    retries = 3

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)

            data = response.json()

            if data["status"] != "OK":
                raise Exception("Codeforces API error")

            results = []
            for entry in data["result"]:
                results.append({
                    "contestId": entry["contestId"],
                    "contestName": entry.get("contestName", "Unknown"),
                    "oldRating": entry.get("oldRating", 0),
                    "newRating": entry.get("newRating", 0),
                    "ratingChange": entry.get("newRating", 0) - entry.get("oldRating", 0),
                    "updateTime": entry.get("ratingUpdateTimeSeconds", 0)
                })
            return results

        except httpx.ReadTimeout:
            print(f"Timeout fetching rating for {handle}, retrying ({attempt+1}/{retries})")
            await asyncio.sleep(2)

    print(f"Failed fetching rating changes for {handle}")
    return []


async def fetch_contest_list() -> dict:
    """
    Fetches the full contest list from Codeforces API.
    Returns a mapping: { contestId: startTimeSeconds (UNIX timestamp) }
    Results are cached in memory for 24 hours.
    """
    # Return cached data if still fresh
    if time.time() - _contest_cache["fetched_at"] < CONTEST_CACHE_TTL and _contest_cache["data"]:
        return _contest_cache["data"]

    url = f"{CF_API}/contest.list"
    retries = 3

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)

            data = response.json()

            if data["status"] != "OK":
                raise Exception("Codeforces API error fetching contest list")

            contest_start_map = {}
            for contest in data["result"]:
                cid = contest.get("id")
                start = contest.get("startTimeSeconds")
                if cid is not None and start is not None:
                    contest_start_map[cid] = start

            # Update cache
            _contest_cache["data"] = contest_start_map
            _contest_cache["fetched_at"] = time.time()
            return contest_start_map

        except httpx.ReadTimeout:
            print(f"Timeout fetching contest list, retrying ({attempt+1}/{retries})")
            await asyncio.sleep(2)

    print("Failed fetching contest list")
    return _contest_cache["data"] or {}