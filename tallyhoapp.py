from PIL import Image
from PIL import ImageTk
from scipy.spatial import distance as dist
import tkinter as tki
import threading
from imutils import perspective
from imutils import contours
import imutils
import numpy as np
import cv2

class TallyhoApp:
    def __init__(self, videoStream):
        self.videoStream = videoStream
        self.frame = None
        self.thread = None
        self.stopEvent = None
        self.updatePPM = False
        self.calibrationWidth = None
        self.pixelsPerMetric = 40 # Initialize to anything, really...

        self.root = tki.Tk()
        self.panel = None

        bottomPanel = tki.Frame(self.root)
        bottomPanel.pack(side="bottom", fill="both", expand="yes", padx=0, pady=10)

        lbl = tki.Label(bottomPanel, text="Calibration width (in inches)")
        lbl.pack(side="left", padx=10, pady=0)
        
        self.calibrationWidthEntry = tki.Entry(bottomPanel, justify="right", width=5)
        self.calibrationWidthEntry.pack(side="left", padx=0, pady=0)
        
        btn = tki.Button(bottomPanel, text="Set Calibration", command=self.calibrate)
        btn.pack(side="left", padx=10, pady=0)

        self.stopEvent = threading.Event()
        self.thread = threading.Thread(target=self.videoLoop, args=())
        self.thread.start()

        self.root.wm_title("Tallyho!")
        self.root.wm_protocol("WM_DELETE_WINDOW", self.onClose)

    def videoLoop(self):
        try:
            while not self.stopEvent.is_set():
                self.frame = self.videoStream.read()
                self.frame = imutils.resize(self.frame, width=800)

                self.drawOverlay()

                image = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(image)
                image = ImageTk.PhotoImage(image)

                if self.panel is None:
                    self.panel = tki.Label(image=image)
                    self.panel.image = image
                    self.panel.pack(side="left", padx=10, pady=10)
                else:
                    self.panel.configure(image=image)
                    self.panel.image = image

        except RuntimeError:
            print("[INFO] Caught a RuntimeError")

    def midpoint(self, ptA, ptB):
        return ((ptA[0] + ptB[0]) * 0.5, (ptA[1] + ptB[1]) * 0.5)

    def drawOverlay(self):
        # Get a single frame, do all calculations, and draw the overlays of measurements
        self.overlay = self.frame.copy()
        opacity = 0.5
        
        # Our operations on the frame come here
        gray = cv2.cvtColor(self.overlay, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        edged = cv2.Canny(gray, 50, 100)
        edged = cv2.dilate(edged, None, iterations=1)
        edged = cv2.erode(edged, None, iterations=1)

        cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if imutils.is_cv2() else cnts[1]

        # sort the contours from left-to-right and initialize the
        # 'pixels per metric' calibration variable if necessary
        if len(cnts) > 1:
            (cnts, _) = contours.sort_contours(cnts)
            if self.updatePPM:
                self.pixelsPerMetric = None
                self.updatePPM = False

        for c in cnts:
            # if the contour is not sufficiently large, ignore it
            if cv2.contourArea(c) < 100:
                continue

            # compute the rotated bounding box of the contour
            box = cv2.minAreaRect(c)
            box = cv2.cv.BoxPoints(box) if imutils.is_cv2() else cv2.boxPoints(box)
            box = np.array(box, dtype="int")

            # order the points in the contour such that they appear
            # in top-left, top-right, bottom-right, and bottom-left
            # order, then draw the outline of the rotated bounding
            # box
            box = perspective.order_points(box)
            cv2.drawContours(self.overlay, [box.astype("int")], -1, (0, 255, 0), 2)

            # loop over the original points and draw them
            for (x, y) in box:
                cv2.circle(self.overlay, (int(x), int(y)), 5, (0, 0, 255), -1)

            # unpack the ordered bounding box, then compute the midpoint
            # between the top-left and top-right coordinates, followed by
            # the midpoint between bottom-left and bottom-right coordinates
            (tl, tr, br, bl) = box
            (tltrX, tltrY) = self.midpoint(tl, tr)
            (blbrX, blbrY) = self.midpoint(bl, br)

            # compute the midpoint between the top-left and top-right points,
            # followed by the midpoint between the top-righ and bottom-right
            (tlblX, tlblY) = self.midpoint(tl, bl)
            (trbrX, trbrY) = self.midpoint(tr, br)

            # draw the midpoints on the image
            cv2.circle(self.overlay, (int(tltrX), int(tltrY)), 5, (255, 0, 0), -1)
            cv2.circle(self.overlay, (int(blbrX), int(blbrY)), 5, (255, 0, 0), -1)
            cv2.circle(self.overlay, (int(tlblX), int(tlblY)), 5, (255, 0, 0), -1)
            cv2.circle(self.overlay, (int(trbrX), int(trbrY)), 5, (255, 0, 0), -1)

            # draw lines between the midpoints
            cv2.line(self.overlay, (int(tltrX), int(tltrY)), (int(blbrX), int(blbrY)), (255, 0, 255), 2)
            cv2.line(self.overlay, (int(tlblX), int(tlblY)), (int(trbrX), int(trbrY)), (255, 0, 255), 2)

            # compute the Euclidean distance between the midpoints
            dA = dist.euclidean((tltrX, tltrY), (blbrX, blbrY))
            dB = dist.euclidean((tlblX, tlblY), (trbrX, trbrY))

            # if the pixels per metric has not been initialized, then
            # compute it as the ratio of pixels to supplied metric
            # (in this case, inches)
            if self.pixelsPerMetric is None:
                self.pixelsPerMetric = dB / self.calibrationWidth

            # compute the size of the object
            dimA = dA / self.pixelsPerMetric
            dimB = dB / self.pixelsPerMetric

            # draw the object sizes on the image
            #cv2.putText(self.overlay, "{:.3f}in".format(dimA), (int(tltrX - 15), int(tltrY - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            #cv2.putText(self.overlay, "{:.3f}in".format(dimB), (int(trbrX + 10), int(trbrY)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            cv2.putText(self.overlay, "{:.4f}ft".format(dimB), (int(trbrX + 10), int(trbrY)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # source1 = overlay, source2 = frame, destination = frame
        cv2.addWeighted(self.overlay, opacity, self.frame, 1 - opacity, 0, self.frame)

    def onClose(self):
        print("[INFO] Closing...")
        self.stopEvent.set()
        self.videoStream.stop()
        self.root.quit()

    def calibrate(self):
        enteredValue = self.calibrationWidthEntry.get()
        print("Entered: " + enteredValue)
        if enteredValue:
            self.calibrationWidth = float(enteredValue)
            self.updatePPM = True
            print("Calibration width set: " + str(self.calibrationWidth))
        else:
            print("Nothing entered.")
