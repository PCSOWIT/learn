import asyncio
import sys
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Response
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from deps import get_current_user
from models import Base
from auth import router as auth_router
from workflow import router as workflow_router
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from db import engine
from limiter import limiter

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 开发阶段先允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(workflow_router, prefix="/api/v1/workflow", tags=["工作流"])
app.mount("/images", StaticFiles(directory="."), name="images")


class TopicRequest(BaseModel):
    theme: str
    count: int = 3

@app.post("/topics")
def create_topics(req: TopicRequest):
    return {"theme": req.theme, "count": req.count, "message": "收到"}

@app.get("/")
def read_root():
    return {"message": "你好，这是我的第一个接口"}

@app.get("/health")
async def health(response: Response):
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        response.status_code = 503
        return {"status": "unhealthy", "db": str(e)}
    return {"status": "ok", "db": "ok"}

@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"你好，{name}"}

@app.get("/profile")
def profile(user = Depends(get_current_user)):
    return user

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import selectors
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, loop="asyncio")
    server = uvicorn.Server(config)

    with asyncio.Runner(
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
    ) as runner:
        runner.run(server.serve())

