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

automations_collection = db["workflow"]


def watch_changes():
    with db.watch() as stream:
        for change in stream:
            print("Change detected:", change)
            process_trigger(change)



def process_trigger(change):
    # Extract details from the change event

    current_collection_name = change['ns']['coll']
    document_id = change["documentKey"]["_id"]
    updated_fields = change["updateDescription"]["updatedFields"]
    print(current_collection_name,"---->" , updated_fields)
    # Retrieve all active automations
    active_automations = automations_collection.find({"active": True})
    print("automation active ------->",active_automations)
    for automation in active_automations:
        trigger = automation["trigger"]
        print("in loop ---->", trigger["tableName"] ,"---> ==",current_collection_name)
        if trigger["tableName"] == current_collection_name and evaluate_condition(trigger, updated_fields ):
            execute_actions(automation["actions"], document_id)

def evaluate_condition(trigger, updated_fields):
    """
    Evaluates the condition of a trigger and checks if the updated fields match.
    Supports both "and" and "or" logic.
    """

    # Handle the "and" conditions - all conditions in this list must be met.
    if "and" in trigger["condition"] and trigger["condition"]["and"]:
        and_conditions_met = all(
            evaluate_single_condition(c, updated_fields) for c in trigger["condition"]["and"]
        )
    else:
        and_conditions_met = True  # No "and" conditions, treat as true

    # Handle the "or" conditions - at least one condition in this list must be met.
    if "or" in trigger["condition"] and trigger["condition"]["or"]:
        or_conditions_met = any(
            evaluate_single_condition(c, updated_fields) for c in trigger["condition"]["or"]
        )
    else:
        or_conditions_met = True  # No "or" conditions, treat as true

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
        updated_value = updated_fields[field_name]
        # Return true if the operation is satisfied (example: 'equals', can be extended to other operations)
        return updated_value == expected_value or expected_value == "*"
    return False



def execute_actions(actions, document_id):
    for action in actions:
        if action["actionName"] == "updaterecord":
            print("\n\n update detected")
            update_record(action, document_id)
        # Add more action handlers as needed


def update_record(action, document_id):

    fields_to_update = {field["fieldName"]: field["fieldValue"] for field in action["fields"]}
    print("\n\n data to update",fields_to_update)
    db[action.get('tableName')].update_one({"_id": document_id}, {"$set": fields_to_update})
    print(f"\n\n\n Updated document {document_id} with fields: {fields_to_update}")


def start_watching():
    # Start a new thread to watch MongoDB in the background
    watcher_thread = threading.Thread(target=watch_changes, daemon=True)
    watcher_thread.start()


