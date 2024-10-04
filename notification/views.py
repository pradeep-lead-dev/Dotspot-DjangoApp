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
    url = "https://dotsapp-om71.onrender.com/send-message"
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


# Example usage
# result = send_whatsapp_message("918220018259", "hiii brooo")   

def template_to_msg(id="66fd0653817940580f1599fc"):
    # Template string with placeholders
    text = '--------------------------------------------------------------\n| {{master.orderId}} |\n| {{master.packageData}} |\n| {{master.totalPackage}} |'
    
    # Find all placeholders inside {{ }}
    msg = re.findall(r'{{(.*?)}}', text)

    # Dictionary to store replacement values
    replace_text = {}

    # Loop through each placeholder and fetch its corresponding data from the database
    for txt in msg:
        tablename, field = txt.split('.')
        collection = db[tablename]
        data_from_db = collection.find_one({"_id": ObjectId(id)})
        
        if data_from_db:
            replace_text[txt] = data_from_db.get(field, "No Data")

    # Initialize a list to store the final table lines
    table_lines = []
    
    # Create table header
    header = f"| {'SpotId'.ljust(30)} | {'Value'.ljust(30)} |"
    table_lines.append("--------------------------------------------------------------")
    table_lines.append(header)
    table_lines.append("--------------------------------------------------------------")

    for key, value in replace_text.items():
        if isinstance(value, list):
            # For lists (like packageData), create multiple rows
            for item in value:
                variant = item.get('variant', 'N/A')
                actual_count = item.get('actualCount', 'N/A')
                table_lines.append(f"| {variant.ljust(30)} | actual count: {str(actual_count).ljust(30)} |")
        else:
            # For single fields like orderId or totalPackage, create a simple row
            field_name = key.split('.')[-1]
            table_lines.append(f"| {field_name.ljust(30)} | {str(value).ljust(30)} |")

    # Add the final closing line of the table
    table_lines.append("--------------------------------------------------------------")

    # Join all lines into a final formatted string
    final_table = '\n'.join(table_lines)

    # Return or print the final converted string
    print("Converted Template:\n", final_table)
    return final_table


def get_contacts(id):
    contact_collection = db['contacts']
    role_collection = db['roles']
    contacts = list(contact_collection.find({"sendLoadUpdate" : True}))

    for contact in contacts:
        roleName = contact.get('roles')[0]
        print(contact.get('roles')[0])
        if roleName :
            role = role_collection.find_one({"roleName" : roleName})
            message_template = role.get('messageTemplate')
            if message_template:
                contact['messageTemplate'] = template_to_msg( id)

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
        print(send_email_function(subject="Order Id Update" ,message= message ,to_field= contact.get('email') ))
        print("contact-----------", contact)
        if contact.get('whatsapp'):
            whatsapp = str(contact.get('whatsapp')).replace("+","")
            if len(whatsapp)==10 :
                whatsapp = "91" + whatsapp
            elif len(whatsapp)==12 :
                send_whatsapp_message(whatsapp , message)
                
    return Response({'req': data}, status=200)

get_contacts(id="66fd0653817940580f1599fc")
# send_email_function(subject="Order Id Update" ,message= "hiii" ,to_field= 'sabarinathan3011@gmail.com')