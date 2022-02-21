from datetime import datetime
import random

SKETYL_EPOCH = 1643000000000


def generate_id():
    sketyl_millis = int(datetime.utcnow().timestamp() * 1000 - SKETYL_EPOCH)
    random_id = "".join(random.choice("0123456789") for _ in range(3))
    encoded = str((sketyl_millis << 13) + (2 ** 13))
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


key_signature_map = {
    0: "C",
    1: "C#",
    2: "D",
    3: "E♭",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "A♭",
    9: "A",
    10: "B♭",
    11: "B",
}


def readable_audio_features(features):
    return {
        "Key Signature": key_signature_map[features["key"]]
        + " "
        + ("minor" if features["mode"] == 0 else "Major"),
        "Tempo": f"{round(features['tempo'])} BPM ({get_tempo_name(features['tempo'])})",
    }


def get_tempo_name(tempo):
    if tempo < 40:
        return "Grave"
    if 40 <= tempo < 45:
        return "Lento"
    if 45 <= tempo < 55:
        return "Largo"
    if 55 <= tempo < 65:
        return "Adagio"
    if 65 <= tempo < 69:
        return "Adagietto"
    if 73 <= tempo < 86:
        return "Andante"
    if 86 <= tempo < 98:
        return "Moderato"
    if 98 <= tempo < 109:
        return "Allegretto"
    if 109 <= tempo < 132:
        return "Allegro"
    if 132 <= tempo < 140:
        return "Vivace"
    if 140 <= tempo < 177:
        return "Presto"
    if tempo > 177:
        return "Prestissimo"
