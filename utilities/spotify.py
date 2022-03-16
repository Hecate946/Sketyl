from urllib.parse import urlencode
from collections import Counter, defaultdict
import base64
import time
import json

from datetime import datetime, date

from quart import request
from utilities import utils, cache
from config import SPOTIFY


class CONSTANTS:
    WHITE_ICON = "https://cdn.discordapp.com/attachments/872338764276576266/927649624888602624/spotify_white.png"
    GREEN_ICON = "https://cdn.discordapp.com/attachments/872338764276576266/932399347289706556/spotify_green.png"
    API_URL = "https://api.spotify.com/v1/"
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SCOPES = [  # Ask for bare minimum needed for functionality
        # Users
        "user-read-private",
        # Library
        "user-library-read",
        # Listening history
        "user-top-read",
        "user-read-recently-played",
        # Playlists
        "playlist-read-collaborative",
        "playlist-read-private",
        "playlist-modify-public",
        # Currently playing track
        "user-read-currently-playing",
    ]
    TIME_RANGE_MAP = {
        "short_term": "four weeks.",
        "medium_term": "six months.",
        "long_term": "few years.",
    }


class ClientCredentials:
    def __init__(self, app):
        self.app = app
        self.id = SPOTIFY.client_id
        self.secret = SPOTIFY.client_secret

        self.token = None
        app.loop.create_task(self.get_token())  # validate token

    def _make_token_auth(self, client_id, client_secret):
        auth_header = base64.b64encode(
            (client_id + ":" + client_secret).encode("ascii")
        )
        return {"Authorization": "Basic %s" % auth_header.decode("ascii")}

    async def get_track(self, track_id):
        """Get a track's info from its id"""
        return await self.make_spotify_req(
            CONSTANTS.API_URL + "tracks/{0}".format(track_id)
        )

    async def get_track_features(self, track_id):
        return await self.make_spotify_req(
            CONSTANTS.API_URL + "audio-features/{0}".format(track_id)
        )

    async def get_tracks_features(self, track_ids):
        features = []
        while len(track_ids) > 0:
            params = {"ids": ",".join(track_ids[:100])}
            query = urlencode(params)
            batch = await self.make_spotify_req(
                CONSTANTS.API_URL + "audio-features?" + query
            )
            features.extend(batch["audio_features"])
            del track_ids[:100]

        return features

    @cache.cache(strategy=cache.Strategy.raw)
    async def get_full_track(self, track_id):
        data = await self.get_track(track_id)
        data["audio_features"] = await self.get_track_features(track_id)

        album_tracks = data["album"]["tracks"] = await self.get_album_tracks(
            data["album"]["id"]
        )

        artist_tracks = data["artists"][0][
            "top_tracks"
        ] = await self.get_artist_top_tracks(data["artists"][0]["id"])

        tracks_without_features = album_tracks + artist_tracks

        features = await self.get_tracks_features(
            [t["id"] for t in tracks_without_features]
        )
        for track, feat in zip(tracks_without_features, features):
            track["audio_features"] = feat

        return Track(data)

    async def get_album_tracks(self, album_id):
        """Get an album's info from its URI"""
        r = await self.make_spotify_req(
            CONSTANTS.API_URL + "albums/{0}/tracks".format(album_id)
        )
        return r["items"]

    async def get_artist_top_tracks(self, artist_id):
        """Get an artist's info from its URI"""
        r = await self.make_spotify_req(
            CONSTANTS.API_URL + "artists/{0}/top-tracks?market=US".format(artist_id)
        )
        return r["tracks"]

    async def get_playlist(self, user, uri):
        """Get a playlist's info from its URI"""
        return await self.make_spotify_req(
            CONSTANTS.API_URL + "users/{0}/playlists/{1}{2}".format(user, uri)
        )

    async def get_playlist_tracks(self, uri):
        """Get a list of a playlist's tracks"""
        return await self.make_spotify_req(
            CONSTANTS.API_URL + "playlists/{0}/tracks".format(uri)
        )

    async def make_spotify_req(self, url):
        """Proxy method for making a Spotify req using the correct Auth headers"""
        token = await self.get_token()
        return await self.make_get(
            url, headers={"Authorization": "Bearer {0}".format(token)}
        )

    async def make_get(self, url, headers=None):
        """Makes a GET request and returns the results"""
        return await self.app.http.get(url, headers=headers, res_method="json")

    async def make_post(self, url, payload, headers=None):
        """Makes a POST request and returns the results"""
        return await self.app.http.post(
            url, data=payload, headers=headers, res_method="json"
        )

    async def get_token(self):
        """Gets the token or creates a new one if expired"""
        if self.token and not await self.check_token(self.token):
            return self.token["access_token"]

        token = await self.request_token()
        if token:
            token["expires_at"] = int(time.time()) + token["expires_in"]
            self.token = token
            return self.token["access_token"]

    async def check_token(self, token):
        """Checks a token is valid"""
        now = int(time.time())
        return token["expires_at"] - now < 60

    async def request_token(self):
        """Obtains a token from Spotify and returns it"""
        payload = {"grant_type": "client_credentials"}
        headers = self._make_token_auth(self.id, self.secret)
        r = await self.make_post(CONSTANTS.TOKEN_URL, payload=payload, headers=headers)
        return r


class Oauth:
    def __init__(self, app):
        self.client_id = SPOTIFY.client_id
        self.client_secret = SPOTIFY.client_secret
        self.redirect_uri = SPOTIFY.redirect_uri
        self.scope = " ".join(CONSTANTS.SCOPES)

        self.client = app

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
            "show_dialog": True,  # If they agreed already, why show them the annoying auth page?
        }
        if state:
            params["state"] = state
        constructed = urlencode(params)
        return "%s?%s" % (CONSTANTS.AUTH_URL, constructed)

    def validate_token(self, token_info):
        """Checks a token is valid"""
        now = int(time.time())
        return token_info["expires_at"] - now > 60

    async def get_access_token(self, user_id, token_info):
        """Gets the token or creates a new one if expired"""
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

        token_info["expires_at"] = int(time.time()) + token_info["expires_in"]
        await self.client.db.insert_user(user_id, token_info)
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
        token_info["expires_at"] = int(time.time()) + token_info["expires_in"]
        return token_info


class BaseUtils:
    def __init__(self) -> None:
        pass

    def _get_image(self, obj, quality="best"):
        if quality == "fast":
            index = -1
        else:
            index = 0
        try:
            return obj["images"][index]["url"]
        except (IndexError, KeyError):
            return CONSTANTS.GREEN_ICON

    def _playlist_type(self, playlist_data):
        if playlist_data["collaborative"]:
            return "Collaborative"
        elif playlist_data["public"]:
            return "Public"
        return "Private"

    def _release_date(self, date_str):
        date_parts = date_str.split("-")
        date_parts = [int(dp) for dp in date_parts]
        if len(date_parts) == 1:
            return date_parts[0]

        date_obj = date(*date_parts)

        return date_obj.__format__("%B %d, %Y")


# Datatypes for Spotify Objects
class Album(BaseUtils):
    def __init__(self, data, *, index=None, tracks=None):
        super().__init__()
        self.id = data["id"]
        self.name = data["name"]
        self.total_tracks = data["total_tracks"]
        self.cover = self._get_image(data)
        self.uri = "spotify:album:" + self.id
        self.url = data["external_urls"]["spotify"]
        self.artists = [Artist(artist) for artist in data["artists"]]

        self.raw = data
        self.json = json.dumps(data)

        if data.get("tracks") or tracks:
            self.tracks = tracks or [
                Track(dict(track, album=data), album=self) for track in data["tracks"]
            ]

        self.index = index


class Artist(BaseUtils):
    def __init__(self, data, *, index=None, related_artists=[], albums=[]):
        super().__init__()
        self.id = data["id"]
        self.name = data["name"]
        self.cover = self._get_image(data)
        self.uri = "spotify:artist:" + self.id
        self.url = data["external_urls"]["spotify"]
        self.popularity = data.get("popularity", 0)
        self.followers = data.get("followers", {}).get("total", 0)
        self.genres = data.get("genres", [])

        self.raw = data
        self.json = json.dumps(data)

        self.index = index

        self.top_tracks = []
        if data.get("top_tracks"):
            self.top_tracks = [Track(t, quality="fast") for t in data.get("top_tracks")]
        self.related_artists = related_artists
        self.albums = albums


class Track(BaseUtils):
    def __init__(self, data, *, quality="best", album=None):
        super().__init__()
        self.id = data["id"]
        self.name = data["name"]
        self.cover = self._get_image(data["album"], quality=quality)
        self.release = self._release_date(data["album"]["release_date"])
        self.uri = "spotify:track:" + self.id
        self.url = data["external_urls"]["spotify"]
        self.popularity = data.get("popularity")
        self.duration = utils.parse_duration(data["duration_ms"] / 1000)
        self.raw_duration = data["duration_ms"]
        self.preview = data["preview_url"]

        self.album = album or Album(data["album"])  # parent album
        self.artists = [Artist(a) for a in data["artists"]]

        self.raw = data
        self.json = json.dumps(data)

        self.features = data.get("audio_features")
        self.index = data.get("index")


class Playlist(BaseUtils):
    def __init__(self, data, *, rank=None):
        super().__init__()
        self.id = data["id"]
        self.name = data["name"]
        self.description = data["description"]
        self.cover = self._get_image(data)
        self.uri = "spotify:playlist:" + self.id
        self.url = data["external_urls"]["spotify"]
        self.followers = data.get("followers", {}).get("total", 0)
        self.type = self._playlist_type(data)
        self.total_tracks = data["tracks"]["total"]
        self.owner = SpotifyUser(data["owner"])

        # print(data["tracks"])

        # self.tracks = [
        #     Track(track, index=rank)
        #     for rank, track in enumerate(data["tracks"], start=1)
        # ]

        self.raw = data
        self.json = json.dumps(dict(data, rank=rank or 0))

        self.index = rank


class SpotifyUser(BaseUtils):
    def __init__(self, data):
        super().__init__()
        self.id = data["id"]
        self.name = data["display_name"]
        self.cover = self._get_image(data)
        self.uri = "spotify:user:" + self.id
        self.url = data["external_urls"]["spotify"]
        self.followers = data.get("followers", {}).get("total", 0)


class User:  # Current user's spotify instance
    def __init__(self, user_id, token_info, app):
        self.id = user_id
        self.token_info = token_info
        self.client = app
        self.oauth = Oauth(app)

    @staticmethod
    async def _get_user_id(app, token_info):
        token = token_info.get("access_token")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        profile = await app.http.get(
            CONSTANTS.API_URL + "me", res_method="json", headers=headers
        )
        print(profile)
        return profile["id"]

    @classmethod
    async def from_id(cls, user_id, app):
        token_info = await app.db.fetch_user(user_id)

        if token_info:
            return cls(user_id, token_info, app)

    @classmethod
    async def from_token(cls, token_info, app, *, user_id=None):
        user_id = user_id or await cls._get_user_id(app, token_info)
        await app.db.insert_user(user_id, token_info)

        return cls(user_id, token_info, app)

    async def get_token(self):
        return await self.oauth.get_access_token(self.id, self.token_info)

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

    async def get_recommendations(self, limit=100, **kwargs):
        params = {"limit": limit}
        params.update(**kwargs)
        return await self.get(
            CONSTANTS.API_URL + "recommendations?" + urlencode(params)
        )

    async def _format_tracks(self, tracks):
        tracks_ids = [track["id"] for track in tracks]
        feats = await self.get_audio_features(tracks_ids)
        func = lambda x, y: Track(dict(x, audio_features=y), quality="fast")
        return list(map(func, tracks, feats))

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_audio_features(self, track_ids):
        features = []
        while len(track_ids) > 0:
            params = {"ids": ",".join(track_ids[:100])}
            query = urlencode(params)
            batch = await self.get(CONSTANTS.API_URL + "audio-features?" + query)
            features.extend(batch["audio_features"])
            del track_ids[:100]

        return features

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_liked_tracks(self, tracks: int = 99):
        """
        Get the current users liked tracks.
        Specify # of tracks.
        Returns list of tracks
        """

        liked_tracks = []
        offset = 0
        while tracks > 0:
            limit = tracks if tracks < 50 else 50
            query = urlencode({"limit": limit, "offset": offset * 50})
            batch = await self.get(CONSTANTS.API_URL + "me/tracks?" + query)
            if not batch["items"]:  # No more tracks
                break
            liked_tracks.extend(item["track"] for item in batch["items"])
            tracks -= limit
            offset += 1

        return await self._format_tracks(liked_tracks)

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_recent_tracks(self, tracks: int = 50):
        """
        Get the current users recent tracks.
        Specify # of tracks.
        Returns list of tracks
        Max items: 99
        """
        query = urlencode({"limit": tracks if tracks < 50 else 50})
        batch = await self.get(CONSTANTS.API_URL + "me/player/recently-played?" + query)
        return await self._format_tracks([item["track"] for item in batch["items"]])

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_top_tracks(self, tracks: int = 99, time_range="short_term"):
        """
        Get the current users top tracks.
        Specify # of tracks and time period.
        Returns list of tracks
        Max items: 99
        """
        top_tracks = []  # list of tracks
        tracks = tracks if tracks < 100 else 99  # Spotify limit.
        limit = tracks if tracks < 50 else 50
        query = urlencode({"limit": limit, "time_range": time_range, "offset": 0})
        batch = await self.get(CONSTANTS.API_URL + "me/top/tracks?" + query)
        top_tracks.extend(batch["items"])

        tracks -= limit

        if tracks > 0:
            query = urlencode({"limit": 50, "time_range": time_range, "offset": tracks})
            batch = await self.get(CONSTANTS.API_URL + "me/top/tracks?" + query)
            top_tracks.extend(batch["items"][1:])

        return await self._format_tracks(top_tracks)

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_top_artists(self, artists: int = 99, time_range="short_term"):
        """
        Get the current users top artists.
        Specify # of artists and time period.
        Returns list of artists
        Max items: 99
        """
        top_artists = []  # list of artists
        artists = artists if artists < 100 else 99  # Spotify limit.
        limit = artists if artists < 50 else 50
        query = urlencode({"limit": limit, "time_range": time_range, "offset": 0})
        batch = await self.get(CONSTANTS.API_URL + "me/top/artists?" + query)
        top_artists.extend(batch["items"])

        artists -= limit

        if artists > 0:
            query = urlencode(
                {"limit": 50, "time_range": time_range, "offset": artists}
            )
            batch = await self.get(CONSTANTS.API_URL + "me/top/artists?" + query)
            top_artists.extend(batch["items"][1:])

        return top_artists

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_decades(self, time_range="short_term"):
        data = await self.get_top_tracks(time_range=time_range)
        decade = lambda date: (int(date.split("-")[0]) // 10) * 10
        decades = defaultdict(list)
        for track in data:
            decades[decade(track.raw["album"]["release_date"])].append(track)

        return {str(decade) + "s": tracks for decade, tracks in sorted(decades.items())}

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_playlists(self, playlists: int = 100):
        """Get a user's owned and followed playlists"""
        _playlists = []
        offset = 0
        while playlists > 0:
            limit = playlists if playlists < 50 else 50
            query = urlencode({"limit": limit, "offset": offset * 50})
            batch = await self.get(CONSTANTS.API_URL + "me/playlists?" + query)
            if not batch["items"]:
                break
            _playlists.extend(batch["items"])
            playlists -= limit
            offset += 1

        return _playlists

    @cache.cache(strategy=cache.Strategy.timed)
    async def get_saved_albums(self, albums: int = 100):
        """Get a user's saved albums"""
        _albums = []
        offset = 0
        while albums > 0:
            limit = albums if albums < 50 else 50
            query = urlencode({"limit": limit, "offset": offset})
            batch = await self.get(CONSTANTS.API_URL + "me/albums?" + query)
            if not batch["items"]:
                break
            _albums.extend(item["album"] for item in batch["items"])
            albums -= limit
            offset += 1

        return _albums

    async def get_artist_top_tracks(self, artist_id):
        return await self.get(CONSTANTS.API_URL + f"artists/{artist_id}/top_tracks")

    async def get_top_genres(self, limit=99, time_range="short_term"):
        data = await self.get_top_artists(limit, time_range)
        genres = []
        for artist in data:
            genres.extend(artist["genres"])

        return Counter(genres)

    async def get_genre_seeds(self):
        r = await self.get(CONSTANTS.API_URL + "recommendations/available-genre-seeds")
        return r["genres"]

    async def get_valid_genres(self, limit=99, time_range="short_term"):
        genre_list_1 = await self.get_top_genres(limit, time_range)
        genre_list_2 = await self.get_genre_seeds()
        genres = [g for g in genre_list_1 if g in genre_list_2]
        return Counter(genres)

    async def get_album(self, album_id):
        return await self.get(CONSTANTS.API_URL + f"albums/{album_id}")

    async def get_albums(self, album_ids):
        albums = []
        while len(album_ids):

            query = urlencode({"ids": ",".join(album_ids[:20])})
            batch = await self.get(CONSTANTS.API_URL + f"albums?" + query)
            albums.extend(batch["albums"])
            del album_ids[:20]

        return albums

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

    async def now_playing(self):
        return await self.get(CONSTANTS.API_URL + f"me/player/currently-playing")

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
            desc=f"Top tracks in the past {CONSTANTS.TIME_RANGE_MAP[time_range]} (Generated by Sketyl.com)",
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
                    "duration": utils.parse_duration(track["duration_ms"] // 1000),
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
                    "duration": utils.parse_duration(track["duration_ms"] // 1000),
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
                        item["track"]["duration_ms"] // 1000
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
                        item["track"]["duration_ms"] // 1000
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
                "duration": utils.parse_duration(item["track"]["duration_ms"] // 1000),
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
