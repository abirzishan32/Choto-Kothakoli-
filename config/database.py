from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# MongoDB connection
client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
db = client['banglish_converter']
users = db['users']

# Create indexes
users.create_index('email', unique=True)
users.create_index('username', unique=True)

# Create contributions collection
contributions = db['contributions']
contributions.create_index([('status', 1), ('submitted_at', -1)]) 