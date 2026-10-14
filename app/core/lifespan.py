from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Any, TypeVar

AppT = TypeVar("AppT")


def combine_lifespans[AppT](
    *lifespans: Callable[[AppT], AbstractAsyncContextManager[Mapping[str, Any] | None]],
) -> Callable[[AppT], AbstractAsyncContextManager[dict[str, Any]]]:

    @asynccontextmanager
    async def combined(app: AppT) -> AsyncGenerator[dict[str, Any]]:
        merged: dict[str, Any] = {}
        async with AsyncExitStack() as stack:
            for ls in lifespans:
                result = await stack.enter_async_context(ls(app))
                if result is not None:
                    merged.update(result)
            yield merged

    return combined
