from rest_framework.views import APIView
from rest_framework.response import Response
import cv2
import queue
import threading
import os
import torch
from ultralytics import YOLO, solutions
import mimetypes
from django.http import StreamingHttpResponse

# Global dictionaries to manage camera streams
frame_queues = {}  # To hold frames for each camera URL/thread
processing_flags = {}  # To control the thread processing for each camera
processing_threads = {}  # To handle thread references

model_path = os.path.join(os.path.dirname(__file__), 'model/demo.pt')
videopath = os.path.join(os.path.dirname(__file__), './model/orange1.mp4')
videopath1 = os.path.join(os.path.dirname(__file__), './model/sample1.mp4')

global camera_urls 

camera_urls = [
    videopath1,
    videopath,
    # Add more camera URLs
]

class HomeView(APIView):
    def get(self, request):
        return Response({"status": "running"})


def start_model_processing():
    """
    Start processing YOLO model for all camera URLs, with separate thread and frame generation.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    def initialize_video_capture(url):
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            print(f"Error: Could not open video source '{url}'")
            return None
        return cap

    def process_video(camera_url):
        # Create a unique frame queue for each camera thread
        frame_queue = queue.Queue(maxsize=100)
        frame_queues[camera_url] = frame_queue
        processing_flags[camera_url] = True

        # Initialize YOLO model for each thread
        model = YOLO(model_path).to(device)

        # Define counter and settings for each thread
        line_points = [(0, 900), (3000, 900)]
        classes_to_count = list(range(100))
        counter = solutions.ObjectCounter(
            view_img=False,
            reg_pts=line_points,
            names=model.names,
            draw_tracks=False,
            region_thickness=4,
            count_reg_color=(255, 233, 203),
        )

        cap = initialize_video_capture(camera_url)
        if not cap:
            print(f"Failed to initialize video for {camera_url}")
            return

        print(f"Processing video from {camera_url}")

        while processing_flags[camera_url] and cap.isOpened():
            success, im0 = cap.read()
            if not success:
                print(f"Video stream from {camera_url} is empty or done.")
                cap.release()
                cap = initialize_video_capture(camera_url)
                continue

            # Run YOLO tracking and counting for the camera thread
            tracks = model.track(im0, persist=True, show=False, classes=classes_to_count)
            im0 = counter.start_counting(im0, tracks)

            # Ensure frame queue doesn't overflow, replace oldest frame if full
            if frame_queue.full():
                frame_queue.get()
            frame_queue.put(im0)

        cap.release()

    # Start a unique thread for each camera URL
    for url in camera_urls:
        processing_threads[url] = threading.Thread(target=process_video, args=(url,))
        processing_threads[url].start()


def generate_frames(camera_url):
    """
    Generator function to retrieve the latest frame for each specific camera.
    """
    while processing_flags.get(camera_url, False):
        try:
            # Get the latest frame from the queue for the specified camera URL
            latest_frame = frame_queues[camera_url].get(timeout=1)
        except queue.Empty:
            continue  # Skip if no frame is available

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', latest_frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


class VideoFeed(APIView):
    """
    APIView to return video feed for a specific camera.
    """
    def get(self, request, camera_no = 1):
        # Ensure the URL passed exists in the processing threads
        print(str(camera_no).isnumeric() )
        if ( not str(camera_no).isnumeric() ):
            return Response({"error": "Bad Request"}, status=400)

        cameraNo = int(camera_no)

        if cameraNo >= len(camera_urls) or  camera_urls[cameraNo] not in camera_urls:
            return Response({"error": "Camera URL not found" }, status=404)

        # Stream the frames for the requested camera
        return StreamingHttpResponse(
            generate_frames(camera_urls[cameraNo]),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )


# Route this in your urls.py as well
