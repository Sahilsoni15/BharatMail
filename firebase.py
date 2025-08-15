import firebase_admin
from firebase_admin import credentials, db
import os

# Get the absolute path to the credentials file
cred_path = os.path.join(os.path.dirname(__file__), "credentials", "bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json")

# Check if file exists
if not os.path.exists(cred_path):
    raise FileNotFoundError(f"Firebase credentials file not found at: {cred_path}")

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bharatmail-3698e-default-rtdb.firebaseio.com//'  # replace YOUR_PROJECT_ID
})

ref = db.reference('/')  # root reference
