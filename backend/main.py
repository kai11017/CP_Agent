from fastapi import FastAPI
from routers.users import router as users_router

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(users_router)# attching the router tot he app