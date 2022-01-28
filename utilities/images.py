
from email.mime import base
import io
import itertools
import base64

from PIL import Image, ImageFont, ImageDraw

colors = [
    '#e6194b',
    '#3cb44b',
    '#ffe119',
    '#4363d8',
    '#f58231',
    '#911eb4',
    '#46f0f0',
    '#f032e6',
    '#bcf60c',
    '#fabebe',
    '#008080',
    '#e6beff',
    '#9a6324',
    '#fffac8',
    '#800000',
    '#aaffc3',
    '#808000',
    '#ffd8b1',
    '#000075',
    '#808080',
    '#ffffff',
    '#000000',
]




def draw_piechart(decades):
    decades = dict(itertools.islice(decades.items(), 20))
    total_tracks = sum(len(x) for x in decades.values())

    img = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    shape = [(0, 0), (1000, 1000)]
    start = 0

    iteration = 0
    for decade in decades:
        iteration += 1
        end = 360 * (len(decades[decade]) / total_tracks) + start
        draw.arc(
            shape,
            start=start,
            end=end,
            fill=colors[iteration],
            width=200,
        )
        start = end

    img.resize((100, 100), Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, "png")
    buffer.seek(0)
    image_data = base64.b64encode(buffer.getvalue()).decode()
    image_src = f"data:image/png;base64,{image_data}"
    return image_src

def draw_legend(decades):
    decades = dict(itertools.islice(decades.items(), 20))

    img = Image.new("RGBA", (500, 1000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    shape = [(0, 0), (500, 1000)]

    draw.rectangle((1850, 800, 1925, 875), fill=Colors.GRAY, outline=(0, 0, 0))
    draw.text(
        (1950, 810),
        f"Offline: {offline/total:.2%}",
        fill=Colors.WHITE,
        font=font,
    )