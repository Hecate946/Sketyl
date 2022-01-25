from datetime import datetime
import random

SKETYL_EPOCH = 1643000000000


def generate_id():
    sketyl_millis = int(datetime.utcnow().timestamp() * 1000 - SKETYL_EPOCH)
    random_id = "".join(random.choice("0123456789") for _ in range(5))
    encoded = str((sketyl_millis << 17) + (2 ** 17))
    return int(encoded + random_id)
