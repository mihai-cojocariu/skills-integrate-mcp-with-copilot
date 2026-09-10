"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import json
import os
import secrets
import base64
import hashlib
import hmac
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "mergington-development-secret").encode()
TEACHER_COOKIE = "mergington_teacher"

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}

TEACHERS_FILE = Path(__file__).with_name("teachers.json")


def load_teachers():
    with TEACHERS_FILE.open(encoding="utf-8") as teachers_file:
        return json.load(teachers_file)


def require_teacher(request: Request):
    teacher_username = get_teacher_from_cookie(request)
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return teacher_username


def make_teacher_cookie(username: str):
    encoded_username = base64.urlsafe_b64encode(username.encode()).decode()
    signature = hmac.new(SESSION_SECRET, encoded_username.encode(), hashlib.sha256).hexdigest()
    return f"{encoded_username}.{signature}"


def get_teacher_from_cookie(request: Request):
    cookie = request.cookies.get(TEACHER_COOKIE, "")
    try:
        encoded_username, signature = cookie.split(".", 1)
        expected_signature = hmac.new(
            SESSION_SECRET, encoded_username.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        return base64.urlsafe_b64decode(encoded_username).decode()
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/auth/me")
def get_auth_status(request: Request):
    teacher_username = get_teacher_from_cookie(request)
    return {
        "authenticated": teacher_username is not None,
        "username": teacher_username,
    }


@app.post("/auth/login")
def login(request: Request, payload: LoginRequest):
    teacher = next(
        (
            teacher
            for teacher in load_teachers()
            if teacher.get("username") == payload.username
            and secrets.compare_digest(str(teacher.get("password", "")), payload.password)
        ),
        None,
    )
    if teacher is None:
        raise HTTPException(status_code=401, detail="Invalid teacher username or password")

    response = JSONResponse({"authenticated": True, "username": payload.username})
    response.set_cookie(TEACHER_COOKIE, make_teacher_cookie(payload.username), httponly=True, samesite="lax")
    return response


@app.post("/auth/logout")
def logout(request: Request):
    response = JSONResponse({"authenticated": False, "username": None})
    response.delete_cookie(TEACHER_COOKIE)
    return response


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(request: Request, activity_name: str, email: str):
    """Sign up a student for an activity"""
    require_teacher(request)
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(request: Request, activity_name: str, email: str):
    """Unregister a student from an activity"""
    require_teacher(request)
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
