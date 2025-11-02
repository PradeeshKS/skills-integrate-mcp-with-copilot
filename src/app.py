"""High School Management System API with persistent storage

This FastAPI app now uses SQLModel (SQLite) to persist activities and
participants. On first startup it will create the database file
`activities.db` in the project root and seed the initial activities
if the DB is empty.
"""

from typing import Optional

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import Field, Session, SQLModel, create_engine, select


DATABASE_URL = "sqlite:///./activities.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)


class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    schedule: str = Field(default="")
    max_participants: int = Field(default=0)


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    activity_id: int = Field(foreign_key="activity.id")
    email: str = Field(index=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def seed_initial_activities():
    initial = {
        "Chess Club": {
            "description": "Learn strategies and compete in chess tournaments",
            "schedule": "Fridays, 3:30 PM - 5:00 PM",
            "max_participants": 12,
            "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
        },
        "Programming Class": {
            "description": "Learn programming fundamentals and build software projects",
            "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
            "max_participants": 20,
            "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
        },
        "Gym Class": {
            "description": "Physical education and sports activities",
            "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
            "max_participants": 30,
            "participants": ["john@mergington.edu", "olivia@mergington.edu"],
        },
        "Soccer Team": {
            "description": "Join the school soccer team and compete in matches",
            "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
            "max_participants": 22,
            "participants": ["liam@mergington.edu", "noah@mergington.edu"],
        },
        "Basketball Team": {
            "description": "Practice and play basketball with the school team",
            "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
            "max_participants": 15,
            "participants": ["ava@mergington.edu", "mia@mergington.edu"],
        },
        "Art Club": {
            "description": "Explore your creativity through painting and drawing",
            "schedule": "Thursdays, 3:30 PM - 5:00 PM",
            "max_participants": 15,
            "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
        },
        "Drama Club": {
            "description": "Act, direct, and produce plays and performances",
            "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
            "max_participants": 20,
            "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
        },
        "Math Club": {
            "description": "Solve challenging problems and participate in math competitions",
            "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
            "max_participants": 10,
            "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
        },
        "Debate Team": {
            "description": "Develop public speaking and argumentation skills",
            "schedule": "Fridays, 4:00 PM - 5:30 PM",
            "max_participants": 12,
            "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
        },
    }

    with Session(engine) as session:
        existing = session.exec(select(Activity)).first()
        if existing:
            return

        for name, data in initial.items():
            activity = Activity(
                name=name,
                description=data["description"],
                schedule=data["schedule"],
                max_participants=data["max_participants"],
            )
            session.add(activity)
            session.commit()
            session.refresh(activity)

            for email in data.get("participants", []):
                participant = Participant(activity_id=activity.id, email=email)
                session.add(participant)
        session.commit()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_initial_activities()


def activities_to_dict():
    """Return activities in the same shape the frontend expects."""
    result = {}
    with Session(engine) as session:
        activities = session.exec(select(Activity)).all()
        for act in activities:
            participants = session.exec(
                select(Participant).where(Participant.activity_id == act.id)
            ).all()
            result[act.name] = {
                "description": act.description,
                "schedule": act.schedule,
                "max_participants": act.max_participants,
                "participants": [p.email for p in participants],
            }
    return result


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities_to_dict()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity (persisted)."""
    with Session(engine) as session:
        activity = session.exec(select(Activity).where(Activity.name == activity_name)).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        participants = session.exec(
            select(Participant).where(Participant.activity_id == activity.id)
        ).all()

        if email in [p.email for p in participants]:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        if len(participants) >= activity.max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        participant = Participant(activity_id=activity.id, email=email)
        session.add(participant)
        session.commit()
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity (persisted)."""
    with Session(engine) as session:
        activity = session.exec(select(Activity).where(Activity.name == activity_name)).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant = session.exec(
            select(Participant).where(
                Participant.activity_id == activity.id, Participant.email == email
            )
        ).first()

        if not participant:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        session.delete(participant)
        session.commit()
    return {"message": f"Unregistered {email} from {activity_name}"}
