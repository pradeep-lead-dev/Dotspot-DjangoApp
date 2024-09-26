from django.shortcuts import render 
from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from rest_framework import status
from bson.objectid import ObjectId
from django.conf import settings

client = MongoClient("mongodb+srv://dotspot:D0ts1t012345!@dotspot.el4d0.mongodb.net/?retryWrites=true&w=majority&appName=Dotspot")
restricted_fields  = settings.SENSITIVE_COLUMN
non_editable_fields = settings.NON_EDITABLE_COLUMN

# Connect to a specific database
db = client['dotspot'] 


# Create your views here.
@api_view(['GET', 'POST'])
def getAll(req,collectionName):
    collection = db[collectionName]
    if req.method == 'GET':
        data = list(collection.find({}))
        if data :
            for d in data:
                d['_id'] = str(d['_id'])  # Convert ObjectId to string
            
            return Response({'success': True , 'data': data}, status=status.HTTP_200_OK)
        
        else :
            return Response({"msg" : "No Data Found" , "data" : data , "success" : False})

    
    if req.method == 'POST' :
        dataToPost = req.data
        try :
            data = collection.insert_one(dataToPost)
        
            return Response({"msg" : f"{collectionName} created Successfully" ,"success" : True },status=201)
        except Exception as e:
            return Response({"msg" : "Request Unsuccessful" ,"success" : False },status=400)


@api_view(['GET','PUT','DELETE'])
def specificAction(request , collectionName , objId):
    collection = db[collectionName]

    if request.method == 'GET':
        try:
            form = collection.find_one({'_id': ObjectId(objId)})
            if form:
                form['_id'] = str(form['_id'])
                filtered_fields = []
                # [field for field in form.get('fields', []) if field['key'] not in restricted_fields]
                print(type(form))
                for field in form:
                    if field in  restricted_fields:
                        form[field] = None
                return Response({'success': True, 'data': form}, status=status.HTTP_200_OK)
                
                
                # Filter out restricted fields
                
            else:
                return Response({'success': False , 'message': f'{collectionName} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False , 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if request.method == "PUT":

        try:
            updated_data = request.data  # Get the data from the requestuest body
            filtered_data = {}
            for field in updated_data:
                if field not in non_editable_fields:
                    filtered_data[field] = updated_data[field]  
            result = collection.update_one({'_id': ObjectId(objId)}, {'$set': filtered_data})
            if result.matched_count:
                return Response({'success': True, 'message': f'{collectionName} updated'}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False, 'message': f'{collectionName} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    if request.method == "DELETE":
        try:
            result = collection.delete_one({'_id': ObjectId(objId)})
            if result.deleted_count:
                return Response({'success': True , 'message': f'{collectionName} deleted'}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False, 'message': f'{collectionName} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

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

