"""Provides a simple API for your basic OCR client
***  myk's copy, cloned 28/10/2025, for project.

Drive the API to complete "interprocess communication"
Requirements
"""
from fastapi import FastAPI, HTTPException
from fastapi import File, UploadFile
from fastapi import Response
from pydantic import BaseModel
from pathlib import Path
from preliminary.library_basics import CodingVideo, CodingFrame
app = FastAPI()

# We'll create a lightweight "database" for our videos
# You can add uploads later (not required for assessment)
# For now, we will just hardcode are samples
VIDEOS: dict[str, Path] = {
    "demo": Path("resources/oop.mp4")
}

class VideoMetaData(BaseModel):
    fps: float
    frame_count: int
    duration_seconds: float
    _links: dict | None = None

@app.get("/video")
def list_videos():
    """List all available videos with HATEOAS-style links."""
    return {
        "count": len(VIDEOS),
        "videos": [
            {
                "id": vid,
                "path": str(path), # Not standard for debug only
                "_links": {
                    "self": f"/video/{vid}",
                    "frame_example": f"/video/{vid}/frame/1.0"
                }
            }
            for vid, path in VIDEOS.items()
        ]
    }

def _open_vid_or_404(vid: str) -> CodingVideo:
    path = VIDEOS.get(vid)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Video '{path}' not found")
    try:
        return CodingVideo(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Could not open video {e}")

def _meta(video: CodingVideo) -> VideoMetaData:
    return VideoMetaData(
            fps=video.fps,
            frame_count=video.frame_count,
            duration_seconds=video.duration
    )


@app.get("/video/{vid}", response_model=VideoMetaData)
def video(vid: str):
    coding_video = _open_vid_or_404(vid)
    try:
            meta = _meta(coding_video)
            meta._links = {
                "self": f"/video/{vid}",
                "frames": f"/video/{vid}/frame/{{seconds}}"
            }
            return meta
    finally:
        coding_video.capture.release()


@app.get("/video/{vid}/frame/{timestamp}", response_class=Response)
def video_frame(vid: str, timestamp: float):
    """
    vid: name of video as returned by /video endpoint
    timestamp:  in seconds, to find frame
    returns a PNG frame. (not json)
    """
    try:
        coding_video = _open_vid_or_404(vid)
        return Response(content=coding_video.get_image_as_bytes(timestamp), media_type="image/png")
    finally:
        coding_video.capture.release()


@app.get("/video/{vid}/frame/{t}/ocr")
def video_frame_ocr(vid: str, t: float):
    """
    returns a string (as application/json) with the OCR text from the frame at specified time
    """
    try:
        coding_video = _open_vid_or_404(vid)
        return coding_video.get_text_from_time(t)
    finally:
        coding_video.capture.release()

@app.post("/frame/ocr")
async def upload_frame_ocr(file:UploadFile = File(...)):
    # Check filename/type
    if file.content_type != "image/png":
        return {"error": "Only PNG images are allowed."}

    # Read the bytes from the uploaded file
    image_bytes = await file.read()
    return CodingFrame(image_bytes).ocr()


