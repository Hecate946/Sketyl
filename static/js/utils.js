function createPlaylist(name, description, track_ids) {
    $.ajax({
        type: "POST",
        url: "/spotify/_create_playlist",
        data: JSON.stringify({
            name: name,
            description: description,
            track_ids: track_ids,
        }),
        success: function (data) {
            console.log(data);
            alert(data.response);
        },
        contentType: "application/json",
    });
}

function getGenreRecommendations(genreName) {
    $.ajax({
        type: "GET",
        url: "/spotify/_genre_recommendations?genre=" + genreName,
        success: function (data) {
            console.log(data);
            alert(data.response);
        },
        contentType: "application/json",
    });
}


$(".table-sort").on("change", function () {
    var selection = $(this).val();
    var tableID = "#" + $(this).data("table-id")
    var rows = $(tableID).children("tbody").children("tr");
    rows.sort(function (a, b) {
        var trackA = $(a).data("track");
        var trackB = $(b).data("track");

        if (selection == "artist") {
            var valueA = trackA["artists"][0]["name"].toLowerCase();
            var valueB = trackB["artists"][0]["name"].toLowerCase();
        }

        if (selection == "album") {
            var valueA = trackA["album"]["name"].toLowerCase();
            var valueB = trackB["album"]["name"].toLowerCase();
        }

        if (selection == "order") {
            var valueA = trackA["rank"];
            var valueB = trackB["rank"];
        }

        if (selection == "name") {
            var valueA = trackA["name"].toLowerCase();
            var valueB = trackB["name"].toLowerCase();
        }

        if (selection == "duration") {
            var valueA = trackA["duration_ms"];
            var valueB = trackB["duration_ms"];
        }

        if (selection == "popularity") {
            var valueA = trackA["popularity"];
            var valueB = trackB["popularity"];
        }

        if (selection == "tempo") {
            var valueA = trackA["audio_features"]["tempo"];
            var valueB = trackB.audio_features.tempo;
        }

        if (selection == "danceability") {
            var valueA = trackA.audio_features.danceability;
            var valueB = trackB.audio_features.danceability;
        }

        if (selection == "valence") {
            var valueA = trackA.audio_features.valence;
            var valueB = trackB.audio_features.valence;
        }

        if (selection == "energy") {
            var valueA = trackA.audio_features.energy;
            var valueB = trackB.audio_features.energy;
        }

        if (valueA > valueB) {
            return 1;
        } else if (valueA < valueB) {
            return -1;
        } else {
            return 0;
        }
    });

    $.each(rows, function (index, row) {
        $(tableID).children("tbody").append(row);
    });
});