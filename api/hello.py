from fastapi import FastAPI

app = FastAPI()

# Function URL will be: https://<project>.vercel.app/api/hello
# So keep the in-app route at "/"
@app.get("/")
def hello():
    return {"ok": True, "msg": "hello from vercel"}
