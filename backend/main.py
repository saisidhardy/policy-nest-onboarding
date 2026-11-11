"""Single-process entrypoint for PaaS hosts: apply migrations, then serve on $PORT."""

import os

import uvicorn

from alembic import command
from alembic.config import Config

if __name__ == "__main__":
    if os.environ.get("RUN_MIGRATIONS_ON_START", "true").lower() == "true":
        command.upgrade(Config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini")), "head")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 - PaaS hosts route traffic to the container interface
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
