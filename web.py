from datetime import datetime, timedelta
import os
import json
import asyncio
import aiohttp
import asyncpg
import secrets

from quart import (
    Quart,
    request,
    redirect,
    url_for,
    render_template,
    session,
    jsonify,
    make_response,
)


import config

from utilities import http, spotify, utils


class Sketyl(Quart):
    def __init__(self, name):
        super().__init__(name)
        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.cxn = self.loop.run_until_complete(
            asyncpg.create_pool(config.POSTGRES.uri)
        )
        self.loop.run_until_complete(self.initialize())

        self.stats = {}

        self.secret_key = secrets.token_urlsafe(64)

    def run(self):
        return super().run(host="0.0.0.0", port=3000, loop=self.loop)

    async def initialize(self):
        if not hasattr(self, "session"):
            self.session = aiohttp.ClientSession(loop=self.loop)

        if not hasattr(self, "http"):
            self.http = http.Utils(self.session)

        await self.scriptexec()

    async def scriptexec(self):
        # We execute the SQL scripts to make sure we have all our tables.
        for script in os.listdir("./scripts"):
            with open("./scripts/" + script, "r", encoding="utf-8") as script:
                await self.cxn.execute(script.read())


app = Sketyl(__name__)


@app.route("/")
async def index():
    user_id = request.cookies.get("user_id")
    print(user_id)
    if not user_id:
        response = await make_response("Hello")
        response.set_cookie("user_id", str(user_id))
        return response
    return "Hello"


@app.route("/spotify")
async def _spotify():
    return await render_template("spotify.html")


@app.route("/spotify/connect")
async def spotify_connect():
    code = request.args.get("code")
    # We don't mind if they're re-authorizing, just give them the same id.
    print(request.cookies.get("user_id"))
    user_id = int(request.cookies.get("user_id", utils.generate_id()))

    if not code:  # Need code, redirect user to spotify
        return redirect(spotify.Oauth(app).get_auth_url())

    token_info = await spotify.Oauth(app).request_access_token(code)
    if not token_info:  # Invalid code or user rejection, redirect them back.
        return redirect(spotify.Oauth(app).get_auth_url())

    await spotify.User.from_token(token_info, app, user_id=user_id)  # Save user
    response = await make_response(await render_template("/spotify/success.html"))
    response.set_cookie(
        "user_id",
        str(user_id),
        expires=datetime.utcnow() + timedelta(days=365),
    )
    return response


@app.route("/spotify/recent")
async def spotify_recent():
    user_id = session.get("user_id")

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("discord_login"))

    user = await spotify.User.load(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_recently_played()
    tracks = spotify.formatting.recent_tracks(data)
    caption = spotify.formatting.get_caption("recents")
    return await render_template("spotify/tables.html", data=tracks, caption=caption)


@app.route("/spotify/playlists/create/<spotify_type>")
async def create_playlist(spotify_type):
    user_id = session.get("user_id")
    time_range = request.args.get("time_range", "short_term")

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "create_playlist", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("discord_login"))

    user = await spotify.User.load(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "create_playlist", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    if spotify_type == "recent":
        await user.create_recent_tracks_playlist()

    if spotify_type == "top":
        await user.create_top_tracks_playlist(time_range=time_range)

    return "created playlist"


@app.route("/spotify/playlists/<playlist_id>")
async def playlists(playlist_id):
    user_id = session.get("user_id")
    raw = request.args.get("raw", False)

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "playlists", playlist_id=playlist_id, raw=raw
        )  # So they'll send the user back here
        return redirect(url_for("discord_login"))

    user = await spotify.User.load(user_id, app)
    data = await user.get_playlist(playlist_id)
    if raw:
        return str(data)
    playlist = spotify.formatting.playlist(data)
    return await render_template(
        "spotify/tables.html", data=playlist, caption=data["name"]
    )


@app.route("/spotify/top/<spotify_type>")
async def spotify_top(spotify_type):
    user_id = session.get("user_id")
    time_range = request.args.get("time_range", "short_term")

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "spotify_top", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("discord_login"))

    user = await spotify.User.load(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "spotify_top", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    if spotify_type == "artists":
        data = await user.get_top_artists(time_range=time_range)
        artists = spotify.formatting.top_artists(data)
        caption = spotify.formatting.get_caption("artists", time_range)
        return await render_template(
            "spotify/tables.html", artist=True, data=artists, caption=caption
        )

    if spotify_type == "tracks":
        data = await user.get_top_tracks(time_range=time_range)
        tracks = spotify.formatting.top_tracks(data)
        caption = spotify.formatting.get_caption("tracks", time_range)
        return await render_template(
            "spotify/tables.html", track=True, data=tracks, caption=caption
        )

    if spotify_type == "genres":
        data = await user.get_top_genres(time_range=time_range)
        genres = spotify.formatting.top_genres(data)
        caption = spotify.formatting.get_caption("genres", time_range)
        return await render_template(
            "spotify/tables.html", genre=True, data=genres, caption=caption
        )


if __name__ == "__main__":
    app.run()
