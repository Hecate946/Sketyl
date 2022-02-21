// Javascript for ./templates/track.html


const feature_dict = {
    "acousticness": "red",
    "danceability": "orange",
    "energy": "yellow",
    "instrumentalness": "green",
    "liveness": "blue",
    "speechiness": "indigo",
    "valence": "violet",
}


var player = document.getElementById('player');
player.addEventListener("timeupdate", function () {
    var currentTime = player.currentTime;
    var duration = player.duration;
    $('.hp_range').stop(true, true).animate({ 'width': (currentTime + .00025) / duration * 100 + '%' }, 250, 'linear');
});



$(function () {
    $(".bar").each(function () {
        var elem = $(this).children();
        var elem_name = elem.attr("class");
        var progress = elem.data("value") * 100 + "%";
        $(elem).css(
            {
                "backgroundColor": feature_dict[elem_name],
                "borderRadius": "20px",
                "height": "100%",
                'width': progress,
            }
        );
    });
});