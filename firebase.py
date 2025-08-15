import firebase_admin
from firebase_admin import credentials, db
import os
import json

# Try to use environment variables first (for production), then fall back to file (for local dev)
def get_firebase_credentials():
    # Check if we have Firebase credentials in environment variables
    firebase_config = os.environ.get('FIREBASE_CONFIG')
    if firebase_config:
        try:
            # Parse the JSON string from environment variable
            cred_dict = json.loads(firebase_config)
            return credentials.Certificate(cred_dict)
        except Exception as e:
            print(f"Error parsing FIREBASE_CONFIG: {e}")
    
    # Fall back to file-based credentials (for local development)
    cred_path = os.path.join(os.path.dirname(__file__), "credentials", "bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json")
    if os.path.exists(cred_path):
        print(f"Using credentials file: {cred_path}")
        return credentials.Certificate(cred_path)
    
    # If neither works, raise an error
    raise FileNotFoundError(
        "Firebase credentials not found. Please either:\n"
        "1. Set FIREBASE_CONFIG environment variable with your service account JSON, or\n"
        f"2. Place your credentials file at: {cred_path}"
    )

# Initialize Firebase
cred = get_firebase_credentials()
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bharatmail-3698e-default-rtdb.firebaseio.com//'
})

ref = db.reference('/')  # root reference
