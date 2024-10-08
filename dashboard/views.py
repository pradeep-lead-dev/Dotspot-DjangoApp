from rest_framework.views import APIView
from rest_framework.response import Response
import cv2
import threading
import os
import torch
from ultralytics import YOLO, solutions
import mimetypes
from django.http import StreamingHttpResponse
from pymongo import MongoClient
import time
from datetime import datetime, timedelta
import json
from queue import Queue , Empty 
from django.conf import settings
import numpy as np  # To create a blank frame if no frames are available
from rest_framework.decorators import api_view
from bson.objectid import ObjectId



model_path = os.path.join(os.path.dirname(__file__), 'models/demo.pt')
videopath = os.path.join(os.path.dirname(__file__), './samplevideos/orange_10s.mp4')
# videopath1 = os.path.join(os.path.dirname(__file__), './model/sample1.mp4')
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING
# Connect to a specific database
print("video",videopath)

client = MongoClient(connection_string)
db = client[database_name] 


collection = db['records']

class HomeView(APIView):
    def get(self, request):
        return Response({"status": "running"})







# -------------------------  functionality section -------------------------------------



global camera_update_data, last_entry_time, start_time , processing , camera_urls , cameradetails , existingPackageData
frame_queues = {}
processing_flags = {}
processing_threads = {}
camera_update_data = {}
camera_cache_data = {}
start_time = {}
last_entry_time = {}
global counters
counters = {}
cameradetails = {}
existingPackageData = {}
uploadPackageData = {}
processing = False
model_path = './models/demo.pt'

model_path = 'models/demo.pt'
camera_urls = []

camera_storage_ids = {}
# camera_urls = ['./samplevideos/orange_10s.mp4', './samplevideos/sample1.mp4', 'rtsp://admin:Admin@123@115.244.221.74:2025/H.264']



# # for database 
# class Report(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     start_time = db.Column(db.DateTime, default=datetime.now)
#     end_time = db.Column(db.DateTime, nullable=True)
#     duration = db.Column(db.Float, default=0.0)
#     conveyor = db.Column(db.Integer, default=0)
#     total_count = db.Column(db.Integer, default=0)
#     last_updated = db.Column(db.DateTime, default=datetime.now)

# with app.app_context():
#     db.create_all()



# class Utility(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     time_buffer = db.Column(db.Integer, default=30)  # When this data was recorded
#     camera_urls = db.Column(db.String, default = "")
#     def __repr__(self):
#         return f'<Utility {self.frame_count} frames>'


# # Create the database and table
# with app.app_context():
#     db.create_all()

global timeperiod_for_db_storage, camera_details
timeperiod_for_db_storage = {}


# Fetch camera details from the database
def get_camera_details():
    global timeperiod_for_db_storage, camera_urls
    # Simulating DB collection
    collection = db['camera']
    data = list(collection.find({}))
    camera = None
    for camera in data:
        c_url = camera.get('cameraUrl')
        if c_url and c_url not in camera_urls:
            camera_urls.append(c_url)
            timeperiod_for_db_storage[c_url] = 10
            cameradetails[c_url] = camera
        print(c_url, "--->", len(camera_urls))
    return [timeperiod_for_db_storage, camera]


get_camera_details()
print("cam urls ---->",camera_urls)
print("cam details ---->",cameradetails)
# cameradetails[]
# Initialize video capture
def initialize_video_capture(url):
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print(f"Error: Could not open video source '{url}'")
        return None
    return cap


# Store updates for camera data
def store_update(camera_url, data):
    global camera_update_data, last_entry_time, start_time

    if camera_update_data.get(camera_url) is None:
        camera_update_data[camera_url] = {}

    if start_time.get(camera_url) is None:
        start_time[camera_url] = datetime.now()

    update_data = camera_update_data[camera_url]

    def process_nested_data(key, value):
        if isinstance(value, dict):
            if 'IN' in value and 'OUT' in value:
                update_data[f"{key}_count"] = value['OUT'] - value['IN']
            else:
                for sub_key, sub_value in value.items():
                    process_nested_data(f"{key}-{sub_key}", sub_value)
        else:
            update_data[key] = value

    for key, value in data.items():
        process_nested_data(key, value)
    if not isinstance(last_entry_time.get(camera_url), datetime):
        print(f"Invalid last_entry_time for {camera_url}. Skipping update.")
        last_entry_time[camera_url] = datetime.now()

    camera_update_data[camera_url]["total_count"] = sum(
        val for k, val in update_data.items() if k.endswith('_count') and k != 'total_count'
    )

    # last_entry_time[camera_url] = datetime.now()
    print(f"\nUpdated data for {camera_url}: {update_data}")
    print(f"Start Time for {camera_url}: {start_time[camera_url]}")
    print(f"Last Entry Time for {camera_url}: {last_entry_time.get(camera_url)}")


def update_existing_with_data(existing_data, data_to_push):
    """Update existing data with new data, modifying existing keys and adding new ones as needed."""
    
    # Convert existing data (list of dicts) into a dictionary indexed by 'variant' for easier lookup
    existing_data_dict = {item['variant']: item for item in existing_data}
    
    # Initialize the updated package data list
    updated_package_data = []
    
    # Keep track of the highest key value in existing data, only for items that have a key
    current_max_key = max((item['key'] for item in existing_data if 'key' in item), default=-1)
    
    # First, update the data from `data_to_push` with actual counts
    for variant, actual_count in data_to_push.items():
        if variant != "total_count":  # Skip 'total_count'
            if variant in existing_data_dict:
                # Update existing entry with new actual count
                updated_package_data.append({
                    'key': existing_data_dict[variant]['key'],
                    'variant': variant,
                    'targetCount': existing_data_dict[variant].get('targetCount', 0),  # Keep existing targetCount
                    'actualCount': actual_count  # Update actualCount
                })
            else:
                # If the variant is new, add it with a default targetCount of 0 and a new key
                current_max_key += 1
                updated_package_data.append({
                    'key': current_max_key,
                    'variant': variant,
                    'targetCount': 0,  # Default target count
                    'actualCount': actual_count  # New actual count
                })

    # Then, retain existing variants that were not updated
    for item in existing_data:
        if item['variant'] not in data_to_push:
            # Retain old data, ensuring to keep existing keys if present
            updated_package_data.append({
                'key': item.get('key', current_max_key + 1),  # Use the existing key or generate a new one
                'variant': item['variant'],
                'targetCount': item.get('targetCount', 0),  # Default if not present
                'actualCount': item.get('actual_count', 0)  # Use existing actual_count if present
            })
    sorted_data = sorted(updated_package_data, key=lambda x: x['key'])

    return sorted_data




def update_package_data(conveyor_split, package_data,targetPackage  , existingData ):
    # Convert package_data to a dict for easier updating, using 'variant' as key
    # print("temp verify",conveyor_split, package_data,targetPackage)
    print("temp verify",existingData)

    package_data_dict = {item['variant']: item for item in package_data}
    max_key = max(item['key'] for item in package_data)  # Find max key for new entries
    totalCount=0
    for i in package_data:
        i['actualCount'] = 0
        print(i)

    print(f'\n {package_data}\n')
    summary = "*Report Summary* \n\n"
    summary += f"*Loader Vehicle* : {existingData.get("vehicleNumber","N/A")}\n\n"
    summary += f"*Performance Overview*\n"
    summary += f"   - *Target* : {targetPackage}\n"
    summary += f"   - *Actual* : {totalCount}\n"
    summary += f"*Details*\n\n"
    start_times = []
    end_times = []
    for split_key, split_value in conveyor_split.items():
        totalCount += split_value['totalCount']
        summary += f"{split_key} - {split_value['totalCount']} \n"
        if split_value.get('startTime'):
            start_times.append(split_value.get('startTime'))

        if split_value.get('endTime'):
            end_times.append(split_value.get('endTime'))

            
        for package in split_value['packageCount']:
            variant = package['variant']
            actual_count = package['actualCount']
            
            # If the variant already exists in package_data, update the actualCount
            if variant in package_data_dict:
                package_data_dict[variant]['actualCount'] += actual_count
            else:
                # If the variant does not exist, create a new entry with the next key
                max_key += 1
                package_data_dict[variant] = {
                    'key': max_key,
                    'variant': variant,
                    'targetCount': package['targetCount'],
                    'actualCount': actual_count
                }
    summary += f"*Balance*  - {targetPackage - totalCount}\n"

    print(totalCount)
    print(summary)
    start = min(start_times)
    end = max(end_times)
    transformed_data = {
        "packageData" : list(package_data_dict.values()) ,
        "totalCount" : totalCount ,
        "summary" : summary,
        "startTime" : start,
        "endTime" : end,
        "duration" :(end-start).total_seconds()
    }
    # Convert back to list
    print("-------------> transformed data",transformed_data)

    return transformed_data





# Create a new report from updates
def create_new_item_from_updates(camera_url):
    collection = db['master']
    global camera_update_data, last_entry_time, start_time

    current_time = datetime.now()
    update_data = camera_update_data.get(camera_url, {})
    print("entered create function")
    if not isinstance(start_time.get(camera_url), datetime):
        print(f"Invalid start_time for {camera_url}. Skipping update.")
        return None

    if not isinstance(last_entry_time.get(camera_url), datetime):
        print(f"Invalid last_entry_time for {camera_url}. Skipping update.")
        return None

    total_count = update_data["total_count"] = sum(
        val for k, val in update_data.items() if k.endswith('_count') and k != 'total_count'
    )

    if (current_time - last_entry_time[camera_url]) >= timedelta(seconds =(timeperiod_for_db_storage.get(camera_url) or 5)) and total_count != 0:
        print(f"\nTotal count for {camera_url}: {total_count}")

        duration = int((last_entry_time[camera_url] - start_time[camera_url]).total_seconds())

       

                
        data_to_push = {}
        for key, value in update_data.items():
            new_key = str(key).replace('_count', '')
            if new_key != "total":
                data_to_push[new_key] = value

        existingPackageData[camera_url] = collection.find_one({"_id" : ObjectId(camera_storage_ids[camera_url])})

        uploadPackageData[camera_url] = update_existing_with_data(existingPackageData[camera_url].get("packageData",{}), data_to_push)
        print("data---> id ",camera_storage_ids,data_to_push ,"\n\n", uploadPackageData[camera_url])
        if  cameradetails.get(camera_url) :
            camera_id = cameradetails[camera_url].get("cameraId","camId")
        else :
            camera_id = "test1"


        print("temp --->")
        final_data = {
            "startTime": start_time[camera_url],
            "endTime": last_entry_time[camera_url],
            "totalCount": total_count,
            "duration": duration,
            "packageData" : uploadPackageData[camera_url]
        }
        print("existing data-->",existingPackageData[camera_url])
        print("existing end-->")

        if "ConveyorSplit" in existingPackageData[camera_url]:
        # Fetch the existing conveyor split data
            conveyor_split = existingPackageData[camera_url]["ConveyorSplit"]

            # Update the conveyor data for the specific camera/conveyor
            conveyor_split[f"{camera_id}"] = {
                "startTime": start_time[camera_url],
                "endTime": last_entry_time[camera_url],
                "totalCount": total_count,
                "duration": duration,
                "packageCount": uploadPackageData[camera_url],
                "current" : current_time
            }


            print("existing split",conveyor_split ,existingPackageData[camera_url].get("packageData") , existingPackageData[camera_url].get("targetPackage") )
            temp = {}
            temp[camera_url] = update_package_data(conveyor_split ,existingPackageData[camera_url].get("packageData") , existingPackageData[camera_url].get("targetPackage"),existingPackageData[camera_url] )
        # Push the updated ConveyorSplit back to the document
            print("temp verify",temp[camera_url])
            collection.update_one(
                {"_id": ObjectId(camera_storage_ids[camera_url])},
                {"$set": {"ConveyorSplit": conveyor_split, "packageData" : temp[camera_url]["packageData"] , "summary" : temp[camera_url]["summary"],
                           "startTime":temp[camera_url]["startTime"],
                          "endTime":temp[camera_url]["endTime"],
                          "duration":temp[camera_url]["duration"],
                          
                          "totalCount" : temp[camera_url]["totalCount"]}},upsert=True
            )
        else:
            # If ConveyorSplit doesn't exist, create it
            new_conveyor_split = {
                f"{camera_id}": {
                    "startTime": start_time[camera_url],
                    "endTime": last_entry_time[camera_url],
                    "totalCount": total_count,
                    "duration": duration,
                    "packageCount": uploadPackageData[camera_url],
                    "current" : current_time

                }
            }

            temp = {}
            temp[camera_url] = update_package_data(new_conveyor_split ,existingPackageData[camera_url].get("packageData") , existingPackageData[camera_url].get("targetPackage"),existingPackageData[camera_url] )
            # Update the document with the new ConveyorSplit
            collection.update_one(
                {"_id": ObjectId(camera_storage_ids[camera_url])},
                {"$set": {"ConveyorSplit": new_conveyor_split , "packageData" : temp[camera_url]["packageData"] , "summary" : temp[camera_url]["summary"],
                          "startTime":temp[camera_url]["startTime"],
                          "endTime":temp[camera_url]["endTime"],
                          "duration":temp[camera_url]["duration"],
                          
                          "totalCount" : temp[camera_url]["totalCount"]
                          }},upsert=True
            )





        # Simulating DB insertion
        # collection.update_one({"_id" : ObjectId(camera_storage_ids[camera_url])  } , {"$set":final_data }, upsert=True )

        
        print(f"updated new report")
        last_entry_time[camera_url] = current_time
        return {'message': 'Report updated successfully successfully'}

    return None


# Initialize the counter for object counting
def initialize_counter(camera_url):
    global counters
    line_points = [(500, 900), (2000, 900)]
    counter = solutions.ObjectCounter(
        view_img=False,
        reg_pts=line_points,
        names=YOLO(model_path).names,
        draw_tracks=False,
        region_thickness=4,
        count_reg_color=(255, 233, 203),
    )
    counters[camera_url] = counter
    print(f"Counter initialized for {camera_url}")


# Reinitialize the counter (clear counts)
def reinitialize_counter(camera_url):
    global counters
    if camera_url in counters:
        counters[camera_url].class_wise_count.clear()  # Clear the class-wise count
        print(f"Counter reset for {camera_url}")
    else:
        print(f"No existing counter found for {camera_url}. Initializing a new one.")
        initialize_counter(camera_url)


# Start model processing for the specified camera
def process_video(camera_url):
    global camera_cache_data, camera_update_data, counters, processing, camera_urls
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = YOLO(model_path).to(device)

    if camera_url not in counters:
        initialize_counter(camera_url)
    counter = counters[camera_url]

    cap = initialize_video_capture(camera_url)
    if not cap:
        return

    frame_skip = 2  # Skip every other frame to improve performance
    frame_count = 0

    while processing_flags.get(camera_url, True):
        success, frame = cap.read()
        if not success:
            cap.release()
            cap = initialize_video_capture(camera_url)
            if not cap:
                break
            continue

        frame_count += 1
        if frame_count % frame_skip != 0:  # Skip frames for efficiency
            continue

        with torch.no_grad():
            tracks = model.track(frame, persist=True, show=False, classes=list(range(100)))

        frame = counter.start_counting(frame, tracks)

        current_count = str(counter.class_wise_count)
        if camera_cache_data.get(camera_url) != current_count or True:
            camera_cache_data[camera_url] = current_count
            try:
                store_update(camera_url, json.loads(current_count.replace("'", '"')))
                create_new_item_from_updates(camera_url)
            except json.JSONDecodeError as e:
                print(f"JSON error: {e} for {camera_url}")

        if frame_queues[camera_url].full():
            frame_queues[camera_url].get()
        frame_queues[camera_url].put(frame)

        time.sleep(0.01)  # Balance CPU/GPU load


# Start camera processing API endpoint
@api_view(['POST'])
def start_camera(request):
    global camera_urls, processing_threads, processing_flags , camera_storage_ids
    print("------------> processing flag",processing_flags)
    camera_url = request.data.get('camera_url')
    obj_id = request.data.get('id')

    print(obj_id , camera_url)
    if not obj_id:
        return Response({'error': 'No camera Storage Id provided'}, status=400)
    if not camera_url:
        return Response({'error': 'No camera URL provided'}, status=400)
    camera_storage_ids[camera_url] = obj_id

    if camera_url not in camera_urls:
        return Response({'error': 'Camera Not Authorized URL provided'}, status=400)
    master_collection = db['master'] 
    master_data = master_collection.find_one({"_id" : ObjectId(camera_storage_ids[camera_url])})
    previous_data = master_data.get('previous') 
    if master_data and previous_data  :
        if previous_data and previous_data.get("camera"):
            previous_camera = previous_data.get("camera")
            stop_camera_function(previous_camera)
        # master_collection.get('previous')
    if not processing_flags.get(camera_url, False):
        processing_flags[camera_url] = True
        frame_queues[camera_url] = Queue(maxsize=10)
        processing_threads[camera_url] = threading.Thread(target=process_video, args=(camera_url,))
        processing_threads[camera_url].start()
        return Response({'message': f'Camera {camera_url} started processing'})

    return Response({'message': f'Camera {camera_url} is already running'})


# Stop camera processing API endpoint
@api_view(['POST'])
def stop_camera(request):
    global processing_flags, processing_threads

    camera_url = request.data.get('camera_url')
    if not camera_url:
        return Response({'error': 'No camera URL provided'}, status=400)

    if processing_flags.get(camera_url, False):
        processing_flags[camera_url] = False
        # Ensure data is saved before stopping
        create_new_item_from_updates(camera_url)
        reinitialize_counter(camera_url)
        if processing_threads.get(camera_url):
            processing_threads[camera_url].join()  # Wait for the thread to finish
            return Response({'message': f'Camera {camera_url} stopped and data saved'})

    return Response({'message': f'Camera {camera_url} was not running'})



def stop_camera_function(camera_url):
    global processing_flags, processing_threads

    if not camera_url:
        print({'error': 'No camera URL provided'}, status=400)
        return 
    if processing_flags.get(camera_url, False):
        processing_flags[camera_url] = False
        # Ensure data is saved before stopping
        create_new_item_from_updates(camera_url)
        reinitialize_counter(camera_url)
        if processing_threads.get(camera_url):
            processing_threads[camera_url].join()  # Wait for the thread to finish
            print({'message': f'Camera {camera_url} stopped and data saved'})

    print({'message': f'Camera {camera_url} was not running'})






















# # ---------------------------------------------------
def generate_frames(camera_url):
    """
    Generator function to retrieve the latest frame for each specific camera.
    Streams default blank frames when no actual frame is available.
    """
    while processing_flags.get(camera_url, False):
        try:
            # Get the latest frame from the queue for the specified camera URL
            latest_frame = frame_queues[camera_url].get(timeout=1)
        except Empty:
            # Create a blank frame (for example, 640x480 black image) to keep the stream alive
            # latest_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            continue

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', latest_frame)
        frame = buffer.tobytes()

        # Yield the frame to the stream
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        # Optional: Add a small delay to avoid too much CPU usage when the queue is empty
        time.sleep(0.1)



class VideoFeed(APIView):
    """
    APIView to return video feed for a specific camera.
    """
    def get(self, request, camera_id):
        # Ensure the URL passed exists in the processing threads
        camera_collection = db["camera"]
        camera = camera_collection.find_one({"cameraId" : camera_id})
        if not camera:
            return Response({"error": "Camera Not Verified" }, status=404)
        camera_url = camera.get("cameraUrl")
        if not processing_flags.get(camera_url, False):
            return Response({"error": "Camera Processing Not yet Started" }, status=404)

        # Stream the frames for the requested camera
        return StreamingHttpResponse(
            generate_frames(camera_url),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )


# # Route this in your urls.py as well
