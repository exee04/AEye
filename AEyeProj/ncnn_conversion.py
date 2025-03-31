from ultralytics import YOLO

model = YOLO("yolov5x.pt")

model.export(format="ncnn")