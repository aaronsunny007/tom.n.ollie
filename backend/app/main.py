"""FastAPI application for the Tom & Ollie storefront backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import create_all
from .routers import admin, catalogue, checkout, content
from .services import shipping

DESCRIPTION = """
Backend for the Tom & Ollie storefront relaunch.

Two rules are enforced in code rather than left to process:

* **Allergen data gates publishing.** A product cannot be sold until a human has
  confirmed its allergens, and that statement follows the order onto the
  dispatch note that goes in the parcel.
* **Chilled goods drive the whole order.** A basket with any chilled line ships
  on a chilled service, only on a dispatch day, and only to a delivery date the
  warehouse can actually hit.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(catalogue.router)
    app.include_router(checkout.router)
    app.include_router(content.router)
    app.include_router(admin.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        card = shipping.rate_card()
        return {
            "status": "ok",
            "admin_enabled": bool(settings.admin_api_key),
            "shipping_rates_quoted": card.get("quoted", False),
        }

    return app


app = create_app()
