from tallyhoapp import TallyhoApp
from imutils.video import VideoStream
import time

vs = VideoStream(2).start()
# It needs to initialize or else the GUI will not render correctly.
time.sleep(2.0)

# Start our app/ui
app = TallyhoApp(vs)
app.root.mainloop()
