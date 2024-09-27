from django.shortcuts import render
from django.conf import settings
from pymongo import MongoClient
import threading
import subprocess


# Connect to MongoDB
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING

client = MongoClient(connection_string)
db = client[database_name] 


print("------------workflow------------------")
# Start watching for changes across the entire database
def watch_mongo_db():
    client = MongoClient(connection_string)
    db = client[database_name] 

    # Start watching for changes across the entire database
    try:
        with db.watch() as stream:
            print("Listening for changes in the whole database...")
            for change in stream:
                collection_name = change['ns']['coll']
                print("Change detected:", change  ,"\n", collection_name)
                # Perform any action here based on the change type
                if change["operationType"] == "insert":
                    print(f"New document inserted in collection {change['ns']['coll']}: {change['fullDocument']}")
                elif change["operationType"] == "update":
                    print(f"Document updated in collection {change['ns']['coll']}: {change['updateDescription']}")
                elif change["operationType"] == "delete":
                    print(f"Document deleted from collection {change['ns']['coll']} with ID: {change['documentKey']['_id']}")
    except Exception as e:
        print(f"Error watching MongoDB: {e}")

def start_watching():
    # Start a new thread to watch MongoDB in the background
    watcher_thread = threading.Thread(target=watch_mongo_db, daemon=True)
    watcher_thread.start()