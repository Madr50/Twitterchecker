import asyncio
import aiohttp
import argparse
import re
from dateutil import parser
import time

import urllib.parse
TOKEN = urllib.parse.unquote("AAAAAAAAAAAAAAAAAAAAALot%2BgEAAAAA%2FgqUMY5cY%2B8xyTeBtu55l%2BLMxlw%3Dp1fc0HPV1OKY13rSCz7qL5lDPlhPrR7qjtQIRG1vX37hl5U3MQ")
INACTIVE_THRESHOLD_YEAR = 2018
BATCH_SIZE = 100 # Max usernames per API request for /2/users/by
CONCURRENT_BATCHES = 5 # Number of concurrent API requests

async def read_usernames(file_path):
    try:
        with open(file_path, 'r') as f:
            raw_usernames = {line.strip() for line in f}
    except FileNotFoundError:
        print(f"Error: No such file '{file_path}'")
        exit(1)

    pattern = r"^[A-Za-z0-9_]{4}$"
    valid_usernames = []
    invalid_count = 0
    for username in raw_usernames:
        if re.match(pattern, username):
            valid_usernames.append(username)
        else:
            invalid_count += 1
    if invalid_count > 0:
        print(f"\033[1;33mWarning:\033[0m Skipped {invalid_count} usernames due to invalid format (not 4 characters or invalid characters).")
    return valid_usernames

async def fetch_batch(session, usernames_chunk, token):
    results = []
    try:
        async with session.get(
            url="https://api.twitter.com/2/users/by",
            headers={
                "Authorization": f"Bearer {token}",
            },
            params={
                "usernames": ",".join(usernames_chunk),
                "user.fields": "id,created_at,name,username,verified,pinned_tweet_id,public_metrics",
            },
            timeout=aiohttp.ClientTimeout(total=30) # 30 seconds timeout for each request
        ) as response:
            data = await response.json()

            if response.status != 200:
                error_detail = data.get('detail', str(data))
                for username in usernames_chunk:
                    results.append({"username": username, "status": f"API_ERROR: {error_detail} (Status: {response.status})"})
                return results

            if "errors" in data:
                for error in data["errors"]:
                    username = error.get("resource_id", "Unknown")
                    if "suspended" in error.get("detail", ""):
                        results.append({"username": username, "status": "SUSPENDED"})
                    elif "Could not find user" in error.get("detail", ""):
                        results.append({"username": username, "status": "AVAILABLE"})
                    else:
                        results.append({"username": username, "status": f"API_ERROR: {error.get('detail', str(error))}"})

            if "data" in data:
                for user in data["data"]:
                    username = user["username"]
                    user_created_year = parser.parse(user["created_at"]).year

                    is_active = (
                        user_created_year > INACTIVE_THRESHOLD_YEAR
                        or user.get("verified", False)
                        or "pinned_tweet_id" in user
                        or user.get("public_metrics", {}).get("tweet_count", 0) > 0
                    )
                    results.append({"username": username, "status": "TAKEN_ACTIVE" if is_active else "TAKEN_INACTIVE"})

    except aiohttp.ClientError as e:
        for username in usernames_chunk:
            results.append({"username": username, "status": f"NETWORK_ERROR: {e}"})
    except asyncio.TimeoutError:
        for username in usernames_chunk:
            results.append({"username": username, "status": "TIMEOUT_ERROR"})
    return results

async def main():
    arg_parser = argparse.ArgumentParser(description="Check Twitter username availability and activity using async API calls.")
    arg_parser.add_argument(
        "username_file",
        help="Path to a text file containing a list of 4-character usernames to check.",
    )
    args = arg_parser.parse_args()

    print("\033[1;34mReading usernames from file...\033[0m")
    usernames_to_check = await read_usernames(args.username_file)
    print(f"\033[1;32mFound {len(usernames_to_check)} valid 4-character usernames to process.\033[0m")

    if not TOKEN or TOKEN == "REPLACE_THIS_WITH_YOUR_BEARER_TOKEN":
        print("\033[1;31mError: Please replace 'REPLACE_THIS_WITH_YOUR_BEARER_TOKEN' with your actual Twitter Bearer Token.\033[0m")
        exit(1)

    start_time = time.time()

    available_usernames = []
    taken_active_usernames = []
    taken_inactive_usernames = []
    suspended_usernames = []
    api_errors = []
    network_errors = []
    timeout_errors = []

    print("\033[1;34mChecking usernames via Twitter API v2 (asynchronously)...\033[0m")
    username_chunks = [usernames_to_check[i : i + BATCH_SIZE] for i in range(0, len(usernames_to_check), BATCH_SIZE)]

    async with aiohttp.ClientSession() as session:
        # Create a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(CONCURRENT_BATCHES)

        async def bounded_fetch_batch(chunk):
            async with semaphore:
                return await fetch_batch(session, chunk, TOKEN)

        tasks = [bounded_fetch_batch(chunk) for chunk in username_chunks]
        all_results = await asyncio.gather(*tasks)

    for chunk_results in all_results:
        for result in chunk_results:
            status = result["status"]
            username = result["username"]
            if status == "AVAILABLE":
                available_usernames.append(username)
            elif status == "TAKEN_ACTIVE":
                taken_active_usernames.append(username)
            elif status == "TAKEN_INACTIVE":
                taken_inactive_usernames.append(username)
            elif status == "SUSPENDED":
                suspended_usernames.append(username)
            elif status.startswith("API_ERROR"):
                api_errors.append(f"{username}: {status}")
            elif status.startswith("NETWORK_ERROR"):
                network_errors.append(f"{username}: {status}")
            elif status == "TIMEOUT_ERROR":
                timeout_errors.append(username)

    end_time = time.time()
    duration = end_time - start_time

    print("\n\033[1;34m--- Results Summary ---\033[0m")
    print(f"\033[1;32mAVAILABLE:\033[0m {len(available_usernames)} usernames")
    for u in available_usernames:
        print(f"  {u}")

    print(f"\033[1;31mTAKEN (ACTIVE):\033[0m {len(taken_active_usernames)} usernames")
    # for u in taken_active_usernames:
    #     print(f"  {u}")

    print(f"\033[1;33mTAKEN (INACTIVE):\033[0m {len(taken_inactive_usernames)} usernames")
    # for u in taken_inactive_usernames:
    #     print(f"  {u}")

    print(f"\033[1;31mSUSPENDED:\033[0m {len(suspended_usernames)} usernames")
    # for u in suspended_usernames:
    #     print(f"  {u}")

    if api_errors:
        print(f"\033[1;31mAPI Errors:\033[0m {len(api_errors)} occurrences")
        # for err in api_errors:
        #     print(f"  {err}")

    if network_errors:
        print(f"\033[1;31mNetwork Errors:\033[0m {len(network_errors)} occurrences")
        # for err in network_errors:
        #     print(f"  {err}")

    if timeout_errors:
        print(f"\033[1;31mTimeout Errors:\033[0m {len(timeout_errors)} occurrences")
        # for err in timeout_errors:
        #     print(f"  {err}")

    print(f"\033[1;36mTotal processing time: {duration:.2f} seconds\033[0m")
    print("\033[1;34m--- End of Summary ---\033[0m")


if __name__ == "__main__":
    asyncio.run(main())
