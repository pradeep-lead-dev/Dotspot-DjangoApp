from django.shortcuts import render
from django.conf import settings
from pymongo import MongoClient
import threading
import subprocess
import requests
from bson.objectid import ObjectId
from datetime import datetime
import json
import ast , re
# Connect to MongoDB
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING

client = MongoClient(connection_string)
db = client[database_name]


print("------------workflow------------------")
# Start watching for changes across the entire database
automations_collection = db["workflow"]


def watch_changes():
    with db.watch() as stream:
        for change in stream:

            print("Change detected:", change)
            process_trigger(change)


def process_trigger(change):
    """
    Processes the trigger based on the type of MongoDB operation.
    Handles 'update', 'insert', and 'delete' operations separately.
    """
    global current_collection_name, document_id, current_document
    
    # Extract the collection name and document ID
    current_collection_name = change['ns']['coll']
    document_id = change["documentKey"]["_id"]
    
    # Check the type of operation
    operation_type = change.get("operationType")
    
    if operation_type == "update":
        # Handle update operation and retrieve updated fields
        updated_fields = change.get("updateDescription", {}).get("updatedFields", {})
        print(f"Update detected in {current_collection_name} --> Updated fields: {updated_fields}")
        previous_document = change.get("fullDocumentBeforeChange")
        if updated_fields:
            
            # Fetch the latest version of the document
            current_document = db[current_collection_name].find_one({"_id": ObjectId(document_id)})
            
            # Proceed with active automations if updated fields match triggers
            trigger_automation(current_collection_name, document_id, updated_fields)
    
    elif operation_type == "insert":
        # Handle insert operation
        current_document = change.get("fullDocument", {})
        print(f"Insert detected in {current_collection_name} --> Document: {current_document}")
        print(current_collection_name, current_document.get("_id"), current_document)
        trigger_automation(current_collection_name, current_document.get("_id"), current_document)
        # You can implement any logic to handle insert events if needed
        # For example, triggering automations based on insertions
    
    elif operation_type == "delete":
        # Handle delete operation
        print(f"Delete detected in {current_collection_name} --> Document ID: {document_id}")
        
        # Logic for handling deletions can be added here if needed
    
    else:
        print(f"Other operation detected: {operation_type}")


def trigger_automation(current_collection_name, document_id, updated_fields):
    """
    Retrieves all active automations and triggers actions if conditions match.
    """
    # Retrieve all active automations
    active_automations = automations_collection.find({"active": True})
    print("Active automations found:", active_automations)

    for automation in active_automations:
        trigger = automation["trigger"]
        print(f"In loop: {trigger['tableName']} == {current_collection_name}")
        
        if trigger["tableName"] == current_collection_name and evaluate_condition(trigger, updated_fields):
            execute_actions(automation["actions"], document_id, updated_fields,current_collection_name)


def evaluate_condition(trigger, updated_fields):
    """
    Evaluates the condition of a trigger and checks if the updated fields match.
    Supports both "and" and "or" logic.
    """

    # Handle the "and" conditions - all conditions in this list must be met.
    and_conditions_met = True
    if "and" in trigger["condition"] and trigger["condition"]["and"]:
        and_conditions_met = all(
            evaluate_single_condition(c, updated_fields) for c in trigger["condition"]["and"]
        )
        print(and_conditions_met,"----------> and condttion")
    # Handle the "or" conditions - at least one condition in this list must be met.
    or_conditions_met = True
    if "or" in trigger["condition"] and trigger["condition"]["or"]:
        or_conditions_met = any(
            evaluate_single_condition(c, updated_fields) for c in trigger["condition"]["or"]
        )

    # Return true only if all "and" conditions are met and at least one "or" condition is satisfied.
    return and_conditions_met and or_conditions_met


def evaluate_single_condition(condition, updated_fields):
    """
    Evaluates a single condition based on the field value.
    Compares the condition field value with the updated field value.
    """
    field_name = condition.get("field")
    expected_value = condition.get("to")
  
    
    # Ensure the field exists in the updated fields and matches the expected value
    if field_name in updated_fields:
        print("fiels ---->" , field_name)
        print("expected --->" ,updated_fields[field_name] , expected_value)
        updated_value = updated_fields[field_name]
        print("----------> ",updated_fields,updated_value == expected_value )
        # Return true if the operation is satisfied (example: 'equals', can be extended to other operations)
        return updated_value == expected_value or expected_value == "*"
    return False


def execute_actions(actions, document_id, updated_fields,current_collection_name):
    """
    Executes actions like 'updaterecord' and 'startcamera' based on the automation config.
    """
    for action in actions:
        if action["actionName"] == "updaterecord":
            print("\n\nUpdate detected")
            update_record(action, document_id)

        elif action["actionName"] == "startcamera":
            start_camera(action, updated_fields,document_id)
        
        elif action["actionName"] == "stopcamera":
            start_camera(action, updated_fields,document_id,stop=True)

        elif action["actionName"] == "webhook":
            trigger_webhook(action, updated_fields,current_collection_name,document_id)


def update_record(action, document_id):
    """
    Updates a record in a collection based on the action's fields.
    """
    fields_to_update = {field["fieldName"]: field["fieldValue"] for field in action["fields"]}
    print(f"\n\nData to update: {fields_to_update}")
    
    db[action.get('tableName')].update_one({"_id": document_id}, {"$set": fields_to_update})
    print(f"Updated document {document_id} with fields: {fields_to_update}")


def start_camera(action, updated_fields,document_id,stop=False):
    """
    Trigger an API call to start a camera based on the given action configuration.
    """
    try:
        api_url = "http://localhost:8000/api/dashboard/start-camera" 
        tableName = action.get("tableName")
        fieldName = action.get("fieldName")
        collection = db[tableName]
        
        print("inside the startcamera func")
        previous = updated_fields.get('previous')
        # print("previous Data",previous.get(fieldName))
        # running_camera  = previous.get(fieldName)
        cameraUrl = updated_fields.get('camera')
        if stop :
            api_url = "http://localhost:8000/api/dashboard/stop-camera"  # The API endpoint URL from the JSON
            current_camera = collection.find_one()
        # stop the previous camera by request
        # if not stop and running_camera:
        #     stop_url = "http://localhost:8000/api/dashboard/stop-camera"
        #     response = requests.post(api_url, json={"camera_url": cameraUrl,"id":str(document_id) })

        # # Check if the request was successful
        #     if response.status_code == 200:
        #         print(response.text)
        #         print(f"Camera {cameraUrl} action successful.")
        #     else:
        #         print(f"Failed to perform  camera {cameraUrl}. Status code: {response.status_code}")
        #         print("Response:", response.text)


        # print(camera_obj_id, "--->id")
        # tableDocument = db[tableName].find_one({'_id': ObjectId(camera_obj_id)})
        # print('table-->', camera_obj_id, tableName, tableDocument)
        # cameraUrl = tableDocument.get('cameraUrl')

        # The camera ID or any other required parameter
        # print()
        print(updated_fields , fieldName)

        if not cameraUrl:
            print("No API URL provided for camera action.")
            return
        print(document_id,type(document_id) ,str(document_id),"doc id")
        # Make an API call using the provided route (e.g., POST request)
        response = requests.post(api_url, json={"camera_url": cameraUrl,"id":str(document_id) })

        # Check if the request was successful   
        if response.status_code == 200:
            # print(response.text)
            print(f"Camera {cameraUrl} action successful.")
        else:
            print(f"Failed to perform  camera {cameraUrl}. Status code: {response.status_code}")
            # print("Response:", response.text)
    except Exception as e:
        print(f"Error while starting camera: {e}")

def json_serial(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to string in ISO format
    raise TypeError(f"Type {type(obj)} not serializable")


def sanitize_body_string(body_str):
    # Replace control characters (if any) that are not allowed in JSON
    # For example, replace unescaped newline or tab characters
    sanitized_str = re.sub(r'[\x00-\x09\x0B-\x1F\x7F]', '', body_str)

    # sanitized_str = re.sub(r'[\x00-\x1F\x7F]', '', body_str)  # Remove control characters
    return sanitized_str

def trigger_webhook(action, updated_fields, current_collection_name, document_id):
    try:
        webhook_url = action.get('url')

        headers = action.get('headers', {})
        
        # Ensure headers is a dictionary
        if not isinstance(headers, dict):
            headers = {}

        if not webhook_url.startswith(('http://', 'https://')):
            webhook_url = 'http://' + webhook_url
        body_str = action.get('body', "")
        print(body_str, "booody str")
        body = {}

        # Sanitize the body string
        if body_str:
            body_str = sanitize_body_string(body_str)  # Clean the string
            
            try:
                # Try to load the body as JSON
                body = json.loads(body_str)
            except json.JSONDecodeError as json_err:
                print(f"JSON decode error: {json_err}")
                return  # Exit if JSON parsing fails

        print("action----->", action, type(body))
        
        print('body ----->' , body )
        method = str(action.get('method', 'get')).upper()
        body["id"] = str(document_id)
        body["tableName"] = current_collection_name
        
        # Convert datetime objects to string (ISO format) if they exist
        for key, value in updated_fields.items():
            if isinstance(value, datetime):
                updated_fields[key] = value.isoformat()
        
        # Add updated fields to the body
        body.update(updated_fields)
        
        print("\nbody\n", body)
        print(f"Triggering webhook: {webhook_url} with headers: {headers} and body: {body}")

        if method == 'POST':
            # Send POST request with JSON body
            response = requests.post(webhook_url, json=body, headers=headers)

        elif method == 'GET':
            # Send GET request with parameters
            response = requests.get(webhook_url, headers=headers, params=body)

        # Check response status
        if response.status_code in [200, 201]:
            print(f"Webhook triggered successfully: {response.status_code}")
        else:
            print(f"Failed to trigger webhook. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error while triggering webhook: {e}")



def start_watching():
    """
    Start a new thread to watch MongoDB in the background.
    """
    watcher_thread = threading.Thread(target=watch_changes, daemon=True)
    watcher_thread.start()

