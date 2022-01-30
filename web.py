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

from utilities import http, spotify, constants


class Sketyl(Quart):
    def __init__(self, name):
        super().__init__(name)
        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        kwargs = {
            "command_timeout": 60,
            "max_size": 20,
            "min_size": 20,
        }

        self.cxn = self.loop.run_until_complete(
            asyncpg.create_pool(config.POSTGRES.uri, **kwargs)
        )
        self.loop.run_until_complete(self.initialize())

        self.stats = {}

        self.secret_key = secrets.token_urlsafe(64)

    def run(self):
        super().run(host="0.0.0.0", port=3000, loop=self.loop)

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

# @app.teardown_appcontext
# async def close(error):
#     await app.cxn.close()
#     print("Closed db connection.")
#     await app.session.close()
#     print("Closed aiohttp connection.")


@app.route("/")
async def index():
    user_id = request.cookies.get("user_id")
    return await render_template("index.html", user_id=user_id)


@app.route("/spotify")
async def _spotify():
    return await render_template("spotify/main.html")


@app.route("/spotify/connect")
async def spotify_connect():
    code = request.args.get("code")
    # We don't mind if they're re-authorizing, just give them the same id.
    user_id = request.cookies.get("user_id")

    if not code:  # Need code, redirect user to spotify
        return redirect(spotify.Oauth(app).get_auth_url())

    token_info = await spotify.Oauth(app).request_access_token(code)
    if not token_info:  # Invalid code or user rejection, redirect them back.
        return redirect(spotify.Oauth(app).get_auth_url())

    sp_user = await spotify.User.from_token(
        token_info, app, user_id=user_id
    )  # Save user
    redirect_location = session.pop("referrer", url_for("_spotify"))
    response = await make_response(redirect(redirect_location))
    print("made response")
    response.set_cookie(
        "user_id",
        str(sp_user.user_id),
        expires=datetime.utcnow() + timedelta(days=365),
    )
    print("set cookie")
    return response


@app.route("/spotify/disconnect")
async def spotify_disconnect():
    user_id = request.cookies.get("user_id")
    if not user_id:
        return "You are not logged in"

    query = """
            DELETE FROM spotify_auth
            WHERE user_id = $1
            """
    await app.cxn.execute(query, int(user_id))
    response = await make_response(redirect(url_for("_spotify")))
    response.set_cookie("user_id", "", expires=0)
    return response


@app.route("/spotify/track/<track_id>")
async def spotify_track(track_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_track", track_id=track_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_track", track_id=track_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_track(track_id)
    return str(data)

@app.route("/spotify/artist/<artist_id>")
async def spotify_artist(artist_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_artist", artist_id=artist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_artist", artist_id=artist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_artist(artist_id)
    return str(data)

@app.route("/spotify/recent")
async def spotify_recent():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    tracks = await user.get_recent_tracks()
    features = await user.get_all_audio_features([i["track"]["id"] for i in tracks["items"]])
    data = spotify.formatting.recent_tracks(tracks["items"], features)
    caption = "Recent Tracks"
    html = await render_template("spotify/tracks.html", recent=True, tracks=tracks["items"], data=data, caption=caption)
    # await emailer.send_email("hecate946@gmail.com", html=html)
    return html

@app.route("/spotify/liked")
async def spotify_liked():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_liked"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_liked"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    tracks = await user.get_all_liked_tracks()
    features = await user.get_all_audio_features([i["track"]["id"] for i in tracks])
    data = spotify.formatting.liked_tracks(tracks, features)
    caption = "Liked Tracks"
    html = await render_template("spotify/tracks.html", liked=True, tracks=tracks, data=data, caption=caption)
    # await emailer.send_email("hecate946@gmail.com", html=html)
    return html


@app.route("/p")
async def p():
    user_id = request.cookies.get("user_id")
    user = await spotify.User.from_id(user_id, app)
    token = await user.get_token()
    return await render_template('spotify/player.html', token=token)

@app.route("/t")
async def t():
    #return await render_template("spotify/pie.html", labels=["2", "1", "3", "4", "5"])
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    decades = await user.get_decades()
    return await render_template(
        "/spotify/charts.html",
        decades=decades,
        labels = list(decades.keys()),
        data=[len(decades[decade]) for decade in decades],
        colors=constants.colors[:len(decades.keys())]
    )


@app.route("/spotify/albums")
async def spotify_albums():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_all_saved_albums()
    albums = spotify.formatting.albums(data)
    caption = ("Showing your saved Spotify albums.",)
    return await render_template(
        "/spotify/tables.html", albums=True, data=albums, caption=caption
    )

@app.route("/spotify/albums/<album_id>")
async def spotify_albums_id(album_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_albums_id", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_albums_id", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    album = await user.get_album(album_id)
    data = await user.get_all_album_tracks(album_id)
    tracks = spotify.formatting.album(data, album)
    caption = (f"Showing tracks in \"{album['name']}\".",)
    return await render_template(
        "/spotify/tables.html", album=True, data=tracks, caption=caption
    )


@app.route("/spotify/playlists")
async def spotify_playlists():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_playlists"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(int(user_id), app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_playlists"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_all_playlists()
    playlists = spotify.formatting.playlists(data)
    caption = ("Showing your Spotify playlists.",)
    return await render_template(
        "/spotify/tables.html", playlists=True, data=playlists, caption=caption
    )


@app.route("/spotify/playlists/create/<spotify_type>")
async def create_playlist(spotify_type):
    user_id = request.cookies.get("user_id")
    time_range = request.args.get("time_range", "short_term")

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "create_playlist", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "create_playlist", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    if spotify_type == "recent":
        await user.create_recent_tracks_playlist()

    if spotify_type == "top":
        await user.create_top_tracks_playlist(time_range=time_range)

    if spotify_type == "liked":
        await user.create_liked_tracks_playlist()

    return "created playlist"


@app.route("/spotify/playlists/<playlist_id>")
async def playlists(playlist_id):
    user_id = request.cookies.get("user_id")
    raw = request.args.get("raw", False)

    if not user_id:  # User is not logged in to discord, redirect them back
        session["referrer"] = url_for(
            "playlists", playlist_id=playlist_id, raw=raw
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    data = await user.get_playlist(playlist_id)
    if raw:
        return str(data)
    playlist = spotify.formatting.playlist(data)
    return await render_template(
        "spotify/tables.html", data=playlist, caption=data["name"]
    )


@app.route("/spotify/top/<spotify_type>")
async def spotify_top(spotify_type):
    user_id = request.cookies.get("user_id")
    time_range = request.args.get("time_range", "short_term")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_top", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "spotify_top", spotify_type=spotify_type, time_range=time_range
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    if spotify_type == "artists":
        data = await user.get_all_top_artists(time_range=time_range)
        artists = spotify.formatting.top_artists(data)
        caption = spotify.formatting.get_caption("artists", time_range)
        return await render_template(
            "spotify/tables.html", artist=True, data=artists, caption=caption
        )

    if spotify_type == "tracks":
        tracks = await user.get_all_top_tracks(time_range=time_range)
        features = await user.get_all_audio_features([t["id"] for t in tracks])
        data = spotify.formatting.top_tracks(tracks, features)
        caption = "Top Tracks"
        return await render_template(
            "spotify/tracks.html", top=True, data=data, caption=caption, tracks=json.dumps(data)
        )

    if spotify_type == "genres":
        data = await user.get_top_genres(time_range=time_range)
        genres = spotify.formatting.top_genres(data)
        caption = spotify.formatting.get_caption("genres", time_range)
        return await render_template(
            "spotify/tables.html", genres=True, data=genres, caption=caption
        )


@app.route("/spotify/following")
async def spotify_following():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_following",
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "spotify_following",
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_all_followed_artists()

    artists = spotify.formatting.top_artists(data)
    caption = ("Showing all artists you follow.",)
    return await render_template(
        "spotify/tables.html", artists=True, data=artists, caption=caption
    )


@app.route("/spotify/friends")
async def spotify_friends():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_following",
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:
        session["referrer"] = url_for(
            "spotify_following",
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    friends = await user.get_friends()

    return str(friends)


if __name__ == "__main__":
    app.run()
