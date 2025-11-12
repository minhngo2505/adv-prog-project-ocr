# Overview

## OCR video player, for TAFE AP 2025-semester 2 project
M.H. J336025.  From 28/10/2025.

Purpose: Create a video player which can run OCR on selected frames, for text-to-voice.
This could be useful to those with limited vision, or even totally blind and using a screen-reader such as JAWS or NVDA.

Server uses fastAPI, allows client to upload a frame for OCR, and get the text back.

Possible Clients
- Web-enabled video player, for local or remote video files, including Youtube.
- An esp32cam based device, which can:
    - take a photo
    - run OCR on the server, 
    - display the text on a small screen
    - read the text aloud using local TTS or web API such as Google
- (stretch goal) a Chrome Extension  


Server Requires:
-    "fastapi[standard]>=0.120.1",
-    "opencv-python>=4.12.0.88",
-    "pillow>=12.0.0",
-    "pytesseract>=0.3.13",
- tesseract binary


Client (Player) requires:
- "pyqt6>=6.10.0"
- "pyqt6-webengine>=6.10.0"
- "python-vlc>=3.0.21203"


## getting started

Download the repo, and run `player/player_qt6.py` .
You should be able to play a local file or URL.

To use the "OCR frame" button, the server must be running
`$ source .venv/bin/activate`
`$ fastapi preliminary/simple_api.py`

## How to contribute

- test the player on Windows, report
- a better OCR engine?  This version of Pytesseract is not great.

### Accessibility
fix tab navigation and shortcuts

### New features:
  - make the time position editable, so user can seek to a given timestamp.

### Bugs:
-  The OCR results need to be de-escaped from JSON to regular strings.  e.g. \" -> " .
    - (I added a line to convert `\n` to newline and remove start and end quotes, but it needs a more complete fix.)
- on Mac, moving window to a different screen breaks the UI display. Should detect this and re-render?

### UI:
- replace button text labels with symbols (play, pause etc), but make sure they have alt-text for screen-readers.
- 
