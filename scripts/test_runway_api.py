#!/usr/bin/env python3
"""
Test Runway API connectivity
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not RUNWAY_API_KEY:
    print("❌ RUNWAY_API_KEY not set in .env")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {RUNWAY_API_KEY}",
    "X-Runway-Version": "2024-11-06"
}

# Test API connectivity
try:
    response = requests.get(
        "https://api.runwayml.com/v1/tasks",  # List recent tasks
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:
        print("✅ Runway API connection successful")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Runway API error: {response.status_code}")
        print(response.text)
        sys.exit(1)

except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
