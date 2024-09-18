from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
import jwt 
from datetime import datetime, timedelta
from django.conf import settings
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64
from functools import wraps


# Replace the URI string with your MongoDB Atlas connection string
client = MongoClient("mongodb+srv://dotspot:D0ts1t012345!@dotspot.el4d0.mongodb.net/?retryWrites=true&w=majority&appName=Dotspot")

# Connect to a specific database
db = client['dotspot']  # Replace with your database name

# Connect to a specific collection
collection = db['user']  # Replace with your collection name

# Create your views here.

key = b"D0ts1t012345678!" # AES-128

# Initialization vector (IV) for CBC mode (must be 16 bytes)
iv = b"1234567890123456"

def encrypt (secret):
    # Data to encrypt (must be a multiple of 16 bytes, so we pad it)
    data = secret.encode('utf-8')
    print(f"Original Data: {data}")

    padded_data = pad(data, AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_data = cipher.encrypt(padded_data)
    encrypted_base64 = base64.b64encode(encrypted_data).decode('utf-8')
    print(f"Encrypted Data: {encrypted_base64}")
    return encrypted_base64

def decrypt(encrypted_base64: str) -> str:
   
    encrypted_data = base64.b64decode(encrypted_base64)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_padded_data = cipher.decrypt(encrypted_data)
    decrypted_data = unpad(decrypted_padded_data, AES.block_size)
    return decrypted_data.decode('utf-8')

def generate_jwt_token(user):
    payload = {
        'user_id': str(user.get("_id")),  # Use string for MongoDB ObjectId
        'username': user.get("name"),
        'exp': datetime.utcnow() + timedelta(days=1),  # Expiration time
        'iat': datetime.utcnow()  # Issued at time
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token



@api_view(['POST'])
def login(req):
    print(req.data,"-------------")
    email = req.data.get('email')
    password = req.data.get('password')
    print(email , password)
    if not password or not email :
        return Response({"msg" : "required both email and password" , "success" : False},status= 400)
    else : 


        token = None
        d = collection.find_one({"email" : f"{email}"})

        
        if d and password == decrypt(d.get("password")):
            token = generate_jwt_token(d)
        else : 
            print("Invalid credentials")
            return Response({"msg" : "Invalid credentials" , "success" : False },status= 400)
        d.pop('password') 
        
        
    return Response({ "token" : token ,"success" : True})


def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return Response({'error': 'Token exipired' , "success" : False }, status=400)  # Token has expired
    except jwt.InvalidTokenError:
        return Response({'error': 'Authorization Failed' , "success" : False}, status=401)  # Invalid token
    


# Middleware (decorator) to check token
def check(func):
    @wraps(func)
    def wrapper(req, *args, **kwargs):
        auth_header = req.headers.get('token', None)

        if auth_header:
            try:
                payload = jwt.decode(auth_header, settings.SECRET_KEY, algorithms=['HS256'])
                # You can attach the payload to the request if needed
                req.user = payload
                return func(req, *args, **kwargs)  # Proceed to the view function if token is valid
            except jwt.ExpiredSignatureError:
                return Response({'error': 'Token expired', 'success': False}, status=400)
            except jwt.InvalidTokenError:
                return Response({'error': 'Authorization Failed', 'success': False}, status=401)
        else:
            return Response({'error': 'Authorization header not found'}, status=401)

    return wrapper


@api_view(['POST'])
def register(req):
    name = req.data.get('name')
    password = req.data.get('password')
    email = req.data.get('email')
    role = req.data.get('role','user') 
    d = collection.find_one({"email" : f"{email}"})
    print(role , "--------------------")
    if d :
        return Response({"msg" : "User Email Already Exists" , "success" : False},status= 400)

    if name and password and email and role :
        data = {"name" : name , "password" : encrypt (password) , "email" : email ,"role" : role}
        d = collection.insert_one(data)
    else :
        return Response({"msg" : "Bad Request" , "success" : False},status= 400)
    print(d)
    return Response({"msg" : "User Registered Successfully"  , "success" : True})


@api_view(['GET'])
@check
def protected_route(req):
    # Since the token is valid, return the protected data
    return Response({"data": "data", "success": True})