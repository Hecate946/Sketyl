import os
import json
import asyncio
import aiohttp
import asyncpg
import logging
import secrets

from datetime import datetime, timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler

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
from utilities import http, spotify, constants, utils, database


# Set up our website logger
MAX_LOGGING_BYTES = 32 * 1024 * 1024  # 32 MiB
FOLDER = "./logs"
if not os.path.exists(FOLDER):
    os.mkdir(FOLDER)
log = logging.getLogger("sketyl")
log.setLevel(logging.INFO)
handler = RotatingFileHandler(
    filename=f"{FOLDER}/web.log",
    encoding="utf-8",
    mode="w",
    maxBytes=MAX_LOGGING_BYTES,
    backupCount=5,
)
log.addHandler(handler)
fmt = logging.Formatter(
    "{asctime}: [{levelname}] {name} || {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
handler.setFormatter(fmt)


class Sketyl(Quart):
    def __init__(self, name):
        super().__init__(name)
        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.loop.run_until_complete(self.set_sessions())
        self.db = database.DB(self.loop)
        self.secret_key = secrets.token_urlsafe(64)

        self.current_users = {}
        self.owner = "x7vjqlqi759vsiemiqh9ekdoa"  # Hecate946

        self.client = spotify.ClientCredentials(self)

        self.jinja_env.globals.update(
            readable_audio_features=utils.readable_audio_features
        )

    def run(self):
        super().run(host="0.0.0.0", port=3000, loop=self.loop)

    async def set_sessions(self):
        if not hasattr(self, "session"):
            self.session = aiohttp.ClientSession(loop=self.loop)

        if not hasattr(self, "http"):
            self.http = http.Utils(self.session)


app = Sketyl(__name__)


async def get_user():
    user_id = request.cookies.get("user_id")
    if user_id:
        user = app.current_users.get(user_id)
        if user:
            return user
        return await spotify.User.from_id(user_id, app)


def login_required():
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = request.cookies.get("user_id")
            user = None
            if user_id:
                user = app.current_users.get(user_id)
                if user:
                    return await func(*args, **kwargs)

                user = await spotify.User.from_id(user_id, app)

            if not user:  # Haven't connected their account.
                session["referrer"] = url_for(func.__name__)
                return redirect(url_for("spotify_connect"))

            app.current_users[user.id] = user

            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def _tasked_requests(user):
    await user.get_decades()
    await user.get_top_genres()
    for span in spotify.CONSTANTS.TIME_RANGE_MAP.keys():
        await user.get_top_tracks(time_range=span)
        await user.get_top_artists(time_range=span)
    await user.get_recent_tracks()
    await user.get_liked_tracks()


@app.before_first_request
async def speed_loader():
    user = await get_user()
    if user:
        app.loop.create_task(_tasked_requests(user))


@app.route("/")
async def home():
    user = await get_user()
    if not user:
        track = await app.client.get_full_track("3eaJHhtNsKOumLQYU7bnas")
        return await render_template("home.html", title="Featured Song", track=track)

    np = await user.now_playing()
    zone = "short_term"
    if np:
        if np["item"]:
            if np["item"].get("type") == "track":
                track = await app.client.get_full_track(np["item"]["id"])
                title = "Current Track"
            else:
                top_tracks = await user.get_top_tracks()
                track = await app.client.get_full_track(top_tracks[0].id)
                title = "Top Track"
        else:
            top_tracks = await user.get_top_tracks()
            track = await app.client.get_full_track(top_tracks[0].id)
            title = "Top Track"
    else:
        top_tracks = await user.get_top_tracks()
        if top_tracks:
            track = await app.client.get_full_track(top_tracks[0].id)
            title = "Top Track"
        else:
            zone = "long_term"
            top_tracks = await user.get_top_tracks(time_range=zone)
            if top_tracks:
                track = await app.client.get_full_track(top_tracks[0].id)
                title = "Top Track"
            else:  # Srsly? No data.
                track = await app.client.get_full_track("3eaJHhtNsKOumLQYU7bnas")
                return await render_template(
                    "home.html", title="Featured Song", track=track
                )

    decades = await user.get_decades(time_range=zone)
    genres = await user.get_top_genres(time_range=zone)

    return await render_template(
        "main.html",
        title=title,
        track=track,
        genres=list(genres.keys())[:10],
        profile="https://sketyl.com/profile/?id=" + user.id,
        decades=decades,
        labels=json.dumps(list(decades.keys())),
        data=json.dumps([len(decades[decade]) for decade in decades]),
        colors=json.dumps(constants.colors[: len(decades.keys())]),
    )


@app.route("/profile/")
async def profile():
    user_id = request.args.get("id")
    user = await spotify.User.from_id(user_id, app)
    if not user:
        return "Invalid User"

    profile = await user.get_profile()
    username = profile.get("display_name", user.id)
    decades = await user.get_decades()
    top_tracks = await user.get_top_tracks()
    track = None
    if top_tracks:
        track = await app.client.get_full_track(top_tracks[0].id)
    genres = await user.get_top_genres()

    return await render_template(
        "main.html",
        title=f"{username}'s Top Track",
        user=username,
        track=track,
        genres=list(genres.keys())[:10],
        decades=decades,
        labels=json.dumps(list(decades.keys())),
        data=json.dumps([len(decades[decade]) for decade in decades]),
        colors=json.dumps(constants.colors[: len(decades.keys())]),
    )


@app.route("/index")
async def index():
    return await render_template("index.html")


@app.route("/privacy_policy/")
async def privacy_policy():
    return await render_template("privacy.html")


@app.route("/faqs")
async def faq_page():
    return "Did you really think I'd write a FAQ page? I sure hope you didn't."


@app.route("/spotify/connect")
async def spotify_connect():
    code = request.args.get("code")

    if not code:  # Need code, redirect user to spotify
        return redirect(spotify.Oauth(app).get_auth_url())

    token_info = await spotify.Oauth(app).request_access_token(code)
    if not token_info:  # Invalid code or user rejection, redirect them back.
        return redirect(spotify.Oauth(app).get_auth_url())

    sp_user = await spotify.User.from_token(token_info, app)  # Save user
    redirect_location = session.pop("referrer", url_for("home"))
    response = await make_response(redirect(redirect_location))

    response.set_cookie(
        "user_id",
        str(sp_user.id),
        expires=datetime.utcnow() + timedelta(days=365),
    )

    app.current_users[sp_user.id] = sp_user
    app.loop.create_task(_tasked_requests(sp_user))

    return response


@app.route("/spotify/disconnect")
async def spotify_disconnect():
    user_id = request.cookies.get("user_id")
    if not user_id:
        return "You are not logged in"

    await app.db.delete_user(user_id)
    response = await make_response(redirect(url_for("home")))
    response.set_cookie("user_id", "", expires=0)
    app.current_users.pop(user_id, None)
    return response


@app.route("/spotify/recent/")
@login_required()
async def spotify_recent():
    user = await get_user()
    tracks = await user.get_recent_tracks()

    return await render_template(
        "spotify/tracks.html",
        type="recent",
        tracks=tracks,
        track_ids=json.dumps([track.id for track in tracks]),
        caption="Recent Tracks",
    )


@app.route("/spotify/liked/")
@login_required()
async def spotify_liked():
    user = await get_user()
    tracks = await user.get_liked_tracks()

    return await render_template(
        "spotify/tracks.html",
        type="liked",
        tracks=tracks,
        track_ids=json.dumps([track.id for track in tracks]),
        caption="Liked Tracks",
    )


@app.route("/spotify/top_tracks/")
@login_required()
async def spotify_top_tracks():
    span = request.args.get("time_range", "short_term")
    user = await get_user()
    tracks = await user.get_top_tracks(time_range=span)

    return await render_template(
        "spotify/tracks.html",
        type="top",
        tracks=tracks,
        track_ids=json.dumps([track.id for track in tracks]),
        caption="Top Tracks",
    )


@app.route("/spotify/top_artists/")
@login_required()
async def spotify_top_artists():
    span = request.args.get("time_range", "short_term")
    user = await get_user()
    data = await user.get_top_artists(time_range=span)
    artists = [
        spotify.Artist(artist, index=rank) for rank, artist in enumerate(data, start=1)
    ]
    caption = "Top Artists"
    return await render_template(
        "spotify/artists.html", type="top", artists=artists, caption=caption
    )


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

    data = await user.get_saved_albums()
    albums = [
        spotify.Album(album, index=rank) for rank, album in enumerate(data, start=1)
    ]
    caption = "Saved Albums"
    return await render_template("/spotify/albums.html", albums=albums, caption=caption)


@app.route("/spotify/albums/<album_id>")
async def albums(album_id):
    user_id = request.cookies.get("user_id")

    if not user_id:  # User is not logged in, redirect them back
        session["referrer"] = url_for(
            "albums", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    user = await spotify.User.from_id(user_id, app)
    if not user:  # Haven't connected their account.
        session["referrer"] = url_for(
            "albums", album_id=album_id
        )  # So they'll send the user back here
        return redirect(url_for("spotify_connect"))

    data = await user.get_album(album_id)
    track_ids = [t["id"] for t in data["tracks"]["items"]]
    features = await user.get_audio_features(track_ids)
    tracks = [
        spotify.Track(dict(track, album=data), features=af, index=rank)
        for (rank, (track, af)) in enumerate(
            zip(data["tracks"]["items"], features), start=1
        )
    ]
    caption = f"Showing tracks in album \"{data['name']}\"."
    return await render_template("spotify/tracks.html", tracks=tracks, caption=caption)


@app.route("/spotify/playlists")
@login_required()
async def spotify_playlists():
    user = await get_user()
    if user:
        data = await user.get_playlists()
        playlists = [
            spotify.Playlist(playlist, rank=rank)
            for rank, playlist in enumerate(data, start=1)
        ]
        caption = "Saved Playlists"
        return await render_template(
            "/spotify/playlists.html", playlists=playlists, caption=caption
        )


@app.route("/spotify/playlists/<playlist_id>")
@login_required()
async def playlists(playlist_id):
    user = await get_user()

    if playlist_id == "None":
        return ""

    data = await user.get_playlist(playlist_id)
    track_ids = [t["track"]["id"] for t in data["tracks"]["items"]]
    features = await user.get_audio_features(track_ids[:100])
    tracks = [
        spotify.Track(dict(track["track"], audio_features=af))
        for track, af in zip(data["tracks"]["items"][:100], features)
    ]
    return await render_template(
        "spotify/tracks.html",
        tracks=tracks,
        caption=data["name"],
        type="playlist",
    )


@app.route("/g")
async def g():
    return await render_template("spotify/genres.html", genres=constants.spotify_genres)


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
        "spotify:track:" + x for x in data["track_ids"]
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


@app.route("/a")
async def al():
    user_id = request.cookies.get("user_id")
    user = await spotify.User.from_id(user_id, app)
    np = await user.now_playing()
    return str(np)


if __name__ == "__main__":
    app.run()
