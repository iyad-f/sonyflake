# pyright: reportPrivateUsage=false

from __future__ import annotations

import concurrent.futures as cf
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonyflake.sonyflake import OverTimeLimit, Sonyflake, _lower_16bit_private_ip

if TYPE_CHECKING:
    from concurrent.futures import Future


class TestSonyflake:
    def test_next_id(self) -> None:
        sf = Sonyflake(time_unit=timedelta(milliseconds=1), start_time=datetime.now(UTC))

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

    def test_next_id_in_parallel(self) -> None:
        start_time = datetime.now(UTC)
        sf1 = Sonyflake(machine_id=1, start_time=start_time)
        sf2 = Sonyflake(machine_id=2, start_time=start_time)

        num_cpus = os.cpu_count() or 8
        num_id = 1000
        ids: set[int] = set()

        def generate_ids(sf: Sonyflake) -> list[int]:
            return [sf.next_id() for _ in range(num_id)]

        with cf.ThreadPoolExecutor(max_workers=num_cpus) as executor:
            futures: list[Future[list[int]]] = []
            for _ in range(num_cpus // 2):
                futures.append(executor.submit(generate_ids, sf1))
                futures.append(executor.submit(generate_ids, sf2))

            for future in cf.as_completed(futures):
                for id_ in future.result():
                    assert id_ not in ids
                    ids.add(id_)

    def test_next_id_raises_error(self) -> None:
        sf = Sonyflake(start_time=datetime.now(UTC))
        ticks_per_year = int(365 * 24 * 60 * 60 * 1e9) // sf._time_unit

        sf._start_time -= 174 * ticks_per_year
        sf.next_id()
        sf._start_time -= 1 * ticks_per_year

        with pytest.raises(OverTimeLimit):
            sf.next_id()

    def test_to_time(self) -> None:
        start = datetime.now(UTC)
        sf = Sonyflake(time_unit=timedelta(milliseconds=100), start_time=start)

        id_ = sf.next_id()
        tm = sf.to_time(id_)
        diff = tm - start

        assert timedelta(0) <= diff <= timedelta(microseconds=sf._time_unit / 1000)
