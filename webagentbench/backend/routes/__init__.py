"""FastAPI route registration for advanced WebAgentBench environments."""

from fastapi import FastAPI

from .amazon import router as amazon_router
from .gmail import router as gmail_router
from .robinhood import router as robinhood_router

ENVIRONMENT_ROUTERS = [amazon_router, gmail_router, robinhood_router]


def mount_environment_routes(app: FastAPI) -> None:
    for router in ENVIRONMENT_ROUTERS:
        app.include_router(router)


__all__ = ["ENVIRONMENT_ROUTERS", "mount_environment_routes"]
