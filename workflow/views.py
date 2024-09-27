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
from bson import ObjectId

def watch_mongo_db():
    # Connect to MongoDB
    # Specify your collection

    # Define a pipeline to filter out changes marked by your app
    pipeline = [
        {
            "$match": {
              
                "fullDocument.ignore_by_app": {"$exists": False}  # Ignore updates marked by the app
            }
        }
    ]

    try:
        with db.watch(pipeline) as stream:
            for change in stream:
                collection_name = change['ns']['coll']
                collection = db[collection_name]
                print(f"Listening for changes in collection: {collection_name}...")
                print(f"Change detected: {change}")

                # Handle insertions, updates, deletions
                if change["operationType"] == "insert":
                    print(f"New document inserted: {change['fullDocument']}")
                elif change["operationType"] == "update":
                    print(f"Document updated: {change['updateDescription']}")
                    
                    # Perform a status update and temporarily mark the document
                    doc_id = change['documentKey']['_id']
                    collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {
                            "$set": {
                                "status": "new_status",  # Update the status
                                "ignore_by_app": True  # Mark the update to ignore in the watcher
                            }
                        }
                    )

                    # Optionally remove the ignore_by_app marker after a short delay
                    # This allows future status updates to be detected again
                    def remove_marker(doc_id):
                        collection.update_one(
                            {"_id": ObjectId(doc_id)},
                            {"$unset": {"ignore_by_app": ""}}  # Remove the ignore marker
                        )

                    # Start a new thread to remove the marker after a delay
                    threading.Timer(1, remove_marker, [doc_id]).start()

                elif change["operationType"] == "delete":
                    print(f"Document deleted with ID: {change['documentKey']['_id']}")
    except Exception as e:
        print(f"Error watching MongoDB: {e}")

def start_watching():
    # Start a new thread to watch MongoDB in the background
    watcher_thread = threading.Thread(target=watch_mongo_db, daemon=True)
    watcher_thread.start()