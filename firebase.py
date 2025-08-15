import firebase_admin
from firebase_admin import credentials, db

cred = credentials.Certificate("bharatmail-3698e-firebase-adminsdk-fbsvc-2fd927c19d.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://bharatmail-3698e-default-rtdb.firebaseio.com//'  # replace YOUR_PROJECT_ID
})

ref = db.reference('/')  # root reference