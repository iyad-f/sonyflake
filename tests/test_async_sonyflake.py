# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest

from sonyflake.sonyflake import AsyncSonyflake, OverTimeLimit, _lower_16bit_private_ip


@pytest.mark.asyncio
class TestAsyncSonyflake:
    async def test_next_id(self) -> None:
        sf = AsyncSonyflake(time_unit=timedelta(milliseconds=1), start_time=datetime.now(UTC))

        previous_id = await sf.next_id()
        previous_time = sf._time_part(previous_id)
        previous_sequence = sf._sequence_part(previous_id)
        machine_id = _lower_16bit_private_ip()

        for _ in range(1000):
            current_id = await sf.next_id()

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

    async def test_next_id_in_parallel(self) -> None:
        start_time = datetime.now(UTC)
        sf1 = AsyncSonyflake(machine_id=1, start_time=start_time)
        sf2 = AsyncSonyflake(machine_id=2, start_time=start_time)

        num_cpus = os.cpu_count() or 8
        num_ids = 1000
        ids: set[int] = set()

        async def generate_ids(sf: AsyncSonyflake) -> list[int]:
            return [await sf.next_id() for _ in range(num_ids)]

        tasks: list[asyncio.Task[list[int]]] = []
        for _ in range(num_cpus // 2):
            tasks.append(asyncio.create_task(generate_ids(sf1)))
            tasks.append(asyncio.create_task(generate_ids(sf2)))

        for coro in asyncio.as_completed(tasks):
            result = await coro
            for id_ in result:
                assert id_ not in ids
                ids.add(id_)

    async def test_next_id_raises_error(self) -> None:
        sf = AsyncSonyflake(start_time=datetime.now(UTC))
        ticks_per_year = int(365 * 24 * 60 * 60 * 1e9) // sf._time_unit

        sf._start_time -= 174 * ticks_per_year
        await sf.next_id()

        sf._start_time -= 1 * ticks_per_year
        with pytest.raises(OverTimeLimit):
            await sf.next_id()

    async def test_to_time(self) -> None:
        start = datetime.now(UTC)
        sf = AsyncSonyflake(time_unit=timedelta(milliseconds=100), start_time=start)

        id_ = await sf.next_id()

        tm = sf.to_time(id_)
        diff = tm - start

        assert timedelta(0) <= diff <= timedelta(microseconds=sf._time_unit / 1000)
