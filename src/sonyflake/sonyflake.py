#    Copyright 2025-present Iyad

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.


from __future__ import annotations

import asyncio
import concurrent.futures as cf
import datetime
import ipaddress
import platform
import socket
import subprocess
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, NamedTuple, NotRequired, TypedDict, Unpack

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final, Literal

__all__ = (
    "DecomposedSonyflake",
    "InvalidBitsMachineID",
    "InvalidBitsSequence",
    "InvalidBitsTime",
    "InvalidMachineID",
    "InvalidSequence",
    "InvalidTimeUnit",
    "MachineIDCheckFailure",
    "NoPrivateAddress",
    "OverTimeLimit",
    "Sonyflake",
    "SonyflakeError",
    "StartTimeAhead",
)

DEFAULT_BITS_TIME: Final = 39
DEFAULT_BITS_SEQUENCE: Final = 8
DEFAULT_BITS_MACHINE_ID: Final = 16
DEFAULT_TIME_UNIT: Final = 10_000_000  # 10msec
SECOND_NS: Final = 1_000_000_000


class SonyflakeError(Exception):
    """Base class for all sonyflake errors."""


class InvalidBitsSequence(SonyflakeError):
    """Raised when the bit length for the sequence is out of valid range (0-30)."""

    def __init__(self) -> None:
        msg = "bit length for sequence number must be between 0 and 30 (inclusive)."
        super().__init__(msg)


class InvalidBitsMachineID(SonyflakeError):
    """Raised when the bit length for the machine ID is out of valid range (0-30)."""

    def __init__(self) -> None:
        msg = "bit length for machine id must be between 0 and 30 (inclusive)."
        super().__init__(msg)


class InvalidBitsTime(SonyflakeError):
    """Raised when the computed time bit length is too small to represent valid timestamps."""

    def __init__(self) -> None:
        msg = "bit length for time must be at least 32."
        super().__init__(msg)


class InvalidTimeUnit(SonyflakeError):
    """Raised when the provided time unit is too small."""

    def __init__(self) -> None:
        msg = "time unit must be atleast 1 millisecond."
        super().__init__(msg)


class InvalidSequence(SonyflakeError):
    """Raised when the sequence number is out of valid range."""

    def __init__(self, bits_sequence: int) -> None:
        max_value = (1 << bits_sequence) - 1
        msg = f"sequence number must be between 0 and {max_value} (inclusive) for bits_sequence={bits_sequence}."
        super().__init__(msg)


class InvalidMachineID(SonyflakeError):
    """Raised when the computed machine ID is out of range."""

    def __init__(self, bits_machine_id: int) -> None:
        max_value = (1 << bits_machine_id) - 1
        msg = f"machine id must be between 0 and {max_value} (inclusive) for bits_machine_id={bits_machine_id}"
        super().__init__(msg)


class MachineIDCheckFailure(SonyflakeError):
    """Raised when a machine ID fails the validation check.

    .. versionadded:: 2.0
    """

    def __init__(self, machine_id: int) -> None:
        msg = f"machine id validation failed for {machine_id=}."
        super().__init__(msg)


class StartTimeAhead(SonyflakeError):
    """Raised when the provided start time is ahead of the current time."""

    def __init__(self) -> None:
        msg = "start time must not be in the future."
        super().__init__(msg)


class OverTimeLimit(SonyflakeError):
    """Raised when the elapsed time exceeds the representable limit."""

    def __init__(self, max_elapsed_time: int) -> None:
        msg = f"elapsed time exceeded the limit: max allowed is {max_elapsed_time}"
        super().__init__(msg)


class NoPrivateAddress(SonyflakeError):
    """Raised when no private IPv4 address could be determined."""

    def __init__(self) -> None:
        msg = "failed to determine private IPv4 address."
        super().__init__(msg)


class DecomposedSonyflake(NamedTuple):
    """Represents a decomposed Sonyflake.

    This structure holds the individual components of a 64-bit Sonyflake ID.

    .. versionchanged:: 2.0
       The ``id`` attribute was removed.

    Attributes
    ----------
    time : int
        The time portion of the ID.
    sequence : int
        The sequence number portion of the ID.
    machine_id : int
        The machine identifier portion of the ID.
    """

    time: int
    sequence: int
    machine_id: int


def _pick_private_ip(ips: list[str]) -> ipaddress.IPv4Address:
    for ip_str in ips:
        ip = ipaddress.IPv4Address(ip_str)

        if ip.is_loopback:
            continue

        if ip.is_private or ip.is_link_local:
            return ip

    raise NoPrivateAddress


def _macos_reliable_ip() -> ipaddress.IPv4Address:
    result = subprocess.run(["/usr/bin/osascript", "-e", "IPv4 address of (system info)"], capture_output=True, check=True)
    ip_str = result.stdout.decode("utf-8").removesuffix("\n")
    return ipaddress.IPv4Address(ip_str)


def _lower_16bit_private_ip() -> int:
    # socket.gethostbyname_ex(socket.getfqdn()) fails on some macbooks (tbh, most from what i have tested).
    # reference: https://github.com/python/cpython/issues/79345
    try:
        *_, ips = socket.gethostbyname_ex(socket.gethostname())
        ip = _pick_private_ip(ips)

    except socket.gaierror:
        if platform.system() != "Darwin":
            raise

        ip = _macos_reliable_ip()

    ip_bytes = ip.packed
    return (ip_bytes[2] << 8) + ip_bytes[3]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


# Thanks to the discussion with Sinbad :).
class _HybridLock:
    __slots__ = ("_internal_lock", "_locked", "_waiters")

    _waiters: deque[cf.Future[None]]
    _internal_lock: threading.Lock
    _locked: bool

    def __init__(self) -> None:
        self._waiters = deque()
        self._internal_lock = threading.Lock()
        self._locked = False

    async def __aenter__(self) -> None:
        with self._internal_lock:
            # Incase you are wondering why the all check
            # https://discuss.python.org/t/preventing-yield-inside-certain-context-managers/1091
            # https://peps.python.org/pep-0789/
            if not self._locked and all(w.cancelled() for w in self._waiters):
                self._locked = True
                return

            fut: cf.Future[None] = cf.Future()
            self._waiters.append(fut)

        try:
            await asyncio.wrap_future(fut)
        except (asyncio.CancelledError, cf.CancelledError):
            with self._internal_lock:
                if fut.done() and not fut.cancelled():
                    self._locked = False
                    self.__wake_next()
            raise

    async def __aexit__(self, *_: object) -> Literal[False]:
        return self.__release()

    def __enter__(self) -> None:
        with self._internal_lock:
            if not self._locked and all(w.cancelled() for w in self._waiters):
                self._locked = True
                return

            fut: cf.Future[None] = cf.Future()
            self._waiters.append(fut)

        try:
            fut.result()
        except cf.CancelledError:
            with self._internal_lock:
                if fut.done() and not fut.cancelled():
                    self._locked = False
                    self.__wake_next()
            raise

    def __exit__(self, *_: object) -> Literal[False]:
        return self.__release()

    def __release(self) -> Literal[False]:
        with self._internal_lock:
            self._locked = False
            self.__wake_next()
        return False

    def __wake_next(self) -> None:
        # Not acquiring the lock here, since this function is gonna be called
        # from a locked context.
        while self._waiters:
            fut = self._waiters.popleft()
            if not fut.cancelled() and not fut.done():
                self._locked = True
                fut.set_result(None)
                break


class _SonyflakeOptions(TypedDict):
    bits_sequence: NotRequired[int]
    bits_machine_id: NotRequired[int]
    time_unit: NotRequired[datetime.timedelta]
    start_time: datetime.datetime
    machine_id: NotRequired[int]
    check_machine_id: NotRequired[Callable[[int], bool]]


class Sonyflake:
    """A distributed unique ID generator.

    Parameters
    ----------
    bits_sequence : int, optional
        Number of bits allocated for the sequence number (the default is `8`).
    bits_machine_id : int, optional
        Number of bits allocated for the machine ID (the default is `16`).
    time_unit : datetime.timedelta, optional
        Minimum time unit used for incrementing IDs (the default is 10 milliseconds).
    start_time : datetime.datetime
        The custom epoch from which time is measured.
    machine_id : int, optional
        Custom machine ID to use (the default is the lower 16 bits of the machine's private IP address).
    check_machine_id : Callable[[int], bool], optional
        Function to validate the generated or provided machine ID (the default is `None`, which disables validation).

    Raises
    ------
    ValueError
        If start time is not provided.
    InvalidBitsSequence
        If the provided bit length for the sequence number is invalid.
    InvalidBitsMachineID
        If the provided bit length for the machine ID is invalid.
    InvalidTimeUnit
        If the time unit is smaller than 1 millisecond.
    InvalidMachineID
        If the provided or generated machine ID is invalid.
    StartTimeAhead
        If the start time is set in the future.
    """

    __slots__ = (
        "_bits_machine_id",
        "_bits_sequence",
        "_bits_time",
        "_elapsed_time",
        "_lock",
        "_machine_id",
        "_sequence",
        "_start_time",
        "_time_unit",
    )

    _bits_machine_id: int
    _bits_sequence: int
    _bits_time: int
    _elapsed_time: int
    _lock: _HybridLock
    _machine_id: int
    _sequence: int
    _start_time: int
    _time_unit: int

    def __init__(self, **options: Unpack[_SonyflakeOptions]) -> None:
        bits_sequence = options.pop("bits_sequence", DEFAULT_BITS_SEQUENCE)
        if not 0 <= bits_sequence <= 30:
            raise InvalidBitsSequence

        bits_machine_id = options.pop("bits_machine_id", DEFAULT_BITS_MACHINE_ID)
        if not 0 <= bits_machine_id <= 30:
            raise InvalidBitsMachineID

        bits_time = 63 - bits_sequence - bits_machine_id
        if bits_time < 32:
            raise InvalidBitsTime

        self._bits_sequence = bits_sequence
        self._bits_machine_id = bits_machine_id
        self._bits_time = bits_time

        try:
            time_unit = options.pop("time_unit")
        except KeyError:
            self._time_unit = DEFAULT_TIME_UNIT
        else:
            if time_unit < datetime.timedelta(milliseconds=1):
                raise InvalidTimeUnit

            self._time_unit = int(time_unit.total_seconds() * SECOND_NS)

        try:
            start_time = options["start_time"]
        except KeyError:
            msg = "'start_time' is required"
            raise ValueError(msg) from None
        else:
            start_time = start_time.astimezone(datetime.UTC)
            if start_time > _utcnow():
                raise StartTimeAhead

        self._start_time = self._to_internal_time(start_time)
        self._elapsed_time = 0

        self._sequence = (1 << self._bits_sequence) - 1

        try:
            machine_id = options.pop("machine_id")
        except KeyError:
            machine_id = _lower_16bit_private_ip()

        if not 0 <= machine_id < (1 << bits_machine_id):
            raise InvalidMachineID(bits_machine_id)

        try:
            check_machine_id = options.pop("check_machine_id")
        except KeyError:
            pass
        else:
            if not check_machine_id(machine_id):
                raise MachineIDCheckFailure(machine_id)

        self._machine_id = machine_id

        self._lock = _HybridLock()

    def next_id(self) -> int:
        """Return the next unique id.

        Returns
        -------
        int
            A 64-bit Sonyflake ID.

        Raises
        ------
        OverTimeLimit
            If the elapsed time exceeds the maximum representable value.
        """
        mask_sequence = (1 << self._bits_sequence) - 1

        with self._lock:
            current = self._current_elapsed_time()
            if self._elapsed_time < current:
                self._elapsed_time = current
                self._sequence = 0
            else:
                self._sequence = (self._sequence + 1) & mask_sequence
                if self._sequence == 0:
                    self._elapsed_time += 1
                    overtime = self._elapsed_time - current
                    self._sleep(overtime)

            return self._to_id()

    async def next_id_async(self) -> int:
        """Return the next unique id.

        This coroutine is the asynchronous version of :meth:`Sonyflake.next_id`
        and is intended for use in asynchronous applications.

        .. versionadded:: 2.0

        Returns
        -------
        int
            A 64-bit Sonyflake ID.

        Raises
        ------
        OverTimeLimit
            If the elapsed time exceeds the maximum representable value.
        """
        mask_sequence = (1 << self._bits_sequence) - 1

        async with self._lock:
            current = self._current_elapsed_time()
            if self._elapsed_time < current:
                self._elapsed_time = current
                self._sequence = 0
            else:
                self._sequence = (self._sequence + 1) & mask_sequence
                if self._sequence == 0:
                    self._elapsed_time += 1
                    overtime = self._elapsed_time - current
                    await self._sleep_async(overtime)

            return self._to_id()

    def to_time(self, sonyflake_id: int) -> datetime.datetime:
        """Convert a Sonyflake ID to its corresponding UTC datetime.

        Parameters
        ----------
        sonyflake_id : int
            The Sonyflake ID to convert.

        Returns
        -------
        datetime.datetime
            The UTC datetime corresponding to the given ID.
        """
        ns = (self._start_time + self._time_part(sonyflake_id)) * self._time_unit
        return datetime.datetime.fromtimestamp(ns / SECOND_NS, tz=datetime.UTC)

    def compose(self, dt: datetime.datetime, sequence: int, machine_id: int) -> int:
        """Compose a Sonyflake ID from datetime, sequence, and machine ID.

        .. versionchanged:: 2.0
            The ``dt`` parameter no longer needs to be in UTC and maybe
            timezone-aware or naieve. If ``dt`` is naive (has no timezone),
            it is assumed to be in the system local timezone.

        Parameters
        ----------
        dt : datetime.datetime
            The datetime at which the ID is generated.
        sequence : int
            A number between 0 and 2^bits_sequence - 1 (inclusive).
        machine_id : int
            A number between 0 and 2^bits_machine_id - 1 (inclusive).

        Returns
        -------
        int
            The composed Sonyflake ID.

        Raises
        ------
        StartTimeAhead
            If the datetime is before the configured start time.
        OverTimeLimit
            If the elapsed time exceeds the representable range.
        InvalidSequence
            If the sequence value is out of range.
        InvalidMachineID
            If the machine ID is out of range.
        """
        elapsed_time = self._to_internal_time(dt) - self._start_time
        if elapsed_time < 0:
            raise StartTimeAhead

        max_elapsed_time = (1 << self._bits_time) - 1
        if elapsed_time > max_elapsed_time:
            raise OverTimeLimit(max_elapsed_time)

        if not 0 <= sequence < (1 << self._bits_sequence):
            raise InvalidSequence(self._bits_sequence)

        if not 0 <= machine_id < (1 << self._bits_machine_id):
            raise InvalidMachineID(self._bits_machine_id)

        time = elapsed_time << (self._bits_sequence + self._bits_machine_id)
        seq = sequence << self._bits_machine_id
        return time | seq | machine_id

    def decompose(self, sonyflake_id: int) -> DecomposedSonyflake:
        """Decompose a Sonyflake ID into its components.

        Parameters
        ----------
        sonyflake_id : int
            The Sonyflake ID to decompose.

        Returns
        -------
        DecomposedSonyflake
            A named tuple with the fields: `time`, `sequence`, `machine_id`.
        """
        time = self._time_part(sonyflake_id)
        sequence = self._sequence_part(sonyflake_id)
        machine_id = self._machine_id_part(sonyflake_id)

        return DecomposedSonyflake(
            time=time,
            sequence=sequence,
            machine_id=machine_id,
        )

    def _to_internal_time(self, dt: datetime.datetime) -> int:
        dt = dt.astimezone(tz=datetime.UTC)
        unix_ns = int(dt.timestamp() * SECOND_NS)
        return unix_ns // self._time_unit

    def _current_elapsed_time(self) -> int:
        return self._to_internal_time(_utcnow()) - self._start_time

    def _to_id(self) -> int:
        max_elapsed_time = (1 << self._bits_time) - 1
        if self._elapsed_time > max_elapsed_time:
            raise OverTimeLimit(max_elapsed_time)

        time = self._elapsed_time << (self._bits_sequence + self._bits_machine_id)
        sequence = self._sequence << self._bits_machine_id
        return time | sequence | self._machine_id

    def _time_part(self, sonyflake_id: int) -> int:
        return sonyflake_id >> (self._bits_sequence + self._bits_machine_id)

    def _sequence_part(self, sonyflake_id: int) -> int:
        mask_sequence = ((1 << self._bits_sequence) - 1) << self._bits_machine_id
        return (sonyflake_id & mask_sequence) >> self._bits_machine_id

    def _machine_id_part(self, sonyflake_id: int) -> int:
        mask_machine_id = (1 << self._bits_machine_id) - 1
        return sonyflake_id & mask_machine_id

    def _sleep(self, overtime: int) -> None:
        now_ns = int(_utcnow().timestamp() * SECOND_NS)
        sleep_ns = (overtime * self._time_unit) - (now_ns % self._time_unit)
        time.sleep(sleep_ns / SECOND_NS)

    async def _sleep_async(self, overtime: int) -> None:
        now_ns = int(_utcnow().timestamp() * SECOND_NS)
        sleep_ns = (overtime * self._time_unit) - (now_ns % self._time_unit)
        await asyncio.sleep(sleep_ns / SECOND_NS)

    def __repr__(self) -> str:
        start_time = str(datetime.datetime.fromtimestamp((self._start_time * self._time_unit) / SECOND_NS, tz=datetime.UTC))
        elapsed_time = str(datetime.timedelta(seconds=(self._elapsed_time * self._time_unit) / SECOND_NS))
        time_unit = str(datetime.timedelta(seconds=self._time_unit / SECOND_NS))
        return (
            f"{self.__class__.__name__}("
            f"bits_machine_id={self._bits_machine_id!r}, "
            f"bits_sequence={self._bits_sequence!r}, "
            f"bits_time={self._bits_time!r}, "
            f"elapsed_time={elapsed_time!r}, "
            f"machine_id={self._machine_id!r}, "
            f"sequence={self._sequence!r}, "
            f"start_time={start_time!r}, "
            f"time_unit={time_unit!r})"
        )
