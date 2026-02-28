import httpx
import asyncio

# Codeforces API base URL
CF_API_BASE = "https://codeforces.com/api"

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

async def fetch_user_submissions(handle: str):
    """Fetches all raw submissions for the user."""
    url = f"{CF_API_BASE}/user.status?handle={handle}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        
        if data["status"] == "OK":
            return data["result"]
        else:
            raise Exception(f"Codeforces API Error: {data.get('comment')}")

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