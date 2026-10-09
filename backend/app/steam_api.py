"""Read optional public Steam account details through the server-side API key."""

from urllib.parse import urlsplit

import httpx

STEAM_PROFILE_API = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"


def steam_profile(steam_id64, api_key, client):
    # OpenID establishes identity even without the optional Steam Web API key.
    profile = {
        "steam_id64": steam_id64,
        "display_name": steam_id64,
        "avatar_url": None,
        "profile_url": f"https://steamcommunity.com/profiles/{steam_id64}",
    }
    if not api_key:
        return profile
    try:
        response = client.get(STEAM_PROFILE_API, params={"key": api_key, "steamids": steam_id64})
        response.raise_for_status()
        players = response.json()["response"]["players"]
        player = next(p for p in players if str(p.get("steamid")) == steam_id64)
        name = player.get("personaname")
        if isinstance(name, str) and name.strip():
            profile["display_name"] = name[:128]
        avatar = player.get("avatarfull")
        if isinstance(avatar, str):
            url = urlsplit(avatar)
            if url.scheme == "https" and url.hostname and not url.username and not url.password:
                profile["avatar_url"] = avatar
    except (httpx.HTTPError, ValueError, TypeError, KeyError, StopIteration):
        # Failure to fetch a nickname cannot invalidate a verified Steam identity.
        pass
    return profile
