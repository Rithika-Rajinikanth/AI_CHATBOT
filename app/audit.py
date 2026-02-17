"""
app/audit.py
Middleware that logs every HTTP request to console + audit.log.
"""
import time
import logging
from fastapi import Request

logger = logging.getLogger("audit")


async def audit_middleware(request: Request, call_next):
    start    = time.perf_counter()
    response = await call_next(request)
    ms       = (time.perf_counter() - start) * 1000

    line = (
        f"{request.method:<6} {str(request.url.path):<40} "
        f"{ms:>7.1f}ms  status={response.status_code}"
    )
    logger.info(line)

    with open("audit.log", "a") as f:
        f.write(line + "\n")

    return response
