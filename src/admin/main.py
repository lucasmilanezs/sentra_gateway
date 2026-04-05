import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.admin.infrastructure.config.settings import AdminSettings
from src.admin.interface.http.exception_handlers import register_domain_exception_handlers
from src.admin.interface.http.routers import auth_router, health_router, tenant_router, admin_route_router
from src.admin.interface.http.wiring import AdminWiring

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AdminSettings()
    
    wiring = AdminWiring(settings)
    
    app.state.admin = wiring
    
    logger.info(f"Aplicação iniciada. Modo: {'JSON Local'}")
    
    yield
    
    # Cleanup aqui se necessário (ex: fechar conexões)
    if settings.use_postgres and hasattr(wiring, 'engine'):
        wiring.engine.dispose()

app = FastAPI(title="Sentra Admin Gateway", lifespan=lifespan)

# Middlewares e Exception Handlers
register_domain_exception_handlers(app)

# Rotas - Use prefixos consistentes
app.include_router(health_router.router, tags=["Health"])
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=[])
app.include_router(tenant_router.router, prefix="/api/v1/tenants", tags=[])
app.include_router(admin_route_router.router, prefix="/api/v1/routes", tags=[])