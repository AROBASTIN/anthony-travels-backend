"""
MongoDB Atlas Connection Test — Final Version
==============================================
Run: py test_atlas_connection.py
"""

import os
import sys
import socket
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(env_path)

MONGODB_URI     = os.getenv('MONGODB_URI', '')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'anthony_travels')

# Mask password
masked = MONGODB_URI
try:
    start  = masked.index('://') + 3
    at     = masked.index('@')
    user   = masked[start:at].split(':')[0]
    masked = masked[:start] + user + ':****@' + masked[at+1:]
except Exception:
    pass

print("\n" + "="*60)
print(" Anthony Travels - MongoDB Atlas Connection Test")
print("="*60)
print(f"  URI  : {masked}")
print(f"  DB   : {MONGODB_DB_NAME}\n")

# Step 1: Connect
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

print("  [1/3] Connecting to Atlas ...")
try:
    client = pymongo.MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
        tlsAllowInvalidCertificates=True,
    )
    client.admin.command('ping')
    print("  Connected!\n")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"  Connection failed: {str(e)[:200]}")
    print()
    print("  If you see 'IP not whitelisted', go to:")
    print("  Atlas > Security > Network Access > Add IP Address > Allow from Anywhere (0.0.0.0/0)")
    sys.exit(1)

# Step 2: List collections
print("  [2/3] Listing collections in", MONGODB_DB_NAME, "...")
db = client[MONGODB_DB_NAME]
cols = sorted(db.list_collection_names())
if cols:
    for c in cols:
        print(f"     - {c}")
else:
    print("  (no collections yet)")
print()

# Step 3: Write/Read/Delete
print("  [3/3] Write/Read/Delete test ...")
test_col = db['_connection_test']
doc_id   = test_col.insert_one({'test': True}).inserted_id
read     = test_col.find_one({'_id': doc_id})
test_col.delete_one({'_id': doc_id})
print(f"  Write/Read/Delete OK (doc_id: {doc_id})\n")

print("="*60)
print(" MongoDB Atlas connection is WORKING")
print("="*60)
print()
print("  Next step: py seed_db.py  (to populate with data)")
print()
