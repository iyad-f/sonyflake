# pyright: reportPrivateUsage=false

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonyflake.sonyflake import (
    DEFAULT_BITS_MACHINE_ID,
    InvalidBitsMachineID,
    InvalidBitsSequence,
    InvalidBitsTime,
    InvalidMachineID,
    InvalidSequence,
    InvalidTimeUnit,
    NoPrivateAddress,
    OverTimeLimit,
    StartTimeAhead,
    _BaseSonyflake,
    _pick_private_ip,
)

if TYPE_CHECKING:
    from sonyflake.sonyflake import DecomposedSonyflake


class TestBaseSonyflake:
    def test_invalid_bits_time(self) -> None:
        with pytest.raises(InvalidBitsTime):
            _BaseSonyflake(bits_sequence=16, bits_machine_id=16, start_time=datetime.now(UTC))

    def test_invalid_bits_sequence(self) -> None:
        with pytest.raises(InvalidBitsSequence):
            _BaseSonyflake(bits_sequence=-1, start_time=datetime.now(UTC))

    def test_invalid_bits_machine_id(self) -> None:
        with pytest.raises(InvalidBitsMachineID):
            _BaseSonyflake(bits_machine_id=31, start_time=datetime.now(UTC))

    def test_invalid_time_unit(self) -> None:
        with pytest.raises(InvalidTimeUnit):
            _BaseSonyflake(time_unit=timedelta(microseconds=1), start_time=datetime.now(UTC))

    def test_start_time_ahead(self) -> None:
        with pytest.raises(StartTimeAhead):
            _BaseSonyflake(start_time=datetime.now(UTC) + timedelta(minutes=1))

    def test_too_large_machine_id(self) -> None:
        with pytest.raises(InvalidMachineID):
            _BaseSonyflake(machine_id=1 << DEFAULT_BITS_MACHINE_ID, start_time=datetime.now(UTC))

    def test_negative_machine_id(self) -> None:
        with pytest.raises(InvalidMachineID):
            _BaseSonyflake(machine_id=-1, start_time=datetime.now(UTC))

    def test_invalid_machine_id(self) -> None:
        with pytest.raises(InvalidMachineID):
            _BaseSonyflake(check_machine_id=lambda _: False, start_time=datetime.now(UTC))

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
        parts: DecomposedSonyflake, expected_time: int, sequence: int, machine_id: int, id_: int
    ) -> None:
        assert parts.time == expected_time
        assert parts.sequence == sequence
        assert parts.machine_id == machine_id
        assert parts.id == id_

    def test_compose_and_decompose_zero_values(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(time_unit=timedelta(milliseconds=1), start_time=now)

        id_ = sf.compose(now, 0, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, 0, id_)

    def test_compose_and_decompose_max_sequence(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(time_unit=timedelta(milliseconds=1), start_time=now)

        max_sequence = (1 << sf._bits_sequence) - 1
        id_ = sf.compose(now, max_sequence, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, max_sequence, 0, id_)

    def test_compose_and_decompose_max_machine_id(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(time_unit=timedelta(milliseconds=1), start_time=now)

        max_machine_id = (1 << sf._bits_machine_id) - 1
        id_ = sf.compose(now, 0, max_machine_id)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(now) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, max_machine_id, id_)

    def test_compose_and_decompose_future_time(self) -> None:
        now = datetime.now(UTC)
        future_time = now + timedelta(hours=1)
        sf = _BaseSonyflake(time_unit=timedelta(milliseconds=1), start_time=now)

        id_ = sf.compose(future_time, 0, 0)
        parts = sf.decompose(id_)
        expected_time = sf._to_internal_time(future_time) - sf._start_time

        self._compose_and_decompose_assertions(parts, expected_time, 0, 0, id_)

    def test_compose_start_time_ahead(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(start_time=now)

        with pytest.raises(StartTimeAhead):
            sf.compose(now - timedelta(seconds=1), 0, 0)

    def test_compose_over_time_limit(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(start_time=now, time_unit=timedelta(milliseconds=1))

        future_time = now + timedelta(days=365 * 175)
        with pytest.raises(OverTimeLimit):
            sf.compose(future_time, 0, 0)

    def test_compose_invalid_sequence(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(start_time=now)

        invalid_sequence = 1 << sf._bits_sequence
        with pytest.raises(InvalidSequence):
            sf.compose(now, invalid_sequence, 0)

    def test_compose_invalid_machine_id(self) -> None:
        now = datetime.now(UTC)
        sf = _BaseSonyflake(start_time=now)

        invalid_machine_id = 1 << sf._bits_machine_id
        with pytest.raises(InvalidMachineID):
            sf.compose(now, 0, invalid_machine_id)
