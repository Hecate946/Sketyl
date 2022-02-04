import base64
from datetime import datetime, timedelta
import os
import json
import asyncio
from time import time
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


@app.route("/")
async def index():
    return await render_template("home.html")


@app.route("/spotify")
async def _spotify():
    user_id = request.cookies.get("user_id")
    if not user_id: # Have them log in
        return await render_template("spotify/login.html")

    user = await spotify.User.from_id(user_id, app)
    decades = await user.get_decades()

    return await render_template(
        "/spotify/charts.html",
        decades=decades,
        labels=json.dumps(list(decades.keys())),
        data=json.dumps([len(decades[decade]["tracks"]) for decade in decades]),
        colors=json.dumps(constants.colors[: len(decades.keys())]),
    )

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

    response.set_cookie(
        "user_id",
        str(sp_user.user_id),
        expires=datetime.utcnow() + timedelta(days=365),
    )

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
    await app.cxn.execute(query, user_id)
    response = await make_response(redirect(url_for("_spotify")))
    response.set_cookie("user_id", "", expires=0)
    return response


@app.route("/spotify/track/<user_id>")
async def spotify_user(user_id):
    current_user_id = request.cookies.get("user_id")

    if not current_user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_playlist", user_id=user_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    current_user = await spotify.User.from_id(current_user_id, app)
    if not current_user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_playlist", user_id=user_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user_id = await current_user.get_user(user_id)
    return await render_template("spotify/user.html", user_id=user_id)


@app.route("/spotify/track/<playlist_id>")
async def spotify_playlist(playlist_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_playlist", playlist_id=playlist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_playlist", playlist_id=playlist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    playlist = await user.get_playlist(playlist_id)
    return await render_template("spotify/playlist.html", playlist=playlist)


@app.route("/spotify/track/<album_id>")
async def spotify_album(album_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_album", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_album", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    tracks = await user.get_all_album_tracks(album_id)
    features = await user.get_all_audio_features([i["track"]["id"] for i in tracks])
    data = spotify.formatting.liked_tracks(tracks, features)
    caption = "Album Tracks"
    return await render_template(
        "spotify/tracks.html", type="album", tracks=tracks, data=data, caption=caption
    )


@app.route("/spotify/track/<artist_id>")
async def spotify_artist(artist_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_artist", artist_id=artist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_artist", artist_id=artist_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    artist = await user.get_artist(artist_id)
    return await render_template("spotify/artist.html", artist=artist)


@app.route("/spotify/track/<track_id>")
async def spotify_track(track_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_track", track_id=track_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_track", track_id=track_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    track = await user.get_full_track(track_id)
    return await render_template("spotify/track.html", track=track)


@app.route("/spotify/recent")
async def spotify_recent():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_recent"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    tracks = await user.get_recent_tracks()
    features = await user.get_all_audio_features(
        [i["track"]["id"] for i in tracks["items"]]
    )
    data = spotify.formatting.recent_tracks(tracks["items"], features)
    caption = "Recent Tracks"
    html = await render_template(
        "spotify/tracks.html",
        type="recent",
        tracks=tracks["items"],
        data=data,
        caption=caption,
    )
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

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_liked"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    tracks = await user.get_all_liked_tracks()
    features = await user.get_all_audio_features([i["track"]["id"] for i in tracks])
    data = spotify.formatting.liked_tracks(tracks, features)
    caption = "Liked Tracks"
    html = await render_template(
        "spotify/tracks.html", type="liked", tracks=tracks, data=data, caption=caption
    )
    # await emailer.send_email("hecate946@gmail.com", html=html)
    return html


@app.route("/spotify/decades")
async def spotify_decades():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_decades"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_decades"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    decades = await user.get_decades()

    return await render_template(
        "/spotify/charts.html",
        decades=decades,
        labels=json.dumps(list(decades.keys())),
        data=json.dumps([len(decades[decade]["tracks"]) for decade in decades]),
        colors=json.dumps(constants.colors[: len(decades.keys())]),
    )


@app.route("/spotify/albums")
async def spotify_albums():
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_albums"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_all_saved_albums()
    albums = spotify.formatting.albums(data)
    caption = "Saved Albums"
    return await render_template("/spotify/albums.html", albums=albums, caption=caption)


@app.route("/spotify/albums/<album_id>")
async def spotify_albums_id(album_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "spotify_albums_id", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
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

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "spotify_playlists"
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_all_playlists()
    playlists = spotify.formatting.playlists(data)
    caption = "Saved Playlists"
    return await render_template(
        "/spotify/playlists.html", playlists=playlists, caption=caption
    )


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
        artists = await user.get_all_top_artists(time_range=time_range)
        data = spotify.formatting.top_artists(artists)
        caption = "Top Artists"
        return await render_template(
            "spotify/artists.html", type="top", artists=data, caption=caption
        )
        return await render_template(
            "spotify/tables.html", artist=True, data=artists, caption=caption
        )

    if spotify_type == "tracks":
        tracks = await user.get_all_top_tracks(time_range=time_range)
        features = await user.get_all_audio_features([t["id"] for t in tracks])
        data = spotify.formatting.top_tracks(tracks, features)
        caption = "Top Tracks"
        return await render_template(
            "spotify/tracks.html",
            type="top",
            data=data,
            caption=caption,
            tracks=json.dumps(data),
        )

    if spotify_type == "genres":
        data = await user.get_top_genres(time_range=time_range)
        genres = spotify.formatting.top_genres(data)
        caption = spotify.formatting.get_caption("genres", time_range)
        return await render_template(
            "spotify/tables.html", genres=True, data=genres, caption=caption
        )


@app.route("/g")
async def g():
    return await render_template("spotify/genres.html", genres=constants.spotify_genres)


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

    artists = await user.get_all_followed_artists()

    data = spotify.formatting.top_artists(artists)
    caption = "Followed Artists"
    return await render_template(
        "spotify/artists.html", type="followed", artists=data, caption=caption
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


# INTERNALS


@app.route("/spotify/_create_playlist", methods=["POST"])
async def _spotify_create_playlist():
    """Create a playlist from JSON data"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return jsonify(
            response="Unable to create playlist. Please connect your Spotify account and retry."
        )

    user = await spotify.User.from_id(user_id, app)

    data = await request.json
    # Playlist data

    name = data["name"]
    track_uris = [
        "spotify:track:" + x for x in data["track_ids"].split(",")
    ]  # turn track ids into uris
    desc = data.get("description", "")

    playlist = await user.create_playlist(name, desc=desc)
    await user.add_to_playlist(playlist["id"], track_uris)

    return jsonify(response=f"Successfully created playlist: {name}")


@app.route("/spotify/_genre_recommendations", methods=["GET"])
async def _spotify_genre_recommendations():
    user_id = request.cookies.get("user_id")
    if not user_id:
        return jsonify(
            response="Unable to generate recommendations. Please connect your Spotify account and retry."
        )

    user = await spotify.User.from_id(user_id, app)

    data = await request.json
    print(data)
    genre_name = request.args.get("genre")
    print(genre_name)
    recommendations = await user.get_recommendations(seed_genres=genre_name)

    return jsonify(response=recommendations)


@app.route("/spotify/_token", methods=["GET"])
async def _spotify_token():
    user_id = request.cookies.get("user_id")
    if not user_id:
        return jsonify(token=None)
    user = await spotify.User.from_id(user_id, app)
    token = await user.get_token()
    return jsonify(token=token)


@app.route("/p")
async def p():
    user_id = request.cookies.get("user_id")
    user = await spotify.User.from_id(user_id, app)
    token = await user.get_token()
    return await render_template("spotify/player.html", token=token)


if __name__ == "__main__":
    app.run()
