from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.elders import router as elders_router
from app.routers.medicines import router as medicines_router
from app.routers.status import router as status_router
from app.routers.sos import router as sos_router

__all__ = ["health_router", "auth_router", "elders_router", "medicines_router", "status_router", "sos_router"]
