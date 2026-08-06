"""Faithful test doubles for orchestrator tick handlers."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any
from unittest.mock import AsyncMock


class _TickDispatchMock:
    """Awaitable-call recorder whose dispatch behavior cannot be reconfigured."""

    __slots__ = ("__recorder",)

    def __init__(self, dispatch: Callable[..., Any]) -> None:
        object.__setattr__(
            self,
            "_TickDispatchMock__recorder",
            AsyncMock(side_effect=dispatch),
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"tick dispatch mock is immutable: {name}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"tick dispatch mock is immutable: {name}")

    async def __call__(self, *args: Any, **kwargs: Any) -> dict[str, float]:
        return await self.__recorder(*args, **kwargs)

    @property
    def await_count(self) -> int:
        return self.__recorder.await_count

    @property
    def await_args(self) -> Any:
        return self.__recorder.await_args

    @property
    def await_args_list(self) -> Any:
        return self.__recorder.await_args_list

    def assert_awaited(self) -> None:
        self.__recorder.assert_awaited()

    def assert_awaited_once(self) -> None:
        self.__recorder.assert_awaited_once()

    def assert_awaited_with(self, *args: Any, **kwargs: Any) -> None:
        self.__recorder.assert_awaited_with(*args, **kwargs)

    def assert_awaited_once_with(self, *args: Any, **kwargs: Any) -> None:
        self.__recorder.assert_awaited_once_with(*args, **kwargs)

    def assert_any_await(self, *args: Any, **kwargs: Any) -> None:
        self.__recorder.assert_any_await(*args, **kwargs)

    def assert_has_awaits(self, calls: Any, any_order: bool = False) -> None:
        self.__recorder.assert_has_awaits(calls, any_order=any_order)

    def assert_not_awaited(self) -> None:
        self.__recorder.assert_not_awaited()

    def configure_mock(self, **_kwargs: Any) -> None:
        raise TypeError("tick dispatch behavior cannot be reconfigured")

    def reset_mock(self, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            raise TypeError("tick dispatch reset cannot change behavior")
        self.__recorder.reset_mock()


def tick_dispatch_mock(
    timings: Mapping[str, float] | None = None,
    *,
    on_call: Callable[..., Any] | None = None,
) -> _TickDispatchMock:
    """Return an async dispatch double that always yields a fresh Mapping.

    ``_tick`` stores this result on every run and formats ``items()`` when a
    run is slow. Keeping construction in one helper makes that production
    contract independent of host timing and prevents mutable mock defaults
    from changing the result after setup.
    """

    if timings is not None and not isinstance(timings, Mapping):
        raise TypeError("tick dispatch timings must be a Mapping")
    snapshot = dict(timings or {})

    async def dispatch(*args: Any, **kwargs: Any) -> dict[str, float]:
        if on_call is not None:
            result = on_call(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Mapping):
                raise TypeError("tick dispatch callback must return a Mapping")
            return dict(result)
        return dict(snapshot)

    return _TickDispatchMock(dispatch)


__all__ = ["tick_dispatch_mock"]
