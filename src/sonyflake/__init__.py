"""A distributed unique ID generator inspired by Twitter's Snowflake.

:copyright: (c) 2025-present Iyad
:license: Apache License, Version 2.0, see LICENSE for more details.
"""

__title__ = "sonyflake"
__author__ = "Iyad"
__license__ = "Apache-2.0"
__copyright__ = "Copyright 2025-present Iyad"
__version__ = "2.0.1"


from .sonyflake import (
    DecomposedSonyflake,
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
    SonyflakeError,
    StartTimeAhead,
)

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
