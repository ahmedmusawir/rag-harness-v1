from fastapi import FastAPI

from src.api.diagnostics import router as diagnostics_router
from src.api.docs import router as docs_router
from src.api.health import router as health_router
from src.api.projects import router as projects_router

app = FastAPI(title="Stark RAG API", version="1.0.0")
app.include_router(health_router)
app.include_router(projects_router)
app.include_router(docs_router)
app.include_router(diagnostics_router)
