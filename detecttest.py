# hal_braille_picamera2_stable.py
import time
import threading
from collections import defaultdict, deque
import numpy as np
import cv2
from picamera2 import Picamera2
from scipy.optimize import linear_sum_assignment
import os

# -------------------------
# Config / Tunables
# -------------------------
CAM_SIZE = (640, 480)
MIN_BLOB_AREA = 5
MAX_BLOB_AREA = 300
MIN_CIRCULARITY = 0.68
CONNECT_SPACING_FACTOR = 1.8
PADDING = 6
STABILIZE_FRAMES = 7
WEIGHT_NEW = 0.6  # weight for newest frame in averaging
TEMP_INTERVAL = 3  # seconds for temperature logging

# -------------------------
# Simple in-process pub/sub
# -------------------------
subscribers = defaultdict(list)
def publish(topic, data):
    for cb in list(subscribers[topic]):
        try:
            cb(data)
        except Exception as e:
            print("Subscriber error:", e)
def subscribe(topic, cb):
    subscribers[topic].append(cb)

# -------------------------
# ArUco setup
# -------------------------
aruco = None
aruco_dict = None
aruco_params = None
try:
    aruco = cv2.aruco
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    aruco_params = aruco.DetectorParameters_create()
    print("ArUco available: DICT_4X4_50")
except Exception:
    print("ArUco not available, skipping marker detection.")

# -------------------------
# Blob detector
# -------------------------
def make_blob_detector():
    params = cv2.SimpleBlobDetector_Params()
    params.filterByArea = True
    params.minArea = MIN_BLOB_AREA
    params.maxArea = MAX_BLOB_AREA
    params.filterByCircularity = True
    params.minCircularity = MIN_CIRCULARITY
    params.filterByConvexity = True
    params.minConvexity = 0.7
    params.filterByInertia = True
    params.minInertiaRatio = 0.4
    params.filterByColor = False
    return cv2.SimpleBlobDetector_create(params)

blob_detector = make_blob_detector()

# -------------------------
# Braille detection
# -------------------------
def detect_braille_clusters(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    th = cv2.adaptiveThreshold(blur, 255,
                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    keypoints = blob_detector.detect(th)
    clusters = []
    coords = np.array([kp.pt for kp in keypoints], dtype=np.float32)
    n = len(coords)
    if n == 0:
        return clusters, keypoints
    # pairwise distance
    diff = coords[:, None, :] - coords[None, :, :]
    distmat = np.hypot(diff[...,0], diff[...,1])
    np.fill_diagonal(distmat, np.inf)
    nearest = np.min(distmat, axis=1)
    median_spacing = float(np.median(nearest))
    if median_spacing == 0 or np.isnan(median_spacing):
        median_spacing = 10
    conn_thresh = median_spacing * CONNECT_SPACING_FACTOR
    # simple union-find
    parent = list(range(n))
    def uf_find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def uf_union(a,b):
        ra, rb = uf_find(a), uf_find(b)
        if ra != rb:
            parent[rb] = ra
    for i in range(n):
        for j in range(i+1, n):
            if distmat[i,j] <= conn_thresh:
                uf_union(i,j)
    groups = {}
    for i in range(n):
        root = uf_find(i)
        groups.setdefault(root, []).append(i)
    for inds in groups.values():
        pts = coords[inds]
        if len(pts) > 6:
            continue
        x,y,w,h = cv2.boundingRect(pts.astype(np.int32))
        cx, cy = int(np.mean(pts[:,0])), int(np.mean(pts[:,1]))
        clusters.append({"indices": inds,"bbox":(x,y,w,h),"center":(cx,cy),"pts":pts})
    return clusters, keypoints

# -------------------------
# Hungarian stabilization
# -------------------------
class Stabilizer:
    def __init__(self, maxlen=STABILIZE_FRAMES, weight_new=WEIGHT_NEW):
        self.history = deque(maxlen=maxlen)
        self.weight_new = weight_new

    def update(self, clusters):
        stabilized = []
        if not self.history:
            for c in clusters:
                stabilized.append(c)
            self.history.append(clusters)
            return stabilized
        prev = self.history[-1]
        if not prev:
            self.history.append(clusters)
            return clusters
        # cost matrix: distance between previous centers and current
        cost = np.zeros((len(prev), len(clusters)), dtype=np.float32)
        for i,p in enumerate(prev):
            for j,c in enumerate(clusters):
                dx = p["center"][0] - c["center"][0]
                dy = p["center"][1] - c["center"][1]
                cost[i,j] = np.hypot(dx,dy)
        row_ind, col_ind = linear_sum_assignment(cost)
        assigned = set()
        for r,cj in zip(row_ind, col_ind):
            prev_cluster = prev[r]
            new_cluster = clusters[cj]
            # weighted average
            new_cx = int(prev_cluster["center"][0]*(1-self.weight_new)+new_cluster["center"][0]*self.weight_new)
            new_cy = int(prev_cluster["center"][1]*(1-self.weight_new)+new_cluster["center"][1]*self.weight_new)
            new_x = int(prev_cluster["bbox"][0]*(1-self.weight_new)+new_cluster["bbox"][0]*self.weight_new)
            new_y = int(prev_cluster["bbox"][1]*(1-self.weight_new)+new_cluster["bbox"][1]*self.weight_new)
            new_w = int(prev_cluster["bbox"][2]*(1-self.weight_new)+new_cluster["bbox"][2]*self.weight_new)
            new_h = int(prev_cluster["bbox"][3]*(1-self.weight_new)+new_cluster["bbox"][3]*self.weight_new)
            stabilized.append({"indices":new_cluster["indices"],"bbox":(new_x,new_y,new_w,new_h),"center":(new_cx,new_cy),"pts":new_cluster["pts"]})
            assigned.add(cj)
        # add unmatched clusters as new
        for i,c in enumerate(clusters):
            if i not in assigned:
                stabilized.append(c)
        self.history.append(stabilized)
        return stabilized

stabilizer = Stabilizer()

# -------------------------
# Draw clusters
# -------------------------
def draw_clusters(frame, clusters, keypoints):
    annotated = frame.copy()
    for cluster in clusters:
        x,y,w,h = cluster["bbox"]
        cv2.rectangle(annotated, (x,y), (x+w,y+h), (0,255,255),2)
        cv2.putText(annotated, "Braille", (x, max(10,y-8)), cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
        for idx in cluster["indices"]:
            k = keypoints[idx]
            px, py = int(k.pt[0]), int(k.pt[1])
            rr = max(1,int(k.size/2))
            cv2.circle(annotated, (px,py), rr, (0,180,0), -1)
    return annotated

# -------------------------
# ArUco detection
# -------------------------
def detect_aruco_and_annotate(frame, draw=True):
    markers=[]
    if aruco is None:
        return markers, frame
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    try:
        corners, ids, _=aruco.detectMarkers(gray,aruco_dict,parameters=aruco_params)
    except Exception:
        corners, ids=[], None
    if ids is not None and len(ids)>0:
        aruco.drawDetectedMarkers(frame,corners,ids)
        for idx,c in enumerate(corners):
            pts=c[0].astype(int)
            center=tuple(np.mean(pts,axis=0).astype(int))
            id_val=int(ids[idx][0]) if hasattr(ids[idx],"__len__") else int(ids[idx])
            markers.append({"id":id_val,"pos":center})
            if draw:
                cv2.putText(frame,f"ID {id_val}",(center[0]+10,center[1]),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,0,0),2)
    return markers, frame

# -------------------------
# Stage2 stub
# -------------------------
def braille_recognizer_stub(frame):
    return ["A","B","C"]

def on_candidate_frame(frame):
    labels = braille_recognizer_stub(frame)
    publish("braille/labels",labels)

subscribe("braille/candidate_frame",on_candidate_frame)

# -------------------------
# Temperature logging
# -------------------------
def log_temperature():
    last_time=0
    while True:
        t=time.time()
        if t-last_time>=TEMP_INTERVAL:
            last_time=t
            temp=0
            try:
                with open("/sys/class/thermal/thermal_zone0/temp","r") as f:
                    temp=int(f.read())/1000
                print(f"🌡️ CPU Temp: {temp:.1f}°C")
            except Exception:
                pass
        time.sleep(0.5)

# -------------------------
# Camera loop
# -------------------------
def camera_loop():
    picam2=Picamera2()
    config=picam2.create_preview_configuration(main={"format":"BGR888","size":CAM_SIZE})
    picam2.configure(config)
    picam2.start()
    print("Camera started")
    while True:
        frame=picam2.capture_array()
        clusters,keypoints=detect_braille_clusters(frame)
        stable_clusters=stabilizer.update(clusters)
        annotated=draw_clusters(frame,stable_clusters,keypoints)
        publish("braille/presence", bool(stable_clusters))
        for cluster in stable_clusters:
            x,y,w,h=cluster["bbox"]
            x0=max(0,x-PADDING); y0=max(0,y-PADDING)
            x1=min(frame.shape[1],x+w+PADDING); y1=min(frame.shape[0],y+h+PADDING)
            crop=frame[y0:y1,x0:x1].copy()
            publish("braille/candidate_frame",crop)
        markers, annotated=detect_aruco_and_annotate(annotated,draw=True)
        publish("aruco/markers",markers)
        cv2.imshow("HAL Preview", annotated)
        if cv2.waitKey(1) & 0xFF==ord('q'):
            break
    picam2.stop()
    cv2.destroyAllWindows()

# -------------------------
# Logging subscribers
# -------------------------
def log_presence(flag):
    print("📌 Braille Presence:", flag)
def log_labels(labels):
    print("🔠 Braille Labels:", labels)
def log_markers(markers):
    if markers: print("🎯 ArUco Markers:",markers)

subscribe("braille/presence",log_presence)
subscribe("braille/labels",log_labels)
subscribe("aruco/markers",log_markers)

# -------------------------
# Main
# -------------------------
if __name__=="__main__":
    t_temp=threading.Thread(target=log_temperature,daemon=True)
    t_temp.start()
    t_cam=threading.Thread(target=camera_loop,daemon=True)
    t_cam.start()
    try:
        while t_cam.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Exiting...")
