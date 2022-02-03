window.onSpotifyPlayerAPIReady = () => {
    const player = new Spotify.Player({
        name: "Web Playback SDK Template",
        getOAuthToken: (cb) => {
            $.getJSON("/spotify/_token", function (data) {
                window.token = data.token
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


function getToken() {
    return new Promise(function (resolve, reject) {
        $.ajax({
            url: '/spotify/_token',
            success: function (data) {
                resolve(data) // Resolve promise and go to then()
            },
            error: function (err) {
                reject(err) // Reject the promise and go to catch()
            }
        });
    });
}

function play(uris) {// comma delimited string of uris
    getToken().then(function (data) {
        // Run this when your request was successful
        uris = uris.split(",")
        $.ajax({
            url: "https://api.spotify.com/v1/me/player/play?device_id=" + device_id,
            type: "PUT",
            data: JSON.stringify({ uris: uris }),
            beforeSend: function (xhr) {
                xhr.setRequestHeader("Authorization", "Bearer " + data.token);
            }
        });
    })
}

function pause() {
    getToken().then(function (data) {
        // Run this when your request was successful
        uris = uris.split(",")
        $.ajax({
            url: "https://api.spotify.com/v1/me/player/pause?device_id=" + device_id,
            type: "PUT",
            beforeSend: function (xhr) {
                xhr.setRequestHeader("Authorization", "Bearer " + data.token);
            }
        });
    })
}

$(function () {
    $(document).on("click", ".play", function () {
        $(this).text("Pause");
        $(this).addClass("pause");
        $(this).removeClass("play");
    });
});
$(function () {
    $(document).on("click", ".pause", function () {
        $(this).text("Play");
        $(this).addClass("play");
        $(this).removeClass("pause");
    });
});
