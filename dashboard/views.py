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



model_path = os.path.join(os.path.dirname(__file__), 'models/demo.pt')
videopath = os.path.join(os.path.dirname(__file__), './model/orange_10s.mp4')
# videopath1 = os.path.join(os.path.dirname(__file__), './model/sample1.mp4')
database_name = settings.DATABASE_NAME
connection_string = settings.DATABASE_CONNECTION_STRING
# Connect to a specific database


client = MongoClient(connection_string)
db = client[database_name] 


collection = db['records']

class HomeView(APIView):
    def get(self, request):
        return Response({"status": "running"})







# -------------------------  functionality section -------------------------------------



global camera_update_data, last_entry_time, start_time , processing , camera_urls , cameradetails
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
processing = False
model_path = './models/demo.pt'

model_path = 'models/demo.pt'
camera_urls = ['models/orange_10s.mp4']
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
    collection = db['cameradetails']
    data = list(collection.find({}))
    camera = None
    for camera in data:
        c_url = camera.get('cameraUrl')
        if c_url and c_url not in camera_urls:
            camera_urls.append(c_url)
            timeperiod_for_db_storage[c_url] = camera.get('bufferTime', 15)
            cameradetails[c_url] = camera
        print(c_url, "--->", len(camera_urls))
    return [timeperiod_for_db_storage, camera]


get_camera_details()


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

    camera_update_data[camera_url]["total_count"] = sum(
        val for k, val in update_data.items() if k.endswith('_count') and k != 'total_count'
    )

    last_entry_time[camera_url] = datetime.now()
    print(f"\nUpdated data for {camera_url}: {update_data}")
    print(f"Start Time for {camera_url}: {start_time[camera_url]}")
    print(f"Last Entry Time for {camera_url}: {last_entry_time[camera_url]}")


# Create a new report from updates
def create_new_item_from_updates(camera_url):
    global camera_update_data, last_entry_time, start_time

    current_time = datetime.now()
    update_data = camera_update_data.get(camera_url, {})

    if not isinstance(start_time.get(camera_url), datetime):
        print(f"Invalid start_time for {camera_url}. Skipping update.")
        return None

    if not isinstance(last_entry_time.get(camera_url), datetime):
        print(f"Invalid last_entry_time for {camera_url}. Skipping update.")
        return None

    total_count = update_data["total_count"] = sum(
        val for k, val in update_data.items() if k.endswith('_count') and k != 'total_count'
    )

    if (current_time - last_entry_time[camera_url]) >= timedelta(minutes=(timeperiod_for_db_storage.get(camera_url) or 10)) and total_count != 0:
        print(f"\nTotal count for {camera_url}: {total_count}")

        duration = int((last_entry_time[camera_url] - start_time[camera_url]).total_seconds())
        data_to_push = {
            "startTime": start_time[camera_url],
            "endTime": last_entry_time[camera_url],
            "Total_count": total_count,
            "duration": duration
        }

        for key, value in update_data.items():
            data_to_push[key] = value

        # Simulating DB insertion
        collection.insert_one(data_to_push)
        print(f"Created new report")

        return {'message': 'Report created successfully'}

    return None


# Initialize the counter for object counting
def initialize_counter(camera_url):
    global counters
    line_points = [(0, 900), (3000, 900)]
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
        if camera_cache_data.get(camera_url) != current_count:
            camera_cache_data[camera_url] = current_count
            try:
                store_update(camera_url, json.loads(current_count.replace("'", '"')))
                # create_new_item_from_updates(camera_url)
            except json.JSONDecodeError as e:
                print(f"JSON error: {e} for {camera_url}")

        if frame_queues[camera_url].full():
            frame_queues[camera_url].get()
        frame_queues[camera_url].put(frame)

        time.sleep(0.01)  # Balance CPU/GPU load


# Start camera processing API endpoint
@api_view(['POST'])
def start_camera(request):
    global camera_urls, processing_threads, processing_flags

    camera_url = request.data.get('camera_url')
    if not camera_url:
        return Response({'error': 'No camera URL provided'}, status=400)

    if camera_url not in camera_urls:
        camera_urls.append(camera_url)

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
        if processing_threads.get(camera_url):
            processing_threads[camera_url].join()  # Wait for the thread to finish
            return Response({'message': f'Camera {camera_url} stopped and data saved'})

    return Response({'message': f'Camera {camera_url} was not running'})
























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
    def get(self, request, camera_no = 1):
        # Ensure the URL passed exists in the processing threads
        print(str(camera_no).isnumeric() , camera_no)
        if ( not str(camera_no).isnumeric() or  int(camera_no) == 0 ):
            return Response({"error": "Bad Request"}, status=400)

        cameraNo = int(camera_no)-1
        
        if cameraNo >= len(camera_urls) or  camera_urls[cameraNo] not in camera_urls:
            return Response({"error": "Camera URL not found" }, status=404)
        
        camera_url = camera_urls[cameraNo]
        if not processing_flags.get(camera_url, False):
            return Response({"error": "Camera Processing Not yet Started" }, status=404)

        # Stream the frames for the requested camera
        return StreamingHttpResponse(
            generate_frames(camera_urls[cameraNo-1]),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )


# # Route this in your urls.py as well
