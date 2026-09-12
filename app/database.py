import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "sih_legal_metrology")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not configured in .env")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]


def get_db():
    return db


def check_connection():
    return client.admin.command("ping")