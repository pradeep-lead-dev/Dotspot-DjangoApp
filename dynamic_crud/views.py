from django.shortcuts import render 
from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from rest_framework import status
from bson.objectid import ObjectId

client = MongoClient("mongodb+srv://dotspot:D0ts1t012345!@dotspot.el4d0.mongodb.net/?retryWrites=true&w=majority&appName=Dotspot")

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
                return Response({'success': True, 'data': form}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False , 'message': f'{collectionName} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'success': False , 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if request.method == "PUT":

        try:
            updated_data = request.data  # Get the data from the requestuest body
            result = collection.update_one({'_id': ObjectId(objId)}, {'$set': updated_data})
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