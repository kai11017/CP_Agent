from fastapi import APIRouter
from uuid import uuid4
from datetime import datetime
from typing import List

from models import User, CreateUserRequest

router = APIRouter()

# Temporary in-memory storage
USERS_DB = []


@router.post("/users", response_model=User)
def create_user(payload: CreateUserRequest):
    user = User(
        userId=uuid4(),
        name=payload.name,
        email=payload.email,
        createdAt=datetime.utcnow()
    )
    USERS_DB.append(user)
    return user


@router.get("/users", response_model=List[User])
def get_users():
    return USERS_DB