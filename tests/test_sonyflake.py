# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import concurrent.futures as cf
import datetime
import ipaddress
import os
from typing import TYPE_CHECKING

import pytest

from sonyflake.sonyflake import (
    DEFAULT_BITS_MACHINE_ID,
    SECOND_NS,
    InvalidBitsMachineID,
    InvalidBitsSequence,
    InvalidBitsTime,
    InvalidMachineID,
    InvalidSequence,
    InvalidTimeUnit,
    MachineIDCheckFailure,
    NoPrivateAddress,
    OverTimeLimit,
    Sonyflake,
    StartTimeAhead,
    _lower_16bit_private_ip,
    _pick_private_ip,
    _utcnow,
)

if TYPE_CHECKING:
    from sonyflake.sonyflake import DecomposedSonyflake

# TODO: Add a test for testing to_time somehow.


class TestSonyflake:
    def test_invalid_bits_time(self) -> None:
        with pytest.raises(InvalidBitsTime):
            Sonyflake(bits_sequence=16, bits_machine_id=16, start_time=_utcnow())

    def test_invalid_bits_sequence(self) -> None:
        with pytest.raises(InvalidBitsSequence):
            Sonyflake(bits_sequence=-1, start_time=_utcnow())

    def test_invalid_bits_machine_id(self) -> None:
        with pytest.raises(InvalidBitsMachineID):
            Sonyflake(bits_machine_id=31, start_time=_utcnow())

    def test_invalid_time_unit(self) -> None:
        with pytest.raises(InvalidTimeUnit):
            Sonyflake(time_unit=datetime.timedelta(microseconds=1), start_time=_utcnow())

    def test_start_time_ahead(self) -> None:
        with pytest.raises(StartTimeAhead):
            Sonyflake(start_time=_utcnow() + datetime.timedelta(minutes=1))

    def test_too_large_machine_id(self) -> None:
        with pytest.raises(InvalidMachineID):
            Sonyflake(machine_id=1 << DEFAULT_BITS_MACHINE_ID, start_time=_utcnow())

    def test_negative_machine_id(self) -> None:
        with pytest.raises(InvalidMachineID):
            Sonyflake(machine_id=-1, start_time=_utcnow())

    def test_check_failure_machine_id(self) -> None:
        with pytest.raises(MachineIDCheckFailure):
            Sonyflake(check_machine_id=lambda _: False, start_time=_utcnow())

    def test_pick_private_ip_single_valid_private(self) -> None:
        ips = ["192.168.0.1"]
        ip = _pick_private_ip(ips)
        assert isinstance(ip, ipaddress.IPv4Address)
        assert str(ip) == "192.168.0.1"

    def test_pick_private_ip_raises_on_empty_list(self) -> None:
        with pytest.raises(NoPrivateAddress):
            _pick_private_ip([])

    def test_pick_private_ip_with_public_and_private(self) -> None:
        ips = ["8.8.8.8", "10.0.0.5", "1.1.1.1"]
        ip = _pick_private_ip(ips)
        assert str(ip) == "10.0.0.5"

    def test_pick_private_ip_raises_when_no_private(self) -> None:
        ips = ["8.8.8.8", "1.1.1.1", "127.0.0.1"]
        with pytest.raises(NoPrivateAddress):
            _pick_private_ip(ips)

    def test_pick_private_ip_first_of_multiple_private_ips(self) -> None:
        ips = ["172.16.0.1", "192.168.0.1", "10.0.0.1"]
        ip = _pick_private_ip(ips)
        assert str(ip) == "172.16.0.1"

    @staticmethod
    def _compose_and_decompose_assertions(
        parts: DecomposedSonyflake, expected_time: int, sequence: int, machine_id: int
    ) -> None:
        assert parts.time == expected_time
        assert parts.sequence == sequence
        assert parts.machine_id == machine_id

    def test_compose_and_decompose_zero_values(self) -> None:
        now = _utcnow()
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=now)

        id_ = sf.compose(now, 0, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, 0)

    def test_compose_and_decompose_max_sequence(self) -> None:
        now = _utcnow()
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=now)

        max_sequence = (1 << sf._bits_sequence) - 1
        id_ = sf.compose(now, max_sequence, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, max_sequence, 0)

    def test_compose_and_decompose_max_machine_id(self) -> None:
        now = _utcnow()
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=now)

        max_machine_id = (1 << sf._bits_machine_id) - 1
        id_ = sf.compose(now, 0, max_machine_id)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, max_machine_id)

    def test_compose_and_decompose_future_time(self) -> None:
        now = _utcnow()
        future_time = now + datetime.timedelta(hours=1)
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=now)

        id_ = sf.compose(future_time, 0, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(future_time) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, 0)

    def test_compose_start_time_ahead(self) -> None:
        now = _utcnow()
        sf = Sonyflake(start_time=now)

        with pytest.raises(StartTimeAhead):
            sf.compose(now - datetime.timedelta(seconds=1), 0, 0)

    def test_compose_over_time_limit(self) -> None:
        now = _utcnow()
        sf = Sonyflake(start_time=now, time_unit=datetime.timedelta(milliseconds=1))

        future_time = now + datetime.timedelta(days=365 * 175)
        with pytest.raises(OverTimeLimit):
            sf.compose(future_time, 0, 0)

    def test_compose_invalid_sequence(self) -> None:
        now = _utcnow()
        sf = Sonyflake(start_time=now)

        invalid_sequence = 1 << sf._bits_sequence
        with pytest.raises(InvalidSequence):
            sf.compose(now, invalid_sequence, 0)

    def test_compose_invalid_machine_id(self) -> None:
        now = _utcnow()
        sf = Sonyflake(start_time=now)

        invalid_machine_id = 1 << sf._bits_machine_id
        with pytest.raises(InvalidMachineID):
            sf.compose(now, 0, invalid_machine_id)

    def test_next_id(self) -> None:
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=_utcnow())

        previous_id = sf.next_id()
        previous_time = sf._time_part(previous_id)
        previous_sequence = sf._sequence_part(previous_id)
        machine_id = _lower_16bit_private_ip()

        for _ in range(1000):
            current_id = sf.next_id()

            assert sf._machine_id_part(current_id) == machine_id

            current_time = sf._time_part(current_id)
            current_sequence = sf._sequence_part(current_id)

            assert current_id > previous_id

            if current_time == previous_time:
                assert current_sequence > previous_sequence
            else:
                assert current_time > previous_time
                assert current_sequence == 0

            previous_id = current_id
            previous_time = current_time
            previous_sequence = current_sequence

    def test_next_id_raises_error(self) -> None:
        sf = Sonyflake(start_time=_utcnow())
        ticks_per_year = int(365 * 24 * 60 * 60 * SECOND_NS) // sf._time_unit

        sf._start_time -= 174 * ticks_per_year
        sf.next_id()
        sf._start_time -= 1 * ticks_per_year

        with pytest.raises(OverTimeLimit):
            sf.next_id()

    # Multithreaded parellelism test -> sync.
    def test_next_id_in_parallel(self) -> None:
        start_time = _utcnow()
        sf1 = Sonyflake(machine_id=1, start_time=start_time)
        sf2 = Sonyflake(machine_id=2, start_time=start_time)

        num_cpus = os.cpu_count() or 8
        num_id = 1000
        ids: set[int] = set()

        def generate_ids(sf: Sonyflake) -> list[int]:
            return [sf.next_id() for _ in range(num_id)]

        with cf.ThreadPoolExecutor(max_workers=num_cpus) as executor:
            futures: list[cf.Future[list[int]]] = []
            for _ in range(num_cpus // 2):
                futures.append(executor.submit(generate_ids, sf1))
                futures.append(executor.submit(generate_ids, sf2))

            for future in cf.as_completed(futures):
                for id_ in future.result():
                    assert id_ not in ids
                    ids.add(id_)

    @pytest.mark.asyncio
    async def test_next_id_async(self) -> None:
        sf = Sonyflake(time_unit=datetime.timedelta(milliseconds=1), start_time=_utcnow())

        previous_id = await sf.next_id_async()
        previous_time = sf._time_part(previous_id)
        previous_sequence = sf._sequence_part(previous_id)
        machine_id = _lower_16bit_private_ip()

        for _ in range(1000):
            current_id = await sf.next_id_async()

            assert sf._machine_id_part(current_id) == machine_id

            current_time = sf._time_part(current_id)
            current_sequence = sf._sequence_part(current_id)

            assert current_id > previous_id

            if current_time == previous_time:
                assert current_sequence > previous_sequence
            else:
                assert current_time > previous_time
                assert current_sequence == 0

            previous_id = current_id
            previous_time = current_time
            previous_sequence = current_sequence

    # Signle threaded concurrency test.
    @pytest.mark.asyncio
    async def test_next_id_async_concurrently(self) -> None:
        start_time = _utcnow()
        sf1 = Sonyflake(machine_id=1, start_time=start_time)
        sf2 = Sonyflake(machine_id=2, start_time=start_time)

        num_cpus = os.cpu_count() or 8
        num_ids = 1000
        ids: set[int] = set()

        async def generate_ids(sf: Sonyflake) -> list[int]:
            return [await sf.next_id_async() for _ in range(num_ids)]

        tasks: list[asyncio.Task[list[int]]] = []
        for _ in range(num_cpus // 2):
            tasks.append(asyncio.create_task(generate_ids(sf1)))
            tasks.append(asyncio.create_task(generate_ids(sf2)))

        for coro in asyncio.as_completed(tasks):
            result = await coro
            for id_ in result:
                assert id_ not in ids
                ids.add(id_)

    @pytest.mark.asyncio
    async def test_next_id_async_raises_error(self) -> None:
        sf = Sonyflake(start_time=_utcnow())
        ticks_per_year = int(365 * 24 * 60 * 60 * SECOND_NS) // sf._time_unit

        sf._start_time -= 174 * ticks_per_year
        await sf.next_id_async()

        sf._start_time -= 1 * ticks_per_year
        with pytest.raises(OverTimeLimit):
            await sf.next_id_async()

    # Multithreaded parellelism test -> sync + async
    def test_next_id_sync_async_in_parallel(self) -> None:
        start_time = _utcnow()
        sf1 = Sonyflake(machine_id=1, start_time=start_time)
        sf2 = Sonyflake(machine_id=2, start_time=start_time)

        num_cpus = os.cpu_count() or 8
        num_id = 1000
        ids: set[int] = set()

        def generate_ids(sf: Sonyflake) -> list[int]:
            return [sf.next_id() for _ in range(num_id)]

        async def generate_ids_async(sf: Sonyflake) -> list[int]:
            return [await sf.next_id_async() for _ in range(num_id)]

        with cf.ThreadPoolExecutor(max_workers=num_cpus) as executor:
            futures: list[cf.Future[list[int]]] = []
            for _ in range(num_cpus // 2):
                futures.append(executor.submit(generate_ids, sf1))
                futures.append(executor.submit(lambda: asyncio.run(generate_ids_async(sf2))))

            for future in cf.as_completed(futures):
                for id_ in future.result():
                    assert id_ not in ids
                    ids.add(id_)
