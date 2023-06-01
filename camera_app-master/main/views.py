from django.http import HttpResponse
from django.shortcuts import render
import cv2                                          # opencv library for image processing tasks
import pyglet.media                                 # for audio playback
from cvzone.FaceMeshModule import FaceMeshDetector  # for landmark detection using the FaceMesh model.
import csv                  
from time import sleep
from django.http import StreamingHttpResponse
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create your views here.
from django.views.decorators import gzip


def index(request):
    return render(request, 'main/index.html')


@gzip.gzip_page
def stream(request):
    try:
        cam = take_video(request)
        return StreamingHttpResponse(gen(cam), content_type="multipart/x-mixed-replace;boundary=frame")
    except:
        pass
    return render(request, 'main/stream.html')


def photo_view(request):
    return render(request, 'main/photo.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')	

def take_video(request):
	cap = cv2.VideoCapture("http://192.168.254.80:4000/video")
	# cap = cv2.VideoCapture(0)   
	# cap = cv2.VideoCapture("0.mp4")                   # Creating a video capture object, which captures video frames from input 
	cap.set(3, 1920)
	cap.set(5, 1084)                            # setting configuration  to capture video frames of size 1920x1024
	detector = FaceMeshDetector(maxFaces=1)     # Creating a FaceMeshDetector object for detecting facial landmarks, and setting the maximum number of faces=1
	breakcount_s, breakcount_y = 0, 0
	counter_s, counter_y = 0, 0
	state_sleep, state_y = False, False
	sound = pyglet.media.load("alarm.wav", streaming=False)     # Loading audio file

	# Alerting when the driver is sleepy or drowsy, count variable is passed as an argument indicating number of times driver has felt drowsy.
	def alert(count):
		cv2.rectangle(img, (700, 20), (1250, 80), (0, 0, 255), cv2.FILLED)
		cv2.putText(img, f"Sleep Alert!! times- {count}", (710, 60),
					cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 2)
		
	# Alerting when the there is no input face detected.
	def alert_no_face():
		cv2.rectangle(img, (700, 20), (1250, 80), (0, 0, 255), cv2.FILLED)
		cv2.putText(img, f"Face not present", (710, 60),
					cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 2)
		
	# Alerting when the number of sleep detections increased safety values.
	def check_count_alert(count):
		if(count>3):
			cv2.rectangle(img, (0, 0), (1250, 80), (0, 0, 255), cv2.FILLED)
			cv2.putText(img, f"Critical Drowsiness Risk, please refrain from driving", (0, 60),
			cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)

	def recordData(condition):
		file = open("database.csv", "a", newline="")
		now = datetime.now()
		dtString = now.strftime("%d-%m-%Y %H:%M:%S")
		tuple = (dtString, condition)
		writer = csv.writer(file)
		writer.writerow(tuple)
		file.close()

	while True:
		success, img = cap.read() # reading a frame from the video capture device, success=success variable indicates whether a frame was successfully read or not, 
		img = cv2.flip(img, 1)    # flipping the image  

		img, faces = detector.findFaceMesh(img, draw=False)  # detect facial landmarks in current frame returns the annotated image with facial landmarks and a list of faces detected in the image

		# if we are not able to detect any faces, we raise an alert
		if not faces:
			sound.play()
			alert_no_face()

		if faces:
			face = faces[0]         #capturing the first face
			eyeLeft = [27, 23, 130, 243]  # up, down, left, right (region of interests for corresponding eye vertices)
			eyeRight = [257, 253, 463, 359]  # up, down, left, right
			mouth = [11, 16, 57, 287]  # up, down, left, right
			faceId = [27, 23, 130, 243, 257, 253, 463, 359, 11, 16, 57, 287] #for tagging region of interests

			#calculate the vertical and horizontal distances between two points on the left eye region of the face.
			eyeLeft_ver, _ = detector.findDistance(face[eyeLeft[0]], face[eyeLeft[1]])
			eyeLeft_hor, _ = detector.findDistance(face[eyeLeft[2]], face[eyeLeft[3]])
			eyeLeft_ratio = int((eyeLeft_ver/eyeLeft_hor )*100)

			# calculate the vertical and horizontal distances between two points on the right eye region of the face.
			eyeRight_ver, _ = detector.findDistance(face[eyeRight[0]], face[eyeRight[1]])
			eyeRight_hor, _ = detector.findDistance(face[eyeRight[2]], face[eyeRight[3]])
			eyeRight_ratio = int((eyeRight_ver / eyeRight_hor) * 100)

			# calculate mouth distance ratio
			mouth_ver, _ = detector.findDistance(face[mouth[0]], face[mouth[1]])
			mouth_hor, _ = detector.findDistance(face[mouth[2]], face[mouth[3]])
			mouth_ratio = int((mouth_ver / mouth_hor) * 100)

			#display text on image
			cv2.rectangle(img, (30,20), (400,150), (0,255,255))
			cv2.putText(img, f'Eye Left Ratio: {eyeLeft_ratio}', (50, 60),
						cv2.FONT_HERSHEY_PLAIN, 2, (255,0,0), 2)
			cv2.putText(img, f'Eye Right Ratio: {eyeRight_ratio}', (50, 100),
						cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)
			
			cv2.putText(img, f'Eye Mouth Ratio: {mouth_ratio}', (50, 140),
                        cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)

			cv2.rectangle(img, (30, 200), (350, 300), (255,0,0))
			cv2.putText(img, f'Sleep Count: {counter_s}', (40, 240),
						cv2.FONT_HERSHEY_PLAIN, 2, (255,0,255), 2)
			cv2.putText(img, f'Yawn Count: {counter_y}', (40, 280),
						cv2.FONT_HERSHEY_PLAIN, 2, (255,0,255), 2)


			#------------------------Eye-----------------------------

			if eyeLeft_ratio <= 50 and eyeRight_ratio <= 50: 
				breakcount_s += 1
				if breakcount_s >= 30:                      # we check eyes closed for 30 frames , and if it is more than that we alert the driver
					alert(counter_s)
					check_count_alert(counter_s)
					if state_sleep == False:
						counter_s += 1
						sound.play()
						recordData("Sleep")
						state_sleep = not state_sleep
			else:
				breakcount_s = 0
				if state_sleep:
					state_sleep = not state_sleep

			# ------------------------Mouth-----------------------------
			if mouth_ratio > 40:
				breakcount_y += 1
				if breakcount_y >= 30:
					alert(counter_y)
					check_count_alert(counter_y)
					if state_y == False:
						counter_y += 1
						sound.play()
						recordData("Yawn")
						state_y = not state_y
			else:
				breakcount_y = 0
				if state_y:
					state_y = not state_y	


			for id in faceId:
				cv2.circle(img,face[id], 5, (0,0,255), cv2.FILLED)


		cv2.imshow("Image", img)
		cv2.waitKey(1)
