from urllib.parse import urlencode
from collections import Counter, defaultdict
import base64
import time
import json

from datetime import datetime, date
from utilities import utils
from config import SPOTIFY


class CONSTANTS:
    WHITE_ICON = "https://cdn.discordapp.com/attachments/872338764276576266/927649624888602624/spotify_white.png"
    GREEN_ICON = "https://cdn.discordapp.com/attachments/872338764276576266/932399347289706556/spotify_green.png"
    API_URL = "https://api.spotify.com/v1/"
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SCOPES = [
        # Images
        "ugc-image-upload",
        # Spotify connect
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        # Users
        "user-read-private",
        "user-read-email",
        # Follow
        "user-follow-modify",
        "user-follow-read",
        # Library
        "user-library-modify",
        "user-library-read",
        # Listening history
        "user-read-playback-position",
        "user-top-read",
        "user-read-recently-played",
        # Playlists
        "playlist-modify-private",
        "playlist-read-collaborative",
        "playlist-read-private",
        "playlist-modify-public",
        "streaming",
        # "user-read-birthdate",
    ]


class Oauth:
    def __init__(self, bot_or_app):
        self.client_id = SPOTIFY.client_id
        self.client_secret = SPOTIFY.client_secret
        self.redirect_uri = SPOTIFY.redirect_uri
        self.scope = " ".join(CONSTANTS.SCOPES)

        self.client = bot_or_app

    @property
    def headers(self):
        """
        Return proper headers for all token requests
        """
        auth_header = base64.b64encode(
            (self.client_id + ":" + self.client_secret).encode("ascii")
        )
        return {
            "Authorization": "Basic %s" % auth_header.decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def get_auth_url(self, state=None):
        """
        Return an authorization url to get an access code
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(CONSTANTS.SCOPES),
            "show_dialog": True,  # Force them to re-agree
        }
        if state:
            params["state"] = state
        constructed = urlencode(params)
        return "%s?%s" % (CONSTANTS.AUTH_URL, constructed)

    def validate_token(self, token_info):
        """Checks a token is valid"""
        now = int(time.time())
        return token_info["expires_at"] - now < 60

    async def get_access_token(self, user_id, token_info):
        """Gets the token or creates a new one if expired"""
        token_info["expires_at"] = int(time.time()) + token_info["expires_in"]
        if self.validate_token(token_info):
            return token_info["access_token"]

        token_info = await self.refresh_access_token(
            user_id, token_info.get("refresh_token")
        )

        return token_info["access_token"]

    async def refresh_access_token(self, user_id, refresh_token):
        params = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        token_info = await self.client.http.post(
            CONSTANTS.TOKEN_URL, data=params, headers=self.headers, res_method="json"
        )
        if not token_info.get("refresh_token"):
            # Didn't get new refresh token.
            # Old one is still valid.
            token_info["refresh_token"] = refresh_token

        query = """
                INSERT INTO spotify_auth
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET token_info = $2
                WHERE spotify_auth.user_id = $1;
                """
        await self.client.cxn.execute(query, user_id, json.dumps(token_info))

        return token_info

    async def request_access_token(self, code):
        params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        token_info = await self.client.http.post(
            CONSTANTS.TOKEN_URL, data=params, headers=self.headers, res_method="json"
        )
        if not token_info.get("access_token"):  # Something went wrong, return None
            return
        return token_info


class User:  # Spotify user w user_id
    def __init__(self, user_id, token_info, bot_or_app):
        self.user_id = user_id
        self.token_info = token_info
        self.client = bot_or_app
        self.oauth = Oauth(bot_or_app)

    @classmethod
    async def from_id(cls, user_id, bot_or_app):
        query = """
                SELECT token_info
                FROM spotify_auth
                WHERE user_id = $1;
                """
        token_info = await bot_or_app.cxn.fetchval(query, int(user_id))

        if token_info:
            token_info = json.loads(token_info)
            return cls(int(user_id), token_info, bot_or_app)

    @classmethod
    async def from_token(cls, token_info, bot_or_app, *, user_id=None):
        user_id = user_id or utils.generate_id()
        query = """
                INSERT INTO spotify_auth
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET token_info = $2
                WHERE spotify_auth.user_id = $1;
                """
        await bot_or_app.cxn.execute(query, int(user_id), json.dumps(token_info))

        return cls(int(user_id), token_info, bot_or_app)

    async def get_token(self):
        return await self.oauth.get_access_token(self.user_id, self.token_info)

    async def auth(self):
        access_token = await self.get_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        return headers

    async def get(self, url):
        return await self.client.http.get(
            url, headers=await self.auth(), res_method="json"
        )

    async def put(self, url, json=None, res_method=None):
        return await self.client.http.put(
            url, headers=await self.auth(), json=json, res_method=res_method
        )

    async def get_spotify_id(self):
        profile = await self.get_profile()
        return profile["id"]

    async def get_profile(self):
        return await self.get(CONSTANTS.API_URL + "me")

    async def get_playback_state(self):
        return await self.get(CONSTANTS.API_URL + "me/player")

    async def get_currently_playing(self):
        return await self.get(CONSTANTS.API_URL + "me/player/currently-playing")

    async def get_devices(self):
        return await self.get(CONSTANTS.API_URL + "me/player/devices")

    async def get_recommendations(self, limit=100, **kwargs):
        params = {"limit": 100}.update(**kwargs)
        return await self.get(CONSTANTS.API_URL + "recommendations")

    async def transfer_playback(self, devices, play: bool = False):
        return await self.put(
            CONSTANTS.API_URL + "me/player", json={"device_ids": devices, "play": play}
        )

    async def get_recent_tracks(
        self, limit=50, *, before: int = None, after: int = None
    ):
        params = {"limit": limit}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        query_params = urlencode(params)
        return await self.get(
            CONSTANTS.API_URL + "me/player/recently-played?" + query_params
        )

    async def get_liked_tracks(self, limit=50, *, offset=0):
        params = {"limit": limit, "offset": offset}
        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/tracks?" + query_params)

    async def get_all_liked_tracks(self, max_tracks: int = 200):
        liked_tracks = []
        offset = 0
        batch = await self.get_liked_tracks()
        batch_tracks = batch["items"]
        liked_tracks.extend(batch_tracks)
        pred = lambda mt: ((offset + 1) * 50) < mt
        while len(batch_tracks) == 50 and pred(max_tracks):
            offset += 1
            batch = await self.get_liked_tracks(offset=offset * 50)
            batch_tracks = batch["items"]
            liked_tracks.extend(batch_tracks)

        return liked_tracks

    async def get_audio_features(self, track_ids):
        params = {"ids": ",".join(track_ids)}
        query = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "audio-features?" + query)

    async def get_all_audio_features(self, track_ids):
        audio_features = []
        while track_ids:
            batch = track_ids[:100]
            batch_features = await self.get_audio_features(batch)
            audio_features.extend(batch_features["audio_features"])
            track_ids = track_ids[100:]
        return audio_features

    async def get_top_tracks(self, limit=50, time_range="short_term", *, offset=0):
        params = {"limit": limit, "time_range": time_range, "offset": offset}
        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/top/tracks?" + query_params)

    async def get_all_top_tracks(self, time_range="short_term", max_tracks: int = 100):
        top_tracks = []
        offset = 0
        batch = await self.get_top_tracks(time_range=time_range)
        batch_tracks = batch["items"]
        top_tracks.extend(batch_tracks)
        pred = lambda mt: ((offset + 1) * 50) < mt
        while len(batch_tracks) == 50 and pred(max_tracks):
            offset += 1
            batch = await self.get_top_tracks(offset=offset * 50)
            batch_tracks = batch["items"]
            top_tracks.extend(batch_tracks)

        return top_tracks

    async def get_top_artists(self, limit=50, time_range="long_term", *, offset=0):
        params = {"limit": limit, "time_range": time_range, "offset": offset}
        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/top/artists?" + query_params)

    async def get_all_top_artists(
        self, time_range="short_term", max_artists: int = 100
    ):
        top_tracks = []
        offset = 0
        batch = await self.get_top_artists(time_range=time_range)
        batch_tracks = batch["items"]
        top_tracks.extend(batch_tracks)
        pred = lambda ma: ((offset + 1) * 50) < ma
        while len(batch_tracks) == 50 and pred(max_artists):
            offset += 1
            batch = await self.get_top_artists(offset=offset * 50)
            batch_tracks = batch["items"]
            top_tracks.extend(batch_tracks)

        return top_tracks

    async def get_artist_top_tracks(self, artist_id):
        return await self.get(CONSTANTS.API_URL + f"artists/{artist_id}/top_tracks")

    async def get_top_genres(self, limit=50, time_range="long_term"):
        data = await self.get_top_artists(limit, time_range)
        genres = []
        for artist in data["items"]:
            genres.extend(artist["genres"])

        return Counter(genres)

    async def get_genre_seeds(self):
        return await self.get(
            CONSTANTS.API_URL + "recommendations/available-genre-seeds"
        )

    async def get_saved_albums(self, limit=50, *, offset=0):
        params = {"limit": limit, "offset": offset}
        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/albums?" + query_params)

    async def get_album(self, album_id):
        return await self.get(CONSTANTS.API_URL + f"albums/{album_id}")

    async def get_album_tracks(self, album_id, limit=50, *, offset=0):
        params = {"limit": limit, "offset": offset}
        query_params = urlencode(params)
        return await self.get(
            CONSTANTS.API_URL + f"albums/{album_id}/tracks?" + query_params
        )

    async def get_all_album_tracks(self, album_id, max_tracks=1000):
        album_tracks = []
        offset = 0
        batch = await self.get_album_tracks(album_id)
        batch_tracks = batch["items"]
        album_tracks.extend(batch_tracks)
        pred = lambda ma: ma > ((offset + 1) * 50)

        while len(batch_tracks) == 50 and pred(max_tracks):
            offset += 1
            batch = await self.get_album_tracks(album_id, offset=offset * 50)
            batch_tracks = batch["items"]
            album_tracks.extend(batch_tracks)
        return album_tracks

    async def get_all_saved_albums(self, max_albums: int = 1000):
        albums = []
        offset = 0
        batch = await self.get_saved_albums()
        album_batch = batch["items"]
        albums.extend(album_batch)
        pred = lambda ma: ma > ((offset + 1) * 50)

        while len(album_batch) == 50 and pred(max_albums):
            offset += 1
            batch = await self.get_saved_albums(offset=offset * 50)
            album_batch = batch["items"]
            albums.extend(album_batch)
        return albums

    async def pause(self):
        return await self.put(CONSTANTS.API_URL + "me/player/pause")

    async def play(self, **kwargs):
        return await self.put(CONSTANTS.API_URL + "me/player/play", json=kwargs)

    async def play(self, **kwargs):
        return await self.put(CONSTANTS.API_URL + "me/player/play", json=kwargs)

    async def skip_to_next(self):
        return await self.client.http.post(
            CONSTANTS.API_URL + "me/player/next",
            headers=await self.auth(),
            res_method=None,
        )

    async def skip_to_previous(self):
        return await self.client.http.post(
            CONSTANTS.API_URL + "me/player/previous",
            headers=await self.auth(),
            res_method=None,
        )

    async def seek(self, position):
        params = {"position_ms": position * 1000}
        query_params = urlencode(params)
        return await self.put(CONSTANTS.API_URL + "me/player/seek?" + query_params)

    async def repeat(self, option):
        params = {"state": option}
        query_params = urlencode(params)
        return await self.put(CONSTANTS.API_URL + "me/player/repeat?" + query_params)

    async def shuffle(self, option: bool):
        params = {"state": option}
        query_params = urlencode(params)
        return await self.put(CONSTANTS.API_URL + "me/player/shuffle?" + query_params)

    async def volume(self, amount):
        params = {"volume_percent": amount}
        query_params = urlencode(params)
        return await self.put(CONSTANTS.API_URL + "me/player/volume?" + query_params)

    async def enqueue(self, uri):
        params = {"uri": uri}
        query_params = urlencode(params)
        return await self.client.http.post(
            CONSTANTS.API_URL + "me/player/queue?" + query_params,
            headers=await self.auth(),
            res_method=None,
        )

    async def get_followed_artists(self, limit=50, after: str = None):
        params = {"limit": limit, "type": "artist"}
        if after:
            params["after"] = after

        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/following?" + query_params)

    async def get_all_followed_artists(self, max_artists: int = 100):
        artists = []
        batch = await self.get_followed_artists()
        batch_artists = batch["artists"]["items"]
        artists.extend(batch_artists)
        while len(batch_artists) == 50:
            batch = await self.get_followed_artists(batch_artists[-1]["id"])
            batch_artists = batch["artists"]["items"]
            artists.extend(batch_artists)

        return artists

    async def get_friends(self):
        data = await self.get_all_playlists()
        profile = await self.get_profile()
        your_owners = {playlist["owner"]["id"] for playlist in data}
        your_owners.difference_update(["spotify", profile["id"]])
        for owner_username in your_owners:
            playlists = await self.get_all_user_playlists(owner_username)
            their_owners = {playlist["owner"]["id"] for playlist in playlists}
            their_owners.difference_update(["spotify"], owner_username)

        friends = your_owners.intersection(their_owners)
        return friends

    async def get_track(self, track_id):
        return await self.get(CONSTANTS.API_URL + f"tracks/{track_id}")

    async def get_track_features(self, track_id):
        return await self.get(CONSTANTS.API_URL + f"audio-features/{track_id}")

    async def get_full_track(self, track_id):
        """Get track with audio features"""
        track = await self.get_track(track_id)
        track["audio_features"] = await self.get_track_features(track_id)
        return track

    async def get_artist(self, id):
        return await self.get(CONSTANTS.API_URL + f"artists/{id}")

    async def get_user(self, user_id):
        return await self.get(CONSTANTS.API_URL + f"users/{user_id}")

    async def get_user_playlists(self, username, limit=50, *, offset=0):
        params = {"limit": limit, "offset": offset}
        query_params = urlencode(params)
        return await self.get(
            CONSTANTS.API_URL + f"users/{username}/playlists?" + query_params
        )

    async def get_all_user_playlists(self, username, max_playlists: int = 100):
        playlists = []
        offset = 0
        batch = await self.get_user_playlists(username)
        playlist_batch = batch["items"]
        playlists.extend(playlist_batch)
        pred = lambda mp: ((offset + 1) * 50) < mp
        while len(playlist_batch) == 50 and pred(max_playlists):
            offset += 1
            batch = await self.get_user_playlists(username, offset=offset * 50)
            playlist_batch = batch["items"]
            playlists.extend(playlist_batch)

        return playlists

    async def get_playlists(self, limit=50, *, offset=0):
        """Get a user's owned and followed playlists"""
        params = {"limit": limit, "offset": offset}
        query_params = urlencode(params)
        return await self.get(CONSTANTS.API_URL + "me/playlists?" + query_params)

    async def get_all_playlists(self):
        playlists = []
        offset = 0
        batch = await self.get_playlists()
        playlist_batch = batch["items"]
        playlists.extend(playlist_batch)
        while len(playlist_batch) == 50:
            offset += 1
            batch = await self.get_playlists(offset=offset * 50)
            playlist_batch = batch["items"]
            playlists.extend(playlist_batch)

        return playlists

    async def get_playlist(self, playlist_id):
        """Get a user's owned and followed playlists"""
        return await self.get(CONSTANTS.API_URL + f"playlists/{playlist_id}")

    async def get_playlist_tracks(self, playlist_id):
        return await self.get(CONSTANTS.API_URL + f"playlists/{playlist_id}/tracks")

    async def create_playlist(self, name, *, public=True, collab=False, desc=""):
        spotify_id = await self.get_spotify_id()
        data = {
            "name": name,
            "public": public,
            "collaborative": collab,
            "description": desc,
        }
        return await self.client.http.post(
            CONSTANTS.API_URL + f"users/{spotify_id}/playlists",
            data=json.dumps(data),
            headers=await self.auth(),
            res_method="json",
        )

    async def add_to_playlist(self, playlist_id, uris: list, position=None):

        while uris:
            data = {"uris": uris[:100]}  # 100 at a time spotify limit.
            if position:
                data["position"] = position
            snapshot = await self.client.http.post(
                CONSTANTS.API_URL + f"playlists/{playlist_id}/tracks",
                data=json.dumps(data),
                headers=await self.auth(),
                res_method="json",
            )
            uris = uris[100:]
        return snapshot

    async def create_top_tracks_playlist(self, time_range="short_term"):
        name = f"Top Tracks {datetime.utcnow().strftime('%B %d, %Y')}"
        playlist = await self.create_playlist(
            name,
            desc=f"Top tracks in the past {formatting.time_range_map[time_range]} (Generated by Sketyl.com)",
        )

        top_tracks = await self.get_all_top_tracks(time_range=time_range)
        track_uris = [track["uri"] for track in top_tracks]
        return await self.add_to_playlist(playlist["id"], track_uris)

    async def create_recent_tracks_playlist(self):
        name = f"Recent Tracks {datetime.utcnow().strftime('%B %d, %Y')}"
        playlist = await self.create_playlist(
            name, desc="Last 50 most recent listens. (Generated by Sketyl.com)"
        )

        recent_tracks = await self.get_recent_tracks()
        track_uris = [item["track"]["uri"] for item in recent_tracks["items"]]
        return await self.add_to_playlist(playlist["id"], track_uris)

    async def create_liked_tracks_playlist(self):
        name = f"Liked Tracks {datetime.utcnow().strftime('%B %d, %Y')}"
        playlist = await self.create_playlist(
            name, desc="Current liked tracks. (Generated by Sketyl.com)"
        )

        liked_tracks = await self.get_all_liked_tracks()
        track_uris = [item["track"]["uri"] for item in liked_tracks]
        return await self.add_to_playlist(playlist["id"], track_uris)

    async def get_decades(self, time_range="long_term"):
        data = await self.get_all_top_tracks(time_range)
        decade = lambda date: (int(date.split("-")[0]) // 10) * 10
        decades = defaultdict(list)
        for track in data:
            decades[decade(track["album"]["release_date"])].append(track)

        features = await self.get_all_audio_features([t["id"] for t in data])
        return {
            str(decade) + "s": formatting.top_tracks(tracks, features)
            for decade, tracks in sorted(decades.items())
        }


class Formatting:
    def __init__(self) -> None:
        self.time_range_map = {
            "short_term": "four weeks.",
            "medium_term": "six months.",
            "long_term": "few years.",
        }

    def release_date(self, date_str):
        date_parts = date_str.split("-")
        date_parts = [int(dp) for dp in date_parts]
        if len(date_parts) == 1:
            return date_parts[0]

        date_obj = date(*date_parts)

        return date_obj.__format__("%B %d, %Y")

    def get_caption(self, option, time_range="short_term", *, user_type="all"):
        if option == "recents":
            return ("Showing your recent Spotify tracks.",)
        if option == "tracks":
            return (
                f"Showing your top Spotify tracks in the past",
                self.time_range_map[time_range],
            )
        if option == "artists":
            return (
                f"Showing your top Spotify artists in the past",
                self.time_range_map[time_range],
            )
        if option == "genres":
            return (
                f"Showing your top Spotify genres in the past",
                self.time_range_map[time_range],
            )

    def get_image(self, obj):
        try:
            return obj["images"][0]["url"]
        except (IndexError, KeyError):
            return CONSTANTS.GREEN_ICON

    def top_tracks(self, data, audio_features):
        return {
            "track_ids": ",".join([track["id"] for track in data]),
            "tracks": [
                {
                    "id": track["id"],
                    "index": index,
                    "image": self.get_image(track["album"]),
                    "preview": track["preview_url"]
                    or "",  # Sometimes tracks are unavailable
                    "name": track["name"],
                    "artists": [
                        {"name": artist["name"], "id": artist["id"]}
                        for artist in track["artists"]
                    ],
                    "duration": utils.parse_duration(track["duration_ms"] / 1000),
                    "album": track["album"]["name"],
                    "json": json.dumps(
                        dict(track, rank=index, audio_features=features)
                    ),
                }
                for index, (track, features) in enumerate(
                    zip(data, audio_features), start=1
                )
            ],
        }

    def album(self, tracks, album):
        return {
            "track_ids": ",".join([track["id"] for track in tracks]),
            "tracks": [
                {
                    "id": track["id"],
                    "index": index,
                    "image": self.get_image(album),
                    "preview": track["preview_url"],
                    "name": track["name"],
                    "artist": ", ".join(
                        [artist["name"] for artist in track["artists"]]
                    ),
                    "duration": utils.parse_duration(track["duration_ms"] / 1000),
                }
                for index, track in enumerate(tracks, start=1)
            ],
        }

    def liked_tracks(self, data, audio_features):
        return {
            "track_ids": ",".join([item["track"]["id"] for item in data]),
            "tracks": [
                {
                    "id": item["track"]["id"],
                    "index": index,
                    "image": self.get_image(item["track"]["album"]),
                    "preview": item["track"]["preview_url"] or "",
                    "name": item["track"]["name"],
                    "artists": [
                        {"name": artist["name"], "id": artist["id"]}
                        for artist in item["track"]["artists"]
                    ],
                    "duration": utils.parse_duration(
                        item["track"]["duration_ms"] / 1000
                    ),
                    "album": item["track"]["album"]["name"],
                    "json": json.dumps(
                        dict(item["track"], rank=index, audio_features=features)
                    ),
                }
                for index, (item, features) in enumerate(
                    zip(data, audio_features), start=1
                )
            ],
        }

    def recent_tracks(self, data, audio_features):
        return {
            "track_ids": ",".join([item["track"]["id"] for item in data]),
            "tracks": [
                {
                    "id": item["track"]["id"],
                    "index": index,
                    "image": self.get_image(item["track"]["album"]),
                    "preview": item["track"]["preview_url"] or "",
                    "name": item["track"]["name"],
                    "artists": [
                        {"name": artist["name"], "id": artist["id"]}
                        for artist in item["track"]["artists"]
                    ],
                    "duration": utils.parse_duration(
                        item["track"]["duration_ms"] / 1000
                    ),
                    "album": item["track"]["album"]["name"],
                    "json": json.dumps(
                        dict(item["track"], rank=index, audio_features=features)
                    ),
                }
                for index, (item, features) in enumerate(
                    zip(data, audio_features), start=1
                )
            ],
        }

    def top_artists(self, data):
        return [
            {
                "index": index,
                "image": self.get_image(artist),
                "name": artist["name"],
                "json": json.dumps(dict(artist, rank=index)),
            }
            for index, artist in enumerate(data, start=1)
        ]

    def top_genres(self, data):
        return [
            {
                "index": index,
                "name": genre.capitalize(),
                "percent": f"{count/sum([x[1] for x in data.most_common() if x[1] > 2]):.1%}",
            }
            for index, (genre, count) in enumerate(data.most_common(), start=1)
            if count > 2
        ]

    def playlist(self, data):
        return [
            {
                "index": index,
                "name": item["track"]["name"],
                "image": self.get_image(item["track"]["album"]),
                "preview": item["track"]["preview_url"],
                "artist": ", ".join(
                    [artist["name"] for artist in item["track"]["artists"]]
                ),
                "duration": utils.parse_duration(item["track"]["duration_ms"] / 1000),
            }
            for index, item in enumerate(data["tracks"]["items"], start=1)
        ]

    def playlists(self, data):
        print(data[0]["owner"])
        return [
            {
                "index": index,
                "image": self.get_image(playlist),
                "name": playlist["name"],
                "owner": playlist["owner"],
                "type": "Collaborative"
                if playlist["collaborative"]
                else "Public"
                if playlist["public"]
                else "Private",
                "tracks": playlist["tracks"]["total"],
                "json": json.dumps(dict(playlist, rank=index)),
            }
            for index, playlist in enumerate(data, start=1)
        ]

    def albums(self, data):
        return [
            {
                "index": index,
                "image": self.get_image(album["album"]),
                "name": album["album"]["name"],
                "id": album["album"]["id"],
                "artists": [
                    {"name": artist["name"], "id": artist["id"]}
                    for artist in album["album"]["artists"]
                ],
                "release": self.release_date(album["album"]["release_date"]),
                "tracks": album["album"]["total_tracks"],
                "json": json.dumps(dict(album, rank=index)),
            }
            for index, album in enumerate(data, start=1)
        ]


formatting = Formatting()
