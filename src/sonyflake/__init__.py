"""A python implementation of sonyflake.

:copyright: (c) 2025-present Iyad
:license: Apache License, Version 2.0, see LICENSE for more details.

"""

__title__ = "sonyflake"
__author__ = "Iyad"
__license__ = "Apache-2.0"
__copyright__ = "Copyright 2025-present Iyad"
__version__ = "1.0.0"


from .sonyflake import (
    AsyncSonyflake,
    DecomposedSonyflake,
    InvalidBitsMachineID,
    InvalidBitsSequence,
    InvalidBitsTime,
    InvalidMachineID,
    InvalidSequence,
    InvalidTimeUnit,
    NoPrivateAddress,
    OverTimeLimit,
    Sonyflake,
    SonyflakeError,
    StartTimeAhead,
)

__all__ = (
    "AsyncSonyflake",
    "DecomposedSonyflake",
    "InvalidBitsMachineID",
    "InvalidBitsSequence",
    "InvalidBitsTime",
    "InvalidMachineID",
    "InvalidSequence",
    "InvalidTimeUnit",
    "NoPrivateAddress",
    "OverTimeLimit",
    "Sonyflake",
    "SonyflakeError",
    "StartTimeAhead",
)
