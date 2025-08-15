#!/usr/bin/env python3
"""
This script generates the FIREBASE_CONFIG environment variable 
for deployment platforms like Railway and Render.
"""

import json
import os

def generate_firebase_config():
    cred_path = os.path.join(os.path.dirname(__file__), "credentials", "bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json")
    
    if not os.path.exists(cred_path):
        print(f"❌ Credentials file not found at: {cred_path}")
        return None
    
    try:
        with open(cred_path, 'r') as f:
            firebase_config = json.load(f)
        
        # Convert to a compact JSON string
        config_string = json.dumps(firebase_config, separators=(',', ':'))
        
        print("✅ Firebase configuration generated successfully!")
        print("\n" + "="*80)
        print("COPY THE VALUE BELOW AND SET IT AS 'FIREBASE_CONFIG' ENVIRONMENT VARIABLE")
        print("="*80)
        print(config_string)
        print("="*80)
        print("\nInstructions:")
        print("1. Copy the JSON string above (the entire line)")
        print("2. In your deployment platform (Railway/Render):")
        print("   - Go to Environment Variables section")
        print("   - Add a new variable named: FIREBASE_CONFIG")
        print("   - Paste the JSON string as the value")
        print("3. Redeploy your application")
        
        return config_string
        
    except Exception as e:
        print(f"❌ Error reading credentials file: {e}")
        return None

if __name__ == "__main__":
    generate_firebase_config()
