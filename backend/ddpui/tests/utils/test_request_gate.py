"""Tests for the concurrency gate in front of the Django request handler."""

import asyncio

from django.http import HttpResponse
from django.test import RequestFactory

from ddpui.utils import request_gate
from ddpui.utils.request_gate import RequestGateMiddleware


def make_gate(handler, size=2, max_wait=0.2):
    """A gate with a small size and a short wait, so tests run in milliseconds."""
    gate = RequestGateMiddleware(handler)
    gate.semaphore = asyncio.Semaphore(size)
    gate.max_wait_seconds = max_wait
    return gate


def get(path="/api/charts/1/data/"):
    return RequestFactory().get(path)


def test_lets_a_request_through_when_there_is_room():
    async def handler(request):
        return HttpResponse("ok")

    async def run():
        return await make_gate(handler)(get())

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.content == b"ok"


def test_never_more_than_size_requests_inside_at_once():
    inside = 0
    most_inside = 0

    async def handler(request):
        nonlocal inside, most_inside
        inside += 1
        most_inside = max(most_inside, inside)
        await asyncio.sleep(0.02)
        inside -= 1
        return HttpResponse("ok")

    async def run():
        gate = make_gate(handler, size=3, max_wait=5)
        return await asyncio.gather(*(gate(get()) for _ in range(10)))

    responses = asyncio.run(run())
    assert [r.status_code for r in responses] == [200] * 10
    assert most_inside == 3


def test_returns_503_when_the_wait_runs_out():
    release = None

    async def handler(request):
        await release.wait()
        return HttpResponse("ok")

    async def run():
        nonlocal release
        release = asyncio.Event()
        gate = make_gate(handler, size=1, max_wait=0.05)
        first = asyncio.ensure_future(gate(get()))
        await asyncio.sleep(0)  # let the first request take the only place
        second = await gate(get())
        release.set()
        return await first, second

    first, second = asyncio.run(run())
    assert first.status_code == 200
    assert second.status_code == 503
    assert second["Retry-After"] == str(request_gate.RETRY_AFTER_SECONDS)


def test_gives_the_place_back_when_the_handler_raises():
    async def handler(request):
        raise ValueError("boom")

    async def run():
        gate = make_gate(handler, size=1, max_wait=0.05)
        for _ in range(3):
            try:
                await gate(get())
            except ValueError:
                pass
        return gate.semaphore.locked()

    assert asyncio.run(run()) is False


def test_exempt_paths_skip_the_line():
    calls = []

    async def handler(request):
        calls.append(request.path)
        return HttpResponse("ok")

    async def run():
        gate = make_gate(handler, size=1, max_wait=0.01)
        await gate.semaphore.acquire()  # the gate is full
        healthcheck = await gate(get("/healthcheck"))
        metrics = await gate(get("/prometheus/metrics"))
        chart = await gate(get("/api/charts/1/data/"))
        return healthcheck, metrics, chart

    healthcheck, metrics, chart = asyncio.run(run())
    assert healthcheck.status_code == 200
    assert metrics.status_code == 200
    assert chart.status_code == 503
    assert calls == ["/healthcheck", "/prometheus/metrics"]


def test_reports_how_long_the_request_waited():
    async def handler(request):
        return HttpResponse("ok")

    async def run():
        return await make_gate(handler)(get())

    response = asyncio.run(run())
    assert int(response["X-Gate-Wait-Ms"]) >= 0
