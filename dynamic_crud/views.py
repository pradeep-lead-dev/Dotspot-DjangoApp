from django.shortcuts import render 
from rest_framework.decorators import api_view 
from rest_framework.response import Response
from pymongo import MongoClient
from rest_framework import status
from bson.objectid import ObjectId
from django.conf import settings
import datetime
from user_auth.views import check , verify_jwt_token , verify_and_get_payload# Import from the separate decorators file
from decimal import Decimal
import json

restricted_fields  = settings.SENSITIVE_COLUMN
non_editable_fields = settings.NON_EDITABLE_COLUMN
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING
history_required_table = settings.HISTORY_REQUIRED_TABLE
# Connect to a specific database
client = MongoClient(connection_string)
db = client[database_name] 


def convert_datetime_to_string(data):
    if isinstance(data, dict):
        return {k: convert_datetime_to_string(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_string(item) for item in data]
    elif isinstance(data, datetime):
        return data.strftime('%d-%m-%Y %H:%M:%S')  # Format datetime to string
    else:
        return data
    

def is_valid_objectid(id_string):
    try:
        # Try to create an ObjectId instance from the string
        ObjectId(id_string)
        return True
    except Exception:
        return False



def isNeeded(data):
    return not data.get("isDeleted",False)



# Create your views here.
@api_view(['GET', 'POST'])
@check
def getAll(req,collectionName):
    
    result = verify_and_get_payload(req)
    username = "Unknown"
    print("------------>payload" , result)
    if result.get('payload') :
        payload = result.get('payload')
    else:
        return Response({"message" : f"{result.get('msg')}"  , "success" : False})
    if payload == "allow.all" :

        permissions = []
    else :
        permissions = payload.get('permissions')[:]
        username = payload.get('username',"Unknown")


    collection = db[collectionName]
    if req.method == 'GET':
        
        if (not permissions or str(collectionName+".read") not in permissions) and payload != "allow.all":
            return Response({'message': 'Permission Denied', 'success': False}, status=401)
        data = list(collection.find({}))
        if data :
            for d in data:
                
                d['_id'] = str(d['_id'])  # Convert ObjectId to string
                for field in restricted_fields:
                    if field in d:
                        del d[field]
            finaldata = [d for d in data if  isNeeded(d)]

            if collectionName == "master" and payload != "allow.all":
                print("statusToBeFiltered" , payload.get('statusToBeFiltered'))
                to_filter = payload.get('statusToBeFiltered')
                master_data= []
                
                master_data = [d for d in finaldata if d.get("status") in to_filter]

                finaldata = master_data

            return Response({'success': True , 'data': finaldata[::-1]}, status=status.HTTP_200_OK)
        
        else :
            return Response({"message" : "No Data Found" , "data" : data , "success" : False})

    
      
    if req.method == 'POST' :
        if not permissions or str(collectionName+".create") not in permissions:
            return Response({'message': 'Permission Denied', 'success': False}, status=401)
        dataToPost = req.data
        dataToPost["updated_at"] = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        dataToPost["created_at"] = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        # if "autoincrement" in dataToPost :

        try :
            forms = db['forms']
            form = forms.find_one({"tableName" : collectionName})
            if form:
                fields = form.get('fields')
                print(fields)
                autoIncrementfield = {}
                for field in fields:
                    if field.get('type') == "autoincrement":
                        autoIncrementfield = field
                print("\n\n",autoIncrementfield) 

                if autoIncrementfield:
                    prefix = autoIncrementfield.get('prefixForAutoIncrement')
                    field_name = autoIncrementfield.get('key')


                    max_entry = collection.find_one({}, sort=[('entry_number', -1)])  # Sort by entry_number in descending order
                    if max_entry and 'entry_number' in max_entry:
                        dataToPost['entry_number'] = max_entry['entry_number'] + 1
                    else:
                        dataToPost['entry_number'] = 1 
                    dataToPost[field_name] = prefix + str(dataToPost['entry_number'])
                    print(f"{prefix} --- {field_name}   --{ prefix + str(dataToPost['entry_number'])} ")
            if collectionName in history_required_table:
                actionName = "created"
                statusName = "waybridgeIn"
                created_at = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                temp = {"actionName" : actionName , "status" : statusName , "created_at" : created_at , "username" : username}
                dataToPost['history'] = [temp]
            data = collection.insert_one(dataToPost)
            print("\n\n post data \n ",dataToPost)

            return Response({"message" : f"{str(collectionName).capitalize()} created Successfully" ,"success" : True },status=201)
        except Exception as e:
            print(e)
            return Response({"message" : "Request Unsuccessful" ,"success" : False },status=400)

def getSummary(data,username):
    timestamp = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    vehicle_number = data.get('vehicleNumber')
    vehicle_number = data.get('vehicleNumber')
    camera_display_name = "Cam 1"
    if status == "weighbridgeIn":
        summary = (f"{vehicle_number} successfully completed empty weight inspection, verified by {username} at {timestamp}.")

    elif status == "awaitingLoadInputs":
        summary = (f"The package count and customer details have been handled by {username} at {timestamp}.")

    elif status == "awaitingLoading":
        summary = (f"Loading initiation point specified at {camera_display_name}, set by {username} at {timestamp}.")

    elif status == "loading":
        summary = (f"1. Loading in progress changed from this Camera ID {previous_camera_id} to Camera ID {current_camera_id}; updated by {username} at {timestamp}.\n"
                f"2. Loading process completed in {duration}; status will be updated by {username} at {timestamp}.")

    elif status == "weighbridgeOut":
        summary = (f"Vehicle weighed post-loading; load weight updated by {username} at {timestamp}.")

    elif status == "awaitingVerification":
        summary = (f"Load Weight and packages checked; verification status being updated by {username} at {timestamp}.")

    elif status == "notVerified":
        summary = (f"Verification failed due to a mismatch in weight and package count, noted by {username} at {timestamp}.")

    elif status == "verified":
        summary = (f"Verification successful; weight and package count confirmed by {username} at {timestamp}.")

    return summary

@api_view(['GET','PUT','DELETE'])
@check
def specificAction(request , collectionName , param):
    result = verify_and_get_payload(request)
    username = "Unknown"
    print("------------>payload" , result)
    if result.get('payload') :
        payload = result.get('payload')
    else:
        return Response({"message" : f"{result.get('msg')}"  , "success" : False})
    if payload == "allow.all" :

        permissions = []
    else :
        permissions = payload.get('permissions')[:]
        username = payload.get('username',"Unknown")

        

    collection = db[collectionName]
    query_field = request.headers.get('query-field', None)
    # print(request.headers)
    if request.method == 'GET':
        if (not permissions or str(collectionName+".read") not in permissions) and payload != "allow.all":
            return Response({'message': 'Permission Denied', 'success': False}, status=401)
        
        try:
            table_collection = db["forms"]
            formData = table_collection.find_one({"tableName" : collectionName})
        except Exception as e:
            print("Error While fetch table Data from Form Table",e)
        serialized_data = None
        if formData:
            formData.pop("_id")
            for i in formData:
                if isinstance(i,datetime.datetime):
                    i = i.isoformat()

            

        print("formData" , formData)
        if param == "undefined":
            return Response({'success': True ,'formData' : formData }, status=status.HTTP_200_OK)
        try:
            if query_field:
                form = collection.find_one({query_field : param})
                
                print("use q ", query_field , param)
            else:

                form = collection.find_one({'_id': ObjectId(param)})

            if form and isNeeded(form):
                form['_id'] = str(form['_id'])
                filtered_fields = []
                # [field for field in form.get('fields', []) if field['key'] not in restricted_fields]
                print(type(form),type(formData))
                for field in form:
                    if field in  restricted_fields:
                        form[field] = None

                if collectionName == "master" and payload != "allow.all":
                    print("statusToBeFiltered" , payload.get('statusToBeFiltered'))
                    if form.get('status') not in payload.get('statusToBeFiltered') :
                        return Response({'message': 'Access Denied', 'success': False}, status=401)
                return Response({'success': True, 'data': form ,'formData' : formData }, status=status.HTTP_200_OK)
                
                
                # Filter out restricted fields
                
            else:
                return Response({'success': False , 'message': f'{str(collectionName).capitalize()} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({'success': False , 'message': str(e).capitalize()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if request.method == "PUT":
        if not permissions or str(collectionName+".update") not in permissions:
            return Response({'message': 'Permission Denied', 'success': False}, status=401)
        try:
            
            updated_data = request.data  # Get the data from the requestuest body
            filtered_data = {}
            for field in updated_data:
                if field not in non_editable_fields:
                    filtered_data[field] = updated_data[field]  
            filtered_data["updated_at"] = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            

            if query_field:
                previous_data = dict(collection.find_one({query_field : param}))
                previous_data_befor_remove = previous_data

                if previous_data :

                    previous_data.pop("_id")
                    if previous_data.get('previous'):
                        previous_data.pop('previous')
                    if collectionName in history_required_table:
                        history = previous_data.get('history',[])
                        print("history",history)
                        actionName = "updated"
                        statusName = previous_data.get('status')
                        created_at = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                        summary = getSummary(previous_data , username)
                        temp = {"actionName" : actionName , "status" : statusName , "created_at" : created_at , "username" : username ,"summary" : summary}
                        
                        history.append(temp)
                        filtered_data['history'] = history
                        print('history' , history)

                        
                filtered_data['previous'] = previous_data
                result = collection.update_one({query_field: param}, {'$set': filtered_data})
            else:
                previous_data = collection.find_one({'_id': ObjectId(param)})
                previous_data_befor_remove = previous_data
                if previous_data :
                    previous_data.pop("_id")
                    if previous_data.get('previous'):
                        previous_data.pop('previous')
                    if collectionName in history_required_table:
                        history = list(previous_data.get('history',[]))
                        print("history",history)
                        actionName = "updated"
                        statusName = "waybridgeIn"
                        created_at = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                        summary = getSummary(previous_data , username)
                        temp = {"actionName" : actionName , "status" : statusName , "created_at" : created_at , "username" : username ,"summary" : summary}
                        
                        print("history",temp)
                        history.append(temp)
                        filtered_data['history'] = history
                        print('history' , history)

                filtered_data['previous'] = previous_data
                result = collection.update_one({'_id': ObjectId(param)}, {'$set': filtered_data})
            if result.matched_count:
                return Response({'success': True, 'message': f'{str(collectionName).capitalize()} updated'}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False, 'message': f'{str(collectionName).capitalize()} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({'success': False, 'message': str(e).capitalize()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    if request.method == "DELETE":
        if not permissions or str(collectionName+".delete") not in permissions:
            return Response({'message': 'Permission Denied', 'success': False}, status=401)
        try:
            filtered_data={"isDeleted": True}
            if query_field:
                result = collection.update_one({query_field: param}, {'$set': filtered_data})
            else:
                result = collection.update_one({'_id': ObjectId(param)}, {'$set': filtered_data})
            if result:
                return Response({'success': True , 'message': f'{str(collectionName).capitalize()} deleted'}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False, 'message': f'{str(collectionName).capitalize()} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({'success': False, 'message': str(e).capitalize()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET'])
def get_all_collections(req):
    try :
        collections = db.list_collection_names()
        print(collections)
    # Print the names of the collections
        for collection in collections:
            print(collection)
        return Response({'success': True, "data" : collections },status=status.HTTP_200_OK)
    except Exception as e:
            print(e)
            return Response({'success': False, 'message': str(e).capitalize()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        











data = {
        "tableName": "Master Table",
        "fields": [
            {
                "type": "textbox",
                "label": "Vehicle Number",
                "key": "vehicleNum",
                "defaultValue": "",
                "options": [],
                "placeholder": "Enter Vehicle Number",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 0,
                "regex": ""
            },
            {
                "type": "textbox",
                "label": "Date Entered",
                "key": "dateEntered",
                "defaultValue": "",
                "options": [],
                "placeholder": "dd-mm-yyyy",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 1,
                "regex": "(^0[1-9]|[12][0-9]|3[01])-(0[1-9]|1[0-2])-(\\d{4}$)"
            },
            {
                "type": "textbox",
                "label": "Weight Without Load",
                "key": "weightwithoutload",
                "defaultValue": "",
                "options": [],
                "placeholder": "Enter Weight",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 2,
                "regex": ""
            },
            {
                "type": "textbox",
                "label": "Driver Name",
                "key": "driverName",
                "defaultValue": "Enter name",
                "options": [],
                "placeholder": "Enter name",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 3,
                "regex": ""
            },
            {
                "type": "textbox",
                "label": "Destination",
                "key": "destination",
                "defaultValue": "Enter Location",
                "options": [],
                "placeholder": "Enter Location",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 4,
                "regex": ""
            },
            {
                "type": "textbox",
                "label": "Gate Officer Name",
                "key": "gateOfficerName",
                "defaultValue": "Enter Name",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 5,
                "regex": ""
            },
            {
                "type": "number",
                "label": "Driver Phone",
                "key": "driverPhone",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 6,
                "regex": ""
            },
            {
                "type": "dropdown",
                "label": "Status",
                "key": "status",
                "defaultValue": "",
                "options": [
                    {"label": "Awaiting Load Inputs", "value": "awaitingLoadInputs"},
                    {"label": "Awaiting Loading", "value": "awaitingLoading"},
                    {"label": "Loading", "value": "loading"},
                    {"label": "Awaiting Verification", "value": "awaitingVerification"},
                    {"label": "Verified", "value": "verified"},
                    {"label": "", "value": ""},
                    {"label": "", "value": ""}
                ],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 7,
                "regex": ""
            },
            {
                "type": "number",
                "label": "Total Package",
                "key": "totalPackage",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 8,
                "regex": ""
            },
            {
                "type": "dropdown",
                "label": "Lane",
                "key": "lane",
                "defaultValue": "",
                "options": [
                    {"label": "Lane 1", "value": "laneOne"},
                    {"label": "Lane 2", "value": "laneTwo"},
                    {"label": "Lane 3", "value": "laneThree"},
                    {"label": "Lane 4", "value": "laneFour"}
                ],
                "placeholder": "",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": 9,
                "regex": ""
            },
            {
                "type": "dropdown",
                "label": "Lane Status",
                "key": "laneStatus",
                "defaultValue": "",
                "options": [
                    {"label": "Entered", "value": "entered"},
                    {"label": "Loading", "value": "loading"},
                    {"label": "Exit", "value": "exit"}
                ],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": False,
                "rolesToVisible": "",
                "order": 10,
                "regex": ""
            },
            {
                "type": "number",
                "label": "Packages Loaded",
                "key": "packagesLoaded",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": False,
                "rolesToVisible": "",
                "order": 11,
                "regex": ""
            },
            {
                "type": "number",
                "label": "Vehicle Moved Lane Count",
                "key": "vehicleMovedLaneCount",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": False,
                "tableView": True,
                "visibility": False,
                "rolesToVisible": "",
                "order": 12,
                "regex": ""
            },
            {
                "type": "textbox",
                "label": "Date Exited",
                "key": "dateExited",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": False,
                "rolesToVisible": "",
                "order": "12",
                "regex": ""
            },
            {
                "type": "number",
                "label": "Weight With Load",
                "key": "weightWithLoad",
                "defaultValue": "",
                "options": [],
                "placeholder": "",
                "disabled": False,
                "required": True,
                "tableView": True,
                "visibility": True,
                "rolesToVisible": "",
                "order": "14",
                "regex": ""
            }
        ] }


@api_view(['GET'])
def dummy(req):
    return Response({"data" : data})

