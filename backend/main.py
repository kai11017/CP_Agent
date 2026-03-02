from fastapi import FastAPI
from routers.users import router as users_router
from database import engine, Base

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the CP_Agent Evaluation API!",
        "status": "Online",
        "docs": "Go to /docs to test the endpoints."
    }

# This creates the actual .db file and tables
Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(users_router)# attching the router tot he app