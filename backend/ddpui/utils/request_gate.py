"""
A gate in front of the Django request handler: at most MAX_CONCURRENT requests
are being handled at once per worker process; the rest wait their turn.

Why: views are sync, so under ASGI Django gives every request its own thread the
moment it arrives. With one worker on one core, a burst of 200 requests means
200 threads taking turns on the GIL, every one of them holding its query results
in memory while it waits. Load tests on staging showed backend RSS climbing from
~330 MB to ~3.7 GB at 50 users, roughly 15 MB per in-flight request.

The gate is async and sits first in MIDDLEWARE, so a waiting request is a cheap
coroutine on the event loop: it has no thread and has loaded nothing yet. Only
requests that get a place go on to the rest of the stack.

It does not add throughput — one core still finishes what one core can. It caps
memory, and it turns overload into a clean 503 instead of every request slowing
down together until something times out.
"""

import asyncio
import time

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import JsonResponse

from ddpui.utils.custom_logger import CustomLogger

logger = CustomLogger("ddpui")

# How many requests are handled at once, per worker process. Near the warehouse
# connection pool (5 + 7 overflow), since more than that cannot query together.
MAX_CONCURRENT = 15

# How long a request may wait for a place before getting 503. Under nginx's 60s
# proxy timeout, so the client gets a clear "busy" rather than a gateway timeout.
MAX_WAIT_SECONDS = 30

RETRY_AFTER_SECONDS = 5

# Never queued: liveness and metrics must answer even when the gate is full.
EXEMPT_PREFIXES = ("/healthcheck", "/prometheus/")


class RequestGateMiddleware:
    """Async-only middleware; Django adapts the rest of the chain around it."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self.max_wait_seconds = MAX_WAIT_SECONDS
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return await self.get_response(request)

        arrived = time.monotonic()
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.max_wait_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                f"request gate full: rejected {request.method} {request.path} "
                f"after {self.max_wait_seconds}s"
            )
            response = JsonResponse({"detail": "Server busy, please retry"}, status=503)
            response["Retry-After"] = str(RETRY_AFTER_SECONDS)
            return response

        waited_ms = int((time.monotonic() - arrived) * 1000)
        try:
            response = await self.get_response(request)
        finally:
            self.semaphore.release()

        # Lets a load test separate time spent queued from time spent working.
        response["X-Gate-Wait-Ms"] = str(waited_ms)
        return response
