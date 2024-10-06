from django.http import JsonResponse
from django.core.mail import send_mail
import json
from pymongo import MongoClient
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
import re
from bson.objectid import ObjectId
import requests


# Connect to MongoDB
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING

global db
client = MongoClient(connection_string)
db = client[database_name]

sender = settings.EMAIL_HOST_USER

@api_view(['POST'])
def send_email(request):
    if request.method == 'POST':
        try:
            # Load the JSON data from the request body
            data = json.loads(request.body)
            subject = data.get('subject', "subject")
            message = data.get('message', "message")
            to_field = data.get('to')

            # Ensure 'to' is a list of recipients (handle single email case)
            if isinstance(to_field, str):
                recipient_list = [to_field]
            elif isinstance(to_field, list):
                recipient_list = to_field
            else:
                return Response({'error': "'to' field must be a valid email or list of emails."}, status=400)

            # Validate inputs
            if not subject or not message or not recipient_list:
                return Response({'error': 'Subject, message, and recipient are required.'}, status=400)

            # Send email
            send_mail(
                subject,
                message,
                sender,  # From email
                recipient_list,  # List of recipients
                fail_silently=False,
            )

            return Response({'status': 'Email sent successfully!'}, status=200)

        except Exception as e:
            return Response({'error': str(e)}, status=500)

    return Response({'error': 'Only POST requests are allowed.'}, status=405)


def send_email_function(subject , message , to_field):
        try:
            # # Load the JSON data from the request body
            # data = json.loads(request.body)
            # subject = data.get('subject', "subject")
            # message = data.get('message', "message")
            # to_field = data.get('to')

            # Ensure 'to' is a list of recipients (handle single email case)
            print('\n\n\n message Template ' ,subject , message , to_field)
            if isinstance(to_field, str):
                recipient_list = [to_field]
            elif isinstance(to_field, list):
                recipient_list = to_field
            else:
                return {'error': "'to' field must be a valid email or list of emails."}

            # Validate inputs
            if not subject or not message or not recipient_list:
                return {'error': 'Subject, message, and recipient are required.'}
            
            # Send email
            send_mail(
                subject,
                message,
                sender,  # From email
                recipient_list,  # List of recipients
                fail_silently=False,
            )

            print({'status': 'Email sent successfully!'})

        except Exception as e:
            return {'error': str(e)}


def send_whatsapp_message(number, message):
    url = "http://localhost:3000/send-message"
    payload = {
        "number": number,
        "message": message
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to send message. Status code: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def send_multiple_whatsapp_message(number, message):
    url = "https://dotsapp-om71.onrender.com/send-message"
    payload = {
        "numbers": number,
        "message": message
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to send message. Status code: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def template_to_msg(message_template, id="67024d81ac773f1b89615276"):
    # Find all placeholders inside {{ }}
    # message_template = "{{master.vehicleNumber}} ,  {{master.packageData}}"
    print(f'message template\n-------------\n{message_template}\n------------\n' , )
    msg = re.findall(r'{{(.*?)}}', message_template)

    # Dictionary to store replacement values
    replace_text = {}
    print("--------------------> msg" , msg)
    # Loop through each placeholder and fetch its corresponding data from the database
    for txt in msg:
        keys = txt.split('.')
        tablename = keys[0]
        field_path = keys[1:]

        # Fetch the data from the appropriate collection
        collection = db[tablename]  # Replace `db` with your actual MongoDB connection
        data_from_db = collection.find_one({"_id": ObjectId(id)})
        print(f"database data/n{data_from_db["orderId"]}, {field_path} ,{data_from_db}/n")
        # Follow the field path dynamically
        if data_from_db:
            value = data_from_db
            for field in field_path:
                if field in value:
                    value = value[field]
                else:
                    value = None
                    break

            # Check if the field_path points to a list (like packageData)
            if isinstance(value, list):
                if field_path[-1] == 'actualCount':
                    # If looking for actualCount, gather it from each item in packageData
                    actual_counts = [item['actualCount'] for item in value if isinstance(item, dict) and 'actualCount' in item]
                    replace_text[txt] = "\n".join(map(str, actual_counts)) if actual_counts else "N/A"
                else:
                    # Handle lists by formatting the individual items if not looking for actualCount
                    formatted_list = "\n".join(
                        [f"{item['variant']}: Target {item['targetCount']}, Actual {item['actualCount']}" for item in value if isinstance(item, dict)]
                    )
                    replace_text[txt] = formatted_list if formatted_list else "N/A"
            else:
                replace_text[txt] = value+"\n" if value is not None else "N/A"  # Set to "N/A" if None
        else:
            replace_text[txt] = "N/A"  # Set to "N/A" if the document is not found

    # Replace the placeholders in the template with the formatted values
    for placeholder, value in replace_text.items():
        message_template = message_template.replace(f"{{{{{placeholder}}}}}", str(value))

    print("Final Message:\n", message_template,"\n-------------------------\n")
    # Return the final formatted message
    return message_template



def get_contacts(id):
    contact_collection = db['contacts']
    role_collection = db['roles']
    contacts = list(contact_collection.find({"sendLoadUpdate" : True}))

    for contact in contacts:
        roleName = contact.get('roles')
        print("roles",contact.get('roles'))
        if roleName :
            role = role_collection.find_one({"roleName" : roleName})
            print("roleTable" , role)
            message_template = role.get('messageTemplate')
            if message_template:
                # print(f'message template\n-------------\n{message_template}\n------------\n' , )
                contact['messageTemplate'] = template_to_msg( message_template , str(id) )
    print(contacts , "---------contact----------->")

    return contacts


@api_view(['POST'])
def trigger(request):
    print("----------> Trigred Notify")
    data = json.loads(request.body)
    id = data.get('id')
    print(data)
    contacts = get_contacts(id)
    for contact in contacts:
        message= contact.get('messageTemplate')
        # print(send_email_function(subject="Order Id Update" ,message= message ,to_field= contact.get('email') ))
        print("contact-----------", contact)
        if contact.get('whatsapp'):
            whatsapp = str(contact.get('whatsapp')).replace("+","")
            if len(whatsapp)==10 :
                whatsapp = "91" + whatsapp
                send_whatsapp_message(whatsapp , message)
            elif len(whatsapp)==12 :
                send_whatsapp_message(whatsapp , message)
                pass
            else:
                print("In valid Whatsapp Number Format")
                
    return Response({'req': data}, status=200)

get_contacts(id="67024d81ac773f1b89615276")
# send_email_function(subject="Order Id Update" ,message= "hiii" ,to_field= 'sabarinathan3011@gmail.com')