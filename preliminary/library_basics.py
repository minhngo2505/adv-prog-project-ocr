"""A basic introduction to Open CV
***  myk's copy, cloned 28/10/2025, for project.

Instructions
------------
Implement the functions below based on their docstrings.

Notice some docstrings include references to third-party documentation
Some docstrings **require** you to add references to third-party documentation.

Make sure you read the docstrings C.A.R.E.F.U.L.Y (yes, I took the L to check that you are awake!)
"""

# imports - add all required imports here
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

VID_PATH = Path("../resources/oop.mp4")
OUT_PATH = Path("..")

class CodingVideo:
    capture: cv2.VideoCapture

    def __init__(self, video: Path | str):
        self.capture = cv2.VideoCapture(video)
        if not self.capture.isOpened():
            raise ValueError(f"Cannot open {video}")

        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps


    def __str__(self) -> str:
        """Displays key metadata from the video
            FPS - Number of frames per second rounded to two decimal points
            FRAME COUNT - The total number of frames in the video
            DURATION (minutes) - Calculated total duration of the video given FPS and FRAME COUNT

        Reference:         https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html#gaeb8dd9c89c10a5c63c139bf7c4f5704d
        """
        mins, secs = divmod(self.duration, 60)
        return f"({self.fps:.2f}fps, {self.frame_count} frames, {mins:.0f}m{round(secs):02.0f}s)"

    def get_frame_number_at_time(self, seconds: int) -> int:
        """Given a time in seconds, returns the value of the nearest frame"""
        return round(self.fps * seconds)

    def get_frame_rgb_array(self, frame_number: int) -> np.ndarray:
        """Returns a numpy N-dimensional array (ndarray)
        The array represents the RGB values of each pixel in a given frame
        Note: cv2 defaults to BGR format, so this function converts the color space to RGB
        """
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)  # jump to the frame
        ret, frame_bgr = self.capture.read()
        if not ret:
            raise Exception("Error: Could not read the frame.")
        # convert colourspace
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def get_image_as_bytes(self, seconds: int) -> bytes:
        """
        what is this for? alternative example???? Not used yet.
        """
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, self.get_frame_number_at_time(seconds))
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise ValueError("Invalid frame in target location")
        ok, buf = cv2.imencode(".png", frame)
        if not ok:
            raise ValueError("Failed to encode frame")
        return buf.tobytes()

    def save_as_image(self, seconds: int, output_path: Path | str = 'output.png') -> None:
      """Saves the given frame as a png image
       calculates frame number, extracts it as RGB using above f'n, save as PNG with PIL.
      """
      # resolve 2 types of output name. If path is string, assume relative path.
      if type(output_path) is str:
          output_path = OUT_PATH/output_path
      frame_number = self.get_frame_number_at_time(seconds)
      frame = self.get_frame_rgb_array(frame_number)

      # cv2.imwrite( "cv2.png", frame )   # assumes BGR.
      pillow_image = Image.fromarray(frame)
      pillow_image.save(output_path)

def test():
    """Try out your class here"""
    oop = CodingVideo(VID_PATH)
    print(oop)
    oop.save_as_image(42)

if __name__ == '__main__':
    test()
