import asyncio
import datetime

from sonyflake import AsyncSonyflake


def check_machine_id(machine_id: int) -> bool:
    # pretend 100, 101, 102 arent valid machine ids.
    return machine_id not in (100, 101, 102)


async def main() -> None:
    start_time = datetime.datetime(2025, 1, 1, 0, 0, 0, 0, datetime.UTC)
    time_unit = datetime.timedelta(milliseconds=1)
    sf = AsyncSonyflake(
        bits_sequence=12,
        bits_machine_id=10,
        time_unit=time_unit,
        start_time=start_time,
        machine_id=120,
        check_machine_id=check_machine_id,
    )
    next_id = await sf.next_id()
    print(next_id)


asyncio.run(main())
