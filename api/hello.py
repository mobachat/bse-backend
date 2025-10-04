from fastapi import FastAPI, Request

app = FastAPI()

# Expected URL: https://<project>.vercel.app/api/hello
@app.get("/")
def root():
    return {"ok": True, "msg": "hello from vercel"}

# DEBUG: catch-all to show what path FastAPI is actually seeing
@app.api_route("/{path_name:path}", methods=["GET"])
async def echo_path(path_name: str, request: Request):
    return {
        "debug": "catch-all",
        "received_path": f"/{path_name}",
        "query": dict(request.query_params),
        "hint": "On Vercel, this file is mounted at /api/hello. "
                "The in-app route should be '/'. If you see received_path != '' here, "
                "you're hitting a subpath."
    }
