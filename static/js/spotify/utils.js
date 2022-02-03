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
