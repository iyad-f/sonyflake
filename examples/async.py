import asyncio
import datetime

from sonyflake import Sonyflake


def check_machine_id(machine_id: int) -> bool:
    # pretend 100, 101, 102 arent valid machine ids.
    return machine_id not in (100, 101, 102)


async def main() -> None:
    start_time = datetime.datetime(2025, 1, 1, 0, 0, 0, 0, datetime.UTC)
    time_unit = datetime.timedelta(milliseconds=1)
    sf = Sonyflake(
        bits_sequence=12,
        bits_machine_id=10,
        time_unit=time_unit,
        start_time=start_time,
        machine_id=120,
        check_machine_id=check_machine_id,
    )
    print(sf)
    next_id = await sf.next_id_async()
    print(next_id)
    print(sf.to_time(next_id))
    print(sf.compose(datetime.datetime.now(datetime.UTC), 0, 0))
    print(sf.decompose(next_id))


asyncio.run(main())
