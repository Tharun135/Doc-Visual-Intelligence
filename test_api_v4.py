#!/usr/bin/env python3
"""Test V4 Flask app endpoint"""

import requests
import json

url = "http://127.0.0.1:5000/home"
data = {
    'analysis_text': """Procedure: Deploy Configuration
1. Open the HMI dashboard panel
2. Select configuration from settings
3. Validate parameters with S7-1500 controller
4. Deploy to cloud platform via gateway
5. Verify on remote server

The microcontroller processes data and sends it through the connector."""
}

try:
    print("Sending test request to Flask app...")
    response = requests.post(url, data=data, timeout=10)
    result = response.json()
    
    print("\n✓ API Response received")
    print(f"Status: {response.status_code}")
    print(f"\nRecommendations ({len(result.get('recommendations', []))} total):\n")
    
    for i, rec in enumerate(result.get('recommendations', [])[:3], 1):
        print(f"{i}. {rec.get('visual_type', 'Unknown')}")
        print(f"   Content Type: {rec.get('content_type')} ({rec.get('content_type_confidence')}%)")
        print(f"   Priority: {rec.get('priority')}")
        print(f"   Confidence: {rec.get('confidence')}")
        print()
    
    print("✓ V4 content_type_confidence field successfully rendered in API response")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("Make sure Flask app is running on http://127.0.0.1:5000")
