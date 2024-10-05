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

database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING

client = MongoClient(connection_string)
db = client[database_name] 
# Connect to a specific collection
collection = db['users']  # Replace with your collection name

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
    print(user)
    try :
        permissions = []
        if user.get('permissions'):
            permissions = list(user.get('permissions').split(","))

        
    except:
        permissions = []
    roles = user.get('roles')
    
    if roles:
        for role in roles:
            collection = db['roles'] 
            roleData = collection.find_one({"roleName" : role}) 
            if roleData:
                roleDataPermisions = roleData.get("permissions")
                if roleDataPermisions:
                    permissions += roleDataPermisions.split(",")
                    print("\nrole permission ------>" , roleDataPermisions )
            
            print(role)
   
    finalPermissions = list(set(permissions))
    finalPermissions.sort()
    
    payload = {
        'user_id': str(user.get("_id")),  # Use string for MongoDB ObjectId
        'username': user.get("userName"),
        'permissions':finalPermissions,
        "roles":roles ,
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
        return Response({"message" : "required both email and password" , "success" : False},status= 400)
    else : 


        token = None
        d = collection.find_one({"email" : f"{email}"})

        
        if d and password == decrypt(d.get("password")):
            token = generate_jwt_token(d)
        else : 
            print("Invalid credentials")
            return Response({"message" : "Invalid credentials" , "success" : False },status= 400)
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

@api_view(['GET'])
def verify_token_route(req):
    try:
        token =str(req.headers.get('Authorization', None)).split(" ")[1]
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return Response({ "success" : True }, status=200)
    except jwt.ExpiredSignatureError:
        return Response({'error': 'Token exipired' , "success" : False }, status=400)  # Token has expired
    except jwt.InvalidTokenError:
        return Response({'error': 'Authorization Failed' , "success" : False}, status=401)  # Invalid token



def verify_and_get_payload(req):
    try:
        token =str(req.headers.get('Authorization', None)).split(" ")[1]
        print("------------>payload_auth",token)
        if token == settings.BY_PASS_TOKEN:
            payload = "allow.all"
        else:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

        return {"success" : True,"payload" : payload , "msg":"Token Decoded Successfully"}
    except jwt.ExpiredSignatureError:
        return {"success" : False,"payload" : None , "msg":"Token exipired"}
    except jwt.InvalidTokenError:
        return {"success" : False,"payload" : None , "msg":"Authorization Failed"}


# Middleware (decorator) to check token
def check(func):
    @wraps(func)
    def wrapper(req, *args, **kwargs):
        auth_head = str(req.headers.get('Authorization', None))

        if auth_head and len(auth_head.split(" "))> 1:
            

            auth_header = auth_head.split(" ")[1]
            if auth_header == settings.BY_PASS_TOKEN:
                return func(req, *args, **kwargs)
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
    role = req.data.get('roles',[]) 
    permission = req.data.get('permissions',"") 
    d = collection.find_one({"email" : f"{email}"})
    print(role , "--------------------")
    if d :
        return Response({"message" : "User Email Already Exists" , "success" : False},status= 400)

    if name and password and email  :
        data = {"userName" : name , "password" : encrypt (password) , "email" : email ,"roles" : role , "permissions":permission}
        d = collection.insert_one(data)
    else :
        return Response({"message" : "Bad Request" , "success" : False},status= 400)
    print(d)
    return Response({"message" : "User Registered Successfully"  , "success" : True})


@api_view(['GET'])
@check
def protected_route(req):
    # Since the token is valid, return the protected data
    return Response({"data": "data", "success": True})