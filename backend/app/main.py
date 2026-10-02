"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import explainer, search


app = FastAPI(title="AI News Agent")

# Allow the separate frontend dev server to call this API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(explainer.router, prefix="/explain", tags=["explainer"])


@app.get("/")
def root() -> dict[str, str]:
    """Return a simple health response for the API root."""
    return {"status": "ok", "service": "ai-news-agent"}



