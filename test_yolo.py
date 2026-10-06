from ultralytics import YOLO

print("Loading model...")
# This will automatically download the model weights on the first run
model = YOLO("yolo11n.pt") 

print("Model successfully loaded!")

