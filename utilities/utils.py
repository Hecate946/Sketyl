from datetime import datetime
import random

SKETYL_EPOCH = 1643000000000


def generate_id():
    sketyl_millis = int(datetime.utcnow().timestamp() * 1000 - SKETYL_EPOCH)
    random_id = "".join(random.choice("0123456789") for _ in range(5))
    encoded = str((sketyl_millis << 17) + (2 ** 17))
    return int(encoded + random_id)


def parse_duration(duration: int):
    """
    Helper function to get visually pleasing
    timestamps from position of song in seconds.
    """
    duration = round(duration)
    if duration > 0:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(str(days))
        if hours > 0:
            duration.append(str(hours))
        if minutes > 0:
            duration.append(str(minutes))
        duration.append("{}".format(str(seconds).zfill(2)))

        value = ":".join(duration)

    elif duration == 0:
        value = "LIVE"

    return value
