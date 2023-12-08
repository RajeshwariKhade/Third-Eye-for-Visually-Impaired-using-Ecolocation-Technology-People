######## Webcam Object Detection Using Tensorflow-trained Classifier #########
#
# Author: Dhananjay Khairnnar
# Date: 16/05/2023
# Email: khairnardm@gmail.com
# Country: India
# github: http://www.github.com/8-DK
##############################################################################

# Import packages
import os
import argparse
import cv2
import numpy as np
import sys
import time
from threading import Thread
import importlib.util
from flask import Flask,render_template,request,jsonify
import threading
import InputHlpr
import OutputHlpr
import RPi.GPIO as GPIO
import time
import json
import pyttsx3  
import queue
from multiprocessing import Process

#initialize fask app
app = Flask(__name__,
        static_url_path='', 
        static_folder='static',
        template_folder='templates')

#initialize sensor instances            
ultrSndSnsr = InputHlpr.UltraSonicSensor();
btn = InputHlpr.Button()
buzr = OutputHlpr.Buzzer()

#initialize data queue
dataQueue = queue.Queue(maxsize=1)
serverDataQueue = queue.Queue(maxsize=1)
lastDateRetrive = time.time()

#initialize audio engine in hndi language need UTF-8 charectors only
engine = pyttsx3.init()
engine.setProperty('voice', 'hindi')
engine.setProperty("rate", 150)
engine.say('Vision starting.')
engine.runAndWait()

#global variable for carry data out for server 
srvrData = "{\"distance\":187.88,\"button\":\"Off\",\"buzzer\":\"Off\",\"car\":0,\"chair\":0,\"mouse\":0,\"person\":0}"

####################Flash events/routes for handle URL##################
@app.route('/getData', methods=['GET'])
def get_data():
    global lastDateRetrive
    global srvrData
    m_jsonOutPut = srvrData
    #lastDateRetrive = time.time()
    print("Server : ",m_jsonOutPut)  
    return m_jsonOutPut
    
@app.route('/getLogin', methods=['POST'])
def get_login():
    data = request.get_json()
    print(data)
    print(data['user']," ",data['pass'])
    if(data['user'] == "admin" and data['pass'] == "admin@123"):
        print("Login Success !!!")
        return render_template('dash.html') #return dhashboard if login ok
        
    if(data['user'] == "Admin" and data['pass'] == "admin@123"):
        print("Login Success !!!")
        return render_template('dash.html') #return dhashboard if login ok
        
    return render_template('index.html') #return login page if login not ok
    
@app.route('/setPeripheral', methods=['POST'])
def set_peripheral():
    global buzr
    data = request.get_json()
    print(data)    
    if(data['buzzer'] == "On"):
        buzr.buzzerOn()        
    else:
        buzr.buzzerOff()
    
    return "OK"
    
   
@app.route('/')
def index():
    #get static page from template folder
    return render_template('index.html') 

########################################################################

# Define VideoStream class to handle streaming of video from webcam in separate processing thread
# Source - Adrian Rosebrock, PyImageSearch: https://www.pyimagesearch.com/2015/12/28/increasing-raspberry-pi-fps-with-python-and-opencv/
class VideoStream:
    """Camera object that controls video streaming from the Picamera"""
    def __init__(self,resolution=(256,256),framerate=30):
        # Initialize the PiCamera and the camera image stream
        self.stream = cv2.VideoCapture(0)
        ret = self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        ret = self.stream.set(3,resolution[0])
        ret = self.stream.set(4,resolution[1])
            
        # Read first frame from the stream
        (self.grabbed, self.frame) = self.stream.read()

	# Variable to control when the camera is stopped
        self.stopped = False

    def start(self):
	# Start the thread that reads frames from the video stream
        Thread(target=self.update,args=()).start()
        return self

    def update(self):
        # Keep looping indefinitely until the thread is stopped
        while True:
            # If the camera is stopped, stop the thread
            if self.stopped:
                # Close camera resources
                self.stream.release()
                return

            # Otherwise, grab the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
	# Return the most recent frame
        return self.frame

    def stop(self):
	# Indicate that the camera and thread should be stopped
        self.stopped = True

# Define and parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('--modeldir', help='Folder the .tflite file is located in',
                    required=True)
parser.add_argument('--graph', help='Name of the .tflite file, if different than detect.tflite',
                    default='detect.tflite')
parser.add_argument('--labels', help='Name of the labelmap file, if different than labelmap.txt',
                    default='labelmap.txt')
parser.add_argument('--threshold', help='Minimum confidence threshold for displaying detected objects',
                    default=0.5)
parser.add_argument('--resolution', help='Desired webcam resolution in WxH. If the webcam does not support the resolution entered, errors may occur.',
                    default='1280x720')
parser.add_argument('--edgetpu', help='Use Coral Edge TPU Accelerator to speed up detection',
                    action='store_true')

args = parser.parse_args()

#mainLoopt handles object detection and update data Queue for further process
def mainLoop(mdataQueue):
    MODEL_NAME = args.modeldir
    GRAPH_NAME = args.graph
    LABELMAP_NAME = args.labels
    min_conf_threshold = float(args.threshold)
    resW, resH = args.resolution.split('x')
    imW, imH = int(resW), int(resH)
    use_TPU = args.edgetpu

    # Import TensorFlow libraries
    # If tflite_runtime is installed, import interpreter from tflite_runtime, else import from regular tensorflow
    # If using Coral Edge TPU, import the load_delegate library
    pkg = importlib.util.find_spec('tflite_runtime')
    if pkg:
        from tflite_runtime.interpreter import Interpreter
        if use_TPU:
            from tflite_runtime.interpreter import load_delegate
    else:
        from tensorflow.lite.python.interpreter import Interpreter
        if use_TPU:
            from tensorflow.lite.python.interpreter import load_delegate

    # If using Edge TPU, assign filename for Edge TPU model
    if use_TPU:
        # If user has specified the name of the .tflite file, use that name, otherwise use default 'edgetpu.tflite'
        if (GRAPH_NAME == 'detect.tflite'):
            GRAPH_NAME = 'edgetpu.tflite'       

    # Get path to current worknowqing directory
    CWD_PATH = os.getcwd()

    # Path to .tflite file, which contains the model that is used for object detection
    PATH_TO_CKPT = os.path.join(CWD_PATH,MODEL_NAME,GRAPH_NAME)

    # Path to label map file
    PATH_TO_LABELS = os.path.join(CWD_PATH,MODEL_NAME,LABELMAP_NAME)

    # Load the label map
    with open(PATH_TO_LABELS, 'r') as f:
        labels = [line.strip() for line in f.readlines()]

    # Have to do a weird fix for label map if using the COCO "starter model" from
    # https://www.tensorflow.org/lite/models/object_detection/overview
    # First label is '???', which has to be removed.
    if labels[0] == '???':
        del(labels[0])

    # Load the Tensorflow Lite model.
    # If using Edge TPU, use special load_delegate argument
    if use_TPU:
        interpreter = Interpreter(model_path=PATH_TO_CKPT,
                                  experimental_delegates=[load_delegate('libedgetpu.so.1.0')])
        print(PATH_TO_CKPT)
    else:
        interpreter = Interpreter(model_path=PATH_TO_CKPT)

    interpreter.allocate_tensors()

    # Get model details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    height = input_details[0]['shape'][1]
    width = input_details[0]['shape'][2]

    floating_model = (input_details[0]['dtype'] == np.float32)

    input_mean = 127.5
    input_std = 127.5

    # Check output layer name to determine if this model was created with TF2 or TF1,
    # because outputs are ordered differently for TF2 and TF1 models
    outname = output_details[0]['name']

    if ('StatefulPartitionedCall' in outname): # This is a TF2 model
        boxes_idx, classes_idx, scores_idx = 1, 3, 0
    else: # This is a TF1 model
        boxes_idx, classes_idx, scores_idx = 0, 1, 2

    # Initialize frame rate calculation
    frame_rate_calc = 1
    freq = cv2.getTickFrequency()

    # Initialize video stream
    videostream = VideoStream(resolution=(imW,imH),framerate=60).start()
    time.sleep(1)

    #for frame1 in camera.capture_continuous(rawCapture, format="bgr",use_video_port=True):
    while True:
        # Start timer (for calculating frame rate)
        t1 = cv2.getTickCount()

        # Grab frame from video stream
        frame1 = videostream.read()

        # Acquire frame and resize to expected shape [1xHxWx3]
        frame = frame1.copy()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (width, height))
        input_data = np.expand_dims(frame_resized, axis=0)

        # Normalize pixel values if using a floating model (i.e. if model is non-quantized)
        if floating_model:
            input_data = (np.float32(input_data) - input_mean) / input_std

        # Perform the actual detection by running the model with the image as input
        interpreter.set_tensor(input_details[0]['index'],input_data)
        interpreter.invoke()

        # Retrieve detection results
        boxes = interpreter.get_tensor(output_details[boxes_idx]['index'])[0] # Bounding box coordinates of detected objects
        classes = interpreter.get_tensor(output_details[classes_idx]['index'])[0] # Class index of detected objects
        scores = interpreter.get_tensor(output_details[scores_idx]['index'])[0] # Confidence of detected objects
        m_carCount = 0
        m_personCount = 0
        m_chairCount = 0
        m_mouseCount = 0
        # Loop over all detections and draw detection box if confidence is above minimum threshold
        
        for i in range(len(scores)):
            if ((scores[i] > min_conf_threshold) and (scores[i] <= 1.0)):

                # Get bounding box coordinates and draw box
                # Interpreter can return coordinates that are outside of image dimensions, need to force them to be within image using max() and min()
                ymin = int(max(1,(boxes[i][0] * imH)))
                xmin = int(max(1,(boxes[i][1] * imW)))
                ymax = int(min(imH,(boxes[i][2] * imH)))
                xmax = int(min(imW,(boxes[i][3] * imW)))
                
                cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), (10, 255, 0), 2)

                # Draw label
                object_name = labels[int(classes[i])] # Look up object name from "labels" array using class index
                if(object_name == "car"):
                    m_carCount += 1
                elif (object_name == "person"):
                    m_personCount += 1
                elif (object_name == "chair"):
                    m_chairCount += 1
                elif (object_name == "mouse"):
                    m_mouseCount += 1
                 
                label = '%s: %d%%' % (object_name, int(scores[i]*100)) # Example: 'person: 72%'
                labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2) # Get font size
                label_ymin = max(ymin, labelSize[1] + 10) # Make sure not to draw label too close to top of window
                cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), (255, 255, 255), cv2.FILLED) # Draw white box to put label text in
                cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2) # Draw label text
        
        if (m_carCount+m_personCount+m_chairCount+m_mouseCount):
            mdataQueue.put([m_carCount,m_personCount,m_chairCount,m_mouseCount])

        # Draw framerate in corner of frame
        cv2.putText(frame,'FPS: {0:.2f}'.format(frame_rate_calc),(30,50),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,0),2,cv2.LINE_AA)

        # All the results have been drawn on the frame, so it's time to display it.
        cv2.imshow('Object detector', frame)
    
        # Calculate framerate
        t2 = cv2.getTickCount()
        time1 = (t2-t1)/freq
        frame_rate_calc= 1/time1

        # Press 'q' to quit
        if cv2.waitKey(1) == ord('q'):
            break

    # Clean up
    cv2.destroyAllWindows()
    videostream.stop()

#dataUpdateLoop handles reading from sensor and making json for server
#this ffuntion also handle audio response and GPIO peripherals
def dataUpdateLoop(mdataQueue):
    global ultrSndSnsr
    global btn
    global buzr
    global lastDateRetrive
    global srvrData
    global engine

    m_carCount = 0
    m_personCount = 0
    m_chairCount = 0
    m_mouseCount = 0
    
    anounceMentTime = time.time()
    
    #infinite loop for perform sensor task
    while True:
        #read sensor values, ultrasonic sensor needs some time to get data
        distance = float(ultrSndSnsr.distanceMes()) #in cm
        button   = str(btn.readBtn()) #read button is pressed
        buzzer   = str(buzr.getBuzzerStatus()) #check buzzer is on
        #check Objects are detected
        if(not mdataQueue.empty()):
            arrData = mdataQueue.get()
            m_carCount = arrData[0]
            m_personCount = arrData[1]
            m_chairCount = arrData[2]
            m_mouseCount = arrData[3]
        #create json for server data update event
        data = {}
        data['distance'] = distance
        data['button'] = button
        data['buzzer'] = buzzer
        data['car'] = m_carCount
        data['chair'] = m_chairCount
        data['mouse'] = m_mouseCount
        data['person'] = m_personCount
        srvrData = (json.dumps(data))
        now = time.time()
        
        #make audio anouncement after every 3 sec
        if(now - anounceMentTime > 3):
            if (m_carCount+m_chairCount+m_mouseCount+m_personCount):
                strng = "आगे "
                if(m_personCount):
                    strng += str(m_personCount)+' इन्सान'
                if(m_carCount): 
                    strng += ', '
                    strng += str(m_carCount)+' वाहान'
                if(m_chairCount): 
                    strng += ', '
                    strng += str(m_chairCount)+' खुर्ची'
                if(m_mouseCount): 
                    strng += ', '
                    strng += str(m_mouseCount)+' Mouse'
                strng += ' है.'
                                    
                engine.say(strng)
                engine.runAndWait()           
            anounceMentTime = time.time()
        else:
            if(distance < 20): #check is there any obstacle ahed and on buzzer
                buzr.buzzerOn()
                engine.say('आगे रुकावट है.')
                engine.runAndWait()    
            else:
                buzr.buzzerOff()
                
        if(now -lastDateRetrive > 1.2):
            m_carCount = 0
            m_personCount = 0
            m_chairCount = 0
            m_mouseCount = 0
            lastDateRetrive = now
        time.sleep(1)         
    
if __name__ == '__main__':
    #buzr.testBuzzer()
    #btn.testButton()
    #ultrSndSnsr.testSensor()
    #create two threads
    t1 = threading.Thread(target=mainLoop,args=(dataQueue,))
    t2 = threading.Thread(target=dataUpdateLoop,args=(dataQueue,))
    #start two threads
    t1.start()
    t2.start()
    #start flask app
    app.run(debug=True, port=8001, host='0.0.0.0',use_reloader=False)
    #clean threads after program exit
    t1.join()
    t2.join()
    print("cleaning up")
    GPIO.cleanup()
