import time
import cv2
import torch
from ultralytics import YOLO

# Load YOLOv8 model
model = YOLO("yolov8.yaml")  # Replace with your actual model path
results = model.train(data="/home/ky/AEye/AEyeProj/BrailleDetect/data.yaml", epochs=100, imgsz=640)


