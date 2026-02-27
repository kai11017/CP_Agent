from pydantic import BaseModel
from uuid import UUID, uuid4
from datetime import datetime


class User(BaseModel): #this is whats erver stores and returns
    userId: UUID
    name: str
    email: str
    createdAt: datetime


class CreateUserRequest(BaseModel):#this is whata. client sends
    name: str
    email: str