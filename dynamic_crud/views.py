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
                statusName = "weighbridgeIn"
                created_at = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                summary = f"{dataToPost.get('vehicleNumber')} successfully completed empty weight inspection, verified by {username} at {created_at}"
                temp = {"actionName" : actionName , "status" : statusName , "created_at" : created_at , "username" : username , "summary" :summary}
                dataToPost['history'] = [temp]
            data = collection.insert_one(dataToPost)
            print("\n\n post data \n ",dataToPost)

            return Response({"message" : f"{str(collectionName).capitalize()} created Successfully" ,"success" : True },status=201)
        except Exception as e:
            print(e)
            return Response({"message" : "Request Unsuccessful" ,"success" : False },status=400)

def getSummary(data,username,statusName):
    try :
        timestamp = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        vehicle_number = data.get('vehicleNumber')
        previous = data.get('previous')
        camera_collection = db["camera"]
        current_cam_url = None
        current_cam_data = None
        previous_cam_data = None
        previous_cam_url = None
        
        if previous :
            current_cam_url = previous.get('camera')
        if current_cam_url:
            current_cam_data = camera_collection.find_one({"cameraUrl" : current_cam_url})
        current_cam_name = "Conveyor"
        if current_cam_data :
            current_cam_name = current_cam_data.get('cameraAlias')
        print("\n\n StatusName",statusName)
        summary = ""
        history = data.get('history')
        remark = data.get('workNotes')
        if previous:
            previous_cam_url = previous.get('camera')
            if previous_cam_url :
                previous_cam_data = camera_collection.find_one({"cameraUrl" : previous_cam_url})
            previous_cam_name = "Conveyor"
            if previous_cam_data :
                previous_cam_name = current_cam_data.get('cameraAlias')

        camera_display_name = "Cam 1"

        if statusName == "weighbridgeIn":
            print("Entered In---->",statusName)
            summary = f"{vehicle_number} successfully completed empty weight inspection, verified by {username} at {timestamp}."

        elif statusName == "awaitingLoadInputs":
            print("Entered In---->",statusName)
            summary = f"The package count {data.get('targetPackage',"")} and customer details have been added by {username} at {timestamp}."

        elif statusName == "awaitingLoading":
            print("Entered In---->",statusName)
            summary = f"Loading initiation point specified at {current_cam_name}, set by {username} at {timestamp}."

            
        elif statusName == "loading":
            print("Entered In---->",statusName)
            if previous_cam_url and current_cam_url and previous_cam_url == current_cam_url :
                summary += f"Loading process completed in {current_cam_name} updated by {username} at {timestamp}."
            else :
                summary = f"\nLoading in progress changed from {previous_cam_name} to  {current_cam_name}; updated by {username} at {timestamp}."
                
        elif statusName == "weighbridgeOut":
            print("Entered In---->",statusName)
            summary = f"{vehicle_number} successfully completed load weight inspection, processed by {username} at {timestamp}."

        elif statusName == "awaitingVerification":
            print("Entered In---->",statusName)
            summary = f"Load Weight and packages checked and verified by {username} at {timestamp}."
            if remark :
                summary += f"\nRemark : {remark}"

        elif statusName == "notVerified":
            print("Entered In---->",statusName)
            summary = f"Verification failed due to a mismatch in weight and package count, reported by {username} at {timestamp}."
            if remark :
                summary += "\nRemark : remark"

        elif statusName == "verified":
            print("Entered In---->",statusName)
            summary = f"Verification successful; weight and package count  confirmed by {username} at {timestamp}."
            if remark :
                summary += "\nRemark : remark"
    except Exception as e :
        print("Error -->",e)
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
            filtered_data["updated_at"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            

            if query_field:
                previous_data = dict(collection.find_one({query_field : param}))
                if previous_data :

                    previous_data.pop("_id")
                    if previous_data.get('previous'):
                        previous_data.pop('previous')
                filtered_data['previous'] = previous_data
                result = collection.update_one({query_field: param}, {'$set': filtered_data})
            else:
                previous_data = collection.find_one({'_id': ObjectId(param)})
                if previous_data :
                    previous_data.pop("_id")
                    if previous_data.get('previous'):
                        previous_data.pop('previous')

                filtered_data['previous'] = previous_data
                result = collection.update_one({'_id': ObjectId(param)}, {'$set': filtered_data})


            if result.matched_count:
                data_after_mod = collection.find_one({'_id': ObjectId(param)})
                print("Enter the History")
                for i in data_after_mod:
                    print("ddd",data_after_mod[i])
                try :
                    if collectionName in history_required_table:
                        filtered_data = {}
                        history = data_after_mod.get('history',[])
                        print("history",history)
                        actionName = "updated"
                        statusName = previous_data.get('status')
                        created_at = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                        summary = getSummary(data_after_mod , username ,statusName)
                        temp = {"actionName" : actionName , "status" : statusName , "created_at" : created_at , "username" : username ,"summary" : summary}
                        
                        history.append(temp)
                        filtered_data['history'] = history
                        collection.update_one({'_id': ObjectId(param)}, {'$set': filtered_data})
                        print('history' , history)
                except Exception as e :
                    print("Error---->" , e)
                    

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

