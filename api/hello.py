# api/hello.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/hello")
def hello():
  return {"ok": True, "msg": "hello from vercel"}
