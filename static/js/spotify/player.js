window.onSpotifyPlayerAPIReady = () => {
    const player = new Spotify.Player({
        name: "Web Playback SDK Template",
        getOAuthToken: (cb) => {
            $.getJSON("/_spotify_token", function (data) {
                cb(data.token);
            });
        },
    });

    // Error handling
    player.on("initialization_error", (e) => console.error(e));
    player.on("authentication_error", (e) => console.error(e));
    player.on("account_error", (e) => console.error(e));
    player.on("playback_error", (e) => console.error(e));

    // Playback status updates
    player.on("player_state_changed", (state) => {
        console.log(state);
        $("#current-track").attr(
            "src",
            state.track_window.current_track.album.images[0].url
        );
        $("#current-track-name").text(state.track_window.current_track.name);
    });

    // Ready
    player.on("ready", (data) => {
        console.log("Ready with Device ID", data.device_id);

        // Set global devide ID
        window.device_id = data.device_id;
    });

    // Connect to the player!
    player.connect();
};

function play(uris) {
    $.ajax({
        url:
            "https://api.spotify.com/v1/me/player/play?device_id=" +
            window.device_id,
        type: "PUT",
        data: JSON.stringify({ uris: uris }),
        beforeSend: function (xhr) {
            $.getJSON("/_spotify_token", function (data) {
                xhr.setRequestHeader("Authorization", "Bearer " + data.token);
            });
        },
        success: function (data) {
            console.log(data);
        },
    });
}
function pause() {
    $.ajax({
        url:
            "https://api.spotify.com/v1/me/player/pause?device_id=" +
            window.device_id,
        type: "PUT",
        beforeSend: function (xhr) {
            $.getJSON("/_spotify_token", function (data) {
                xhr.setRequestHeader("Authorization", "Bearer " + data.token);
            });
        },
        success: function (data) {
            console.log(data);
        },
    });
}

$(function () {
    $(document).on("click", ".play", function () {
        console.log("play clicked");
        $(this).text("Pause");
        $(this).addClass("pause");
        $(this).removeClass("play");
    });
});
$(function () {
    $(document).on("click", ".pause", function () {
        console.log("pause clicked");
        $(this).text("Play");
        $(this).addClass("play");
        $(this).removeClass("pause");
    });
});
