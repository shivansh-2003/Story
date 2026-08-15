import functools
import inspect
import logging
import time
import uuid
from collections.abc import Callable

# Names redacted outright, regardless of how short/harmless-looking the value
# is — these are exactly the fields the observability pass must never leak:
# passwords, tokens, and full prompt/completion text. Matched on the exact
# parameter name so "instruction"/"content" get redacted but "user_id"/
# "character_id" (which merely contain "user"/"content"-adjacent substrings)
# don't lose useful tracing value for nothing.
_EXACT_SENSITIVE_NAMES = {
    "user",
    "system",
    "prompt",
    "instruction",
    "content",
    "new_content",
    "chapter_summary",
    "running_summary_cache",
    "running_summary",
    "text",
}
# "token" alone would also catch "max_tokens" (a harmless generation
# parameter, not a credential) — matched more specifically instead.
_SUBSTRING_SENSITIVE = ("password", "jwt", "secret", "access_token", "bearer")

_SAFE_SCALAR_TYPES = (int, float, bool, type(None))
_MAX_STR_LEN = 200


def _is_sensitive(name: str) -> bool:
    lname = name.lower()
    if lname in _EXACT_SENSITIVE_NAMES:
        return True
    return any(s in lname for s in _SUBSTRING_SENSITIVE)


def _safe_repr(value: object) -> str:
    # Deliberately conservative: only ever show primitives (truncated) or a
    # UUID. Everything else — ORM rows, sessions, Pydantic models, dicts,
    # lists — becomes just its type name. Never call repr() on an arbitrary
    # object; there's no way to guarantee that's safe for objects this
    # decorator wasn't specifically written to know about.
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        return repr(value if len(value) <= _MAX_STR_LEN else value[:_MAX_STR_LEN] + "…")
    if isinstance(value, _SAFE_SCALAR_TYPES):
        return repr(value)
    return f"<{type(value).__name__}>"


def _safe_args(fn: Callable, args: tuple, kwargs: dict) -> str:
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs)
        items = bound.arguments.items()
    except TypeError:
        items = [(str(i), a) for i, a in enumerate(args)] + list(kwargs.items())

    parts = []
    for name, value in items:
        if name == "self":
            continue
        parts.append(f"{name}=<redacted>" if _is_sensitive(name) else f"{name}={_safe_repr(value)}")
    return ", ".join(parts)


def log_execution(func: Callable | None = None, *, label: str | None = None):
    """Logs start/completion/failure with elapsed time in ms. Handles plain
    sync functions, coroutine functions, and async generator functions (the
    streaming case) — an async generator additionally gets a TTFT line on
    its first yield and a total-duration + chunk-count line at the end,
    which is what section 3's STREAM_TTFT/STREAM_TOTAL labels need; there's
    no separate "streaming instrumentation" to hand-write, this covers it.

    Usage: @log_execution or @log_execution(label="PREPARE_PHASE")."""

    def decorator(fn: Callable) -> Callable:
        logger = logging.getLogger(fn.__module__)
        qualname = f"{fn.__module__}.{fn.__qualname__}"
        tag = f"{label} [{qualname}]" if label else qualname

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args, **kwargs):
                start = time.perf_counter()
                logger.info("%s START %s", tag, _safe_args(fn, args, kwargs))
                first_chunk_at: float | None = None
                chunks = 0
                try:
                    async for item in fn(*args, **kwargs):
                        if first_chunk_at is None:
                            first_chunk_at = time.perf_counter()
                            logger.info("%s STREAM_TTFT %.1fms", tag, (first_chunk_at - start) * 1000)
                        chunks += 1
                        yield item
                    logger.info(
                        "%s STREAM_TOTAL %.1fms chunks=%d", tag, (time.perf_counter() - start) * 1000, chunks
                    )
                except Exception as e:
                    elapsed = (time.perf_counter() - start) * 1000
                    logger.error("%s FAILED after %.1fms: %s: %s", tag, elapsed, type(e).__name__, e)
                    raise

            return async_gen_wrapper

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                logger.info("%s START %s", tag, _safe_args(fn, args, kwargs))
                try:
                    result = await fn(*args, **kwargs)
                    logger.info("%s DONE %.1fms", tag, (time.perf_counter() - start) * 1000)
                    return result
                except Exception as e:
                    elapsed = (time.perf_counter() - start) * 1000
                    logger.error("%s FAILED after %.1fms: %s: %s", tag, elapsed, type(e).__name__, e)
                    raise

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger.info("%s START %s", tag, _safe_args(fn, args, kwargs))
            try:
                result = fn(*args, **kwargs)
                logger.info("%s DONE %.1fms", tag, (time.perf_counter() - start) * 1000)
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                logger.error("%s FAILED after %.1fms: %s: %s", tag, elapsed, type(e).__name__, e)
                raise

        return sync_wrapper

    return decorator(func) if func is not None else decorator


def log_cache_event(key: str, hit: bool, source: str) -> None:
    """CACHE_HIT / CACHE_MISS, keyed and attributed to the calling function —
    greppable now, ready to wire into a real cache layer later. Used today
    against session_store's Redis reads (session state, not a cache, but the
    same read-or-miss shape) and left as a # TODO at the caching candidates
    identified in the backend optimization pass."""
    logger = logging.getLogger(source)
    logger.info("%s key=%s", "CACHE_HIT" if hit else "CACHE_MISS", key)


def _demo() -> None:
    import asyncio
    import io

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    test_logger = logging.getLogger(__name__)
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    @log_execution
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5

    @log_execution
    async def async_add(a: int, b: int) -> int:
        return a + b

    assert asyncio.run(async_add(2, 3)) == 5

    @log_execution(label="STREAM")
    async def gen(n: int):
        for i in range(n):
            yield i

    async def collect() -> list[int]:
        return [x async for x in gen(3)]

    assert asyncio.run(collect()) == [0, 1, 2]

    @log_execution
    def with_secret(password: str, user_id: str) -> None:
        return None

    with_secret("hunter22222", "abc-123")

    @log_execution
    def boom() -> None:
        raise ValueError("nope")

    try:
        boom()
        raise AssertionError("should have raised")
    except ValueError:
        pass

    output = log_stream.getvalue()
    assert "hunter22222" not in output, "password leaked into logs"
    assert "abc-123" in output, "non-sensitive arg was needlessly redacted"
    assert "STREAM_TTFT" in output
    assert "STREAM_TOTAL" in output
    assert "FAILED" in output

    test_logger.removeHandler(handler)
    print("logging_utils self-check passed")


if __name__ == "__main__":
    _demo()
