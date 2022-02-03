# Generates ./json/genres.json

import json
from bs4 import BeautifulSoup

data = {}


async def scrape(app):
    url = "https://everynoise.com/everynoise1d.cgi?scope=all"
    page_html = await app.http.get(url, res_method="text")

    soup = BeautifulSoup(page_html, features="html.parser")
    trs = soup.findAll("tr", {"valign": "top"})
    for el in trs:
        atags = el.findAll("a")
        playlist_id = atags[0]["href"].split(":")[-1]
        genre = atags[1].contents[0]
        data.update({genre.lower(): playlist_id})

    with open("./static/json/genres.json", "w") as fp:
        json.dump(data, fp, indent=2)


if __name__ == "main":
    scrape()
