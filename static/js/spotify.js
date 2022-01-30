$(function(){
    // this will get the full URL at the address bar
    // passes on every "a" tag 
    $(".dropdown-item").each(function() {
            // checks if its the same on the address bar
        if (window.location.href == this.href || window.location.href == this.href + "?time_range=short_term") { 
            $(this).remove();
        }
    });
});

// $(function(){
//     $(".clickable-row").click(function() {
//         console.log("cliick")
//         window.location = $(this).data("href");
//     });
// });

$(function(){
    $(document).on("click", ".play-pause", function() {
        window.audio = $(this).children("audio")
        if (window.audio[0].paused) {
            play()
        }
        else {
            pause()
        }
    });
});

$("audio").on({
    play:function(){ // the audio is playing!
        $(window.audio).siblings("i").removeClass("fa-play").addClass("fa-pause")
    },
    pause:function(){ // the audio is paused!
        $(window.audio).siblings("i").removeClass("fa-pause").addClass("fa-play")
    },
})

function play() {
    $("audio").trigger("pause") // pause other audios
    $("audio").siblings("i").removeClass("fa-pause").addClass("fa-play")

    window.audio.trigger("play");
}
function pause() {
    window.audio.trigger("pause");
}

$(".table-sort").on("change", function() {
    var selection = $(this).val()
    var rows = $("table tbody tr").get()
    rows.sort(function(a, b) {
        var trackA = $(a).data("track")
        var trackB = $(b).data("track")

        console.log(typeof trackB)
        console.log(trackB)

        if (selection == "artist") {
            var valueA = trackA["artists"][0]["name"].toLowerCase()
            var valueB = trackB["artists"][0]["name"].toLowerCase()
        }

        if (selection == "album") {
            var valueA = trackA["album"]["name"].toLowerCase()
            var valueB = trackB["album"]["name"].toLowerCase()
        }

        if (selection == "affinity") {
            var valueA = trackA["rank"]
            var valueB = trackB["rank"]
        }

        if (selection == "name") {
            var valueA = trackA["name"].toLowerCase()
            var valueB = trackB["name"].toLowerCase()
        }

        if (selection == "duration") {
            var valueA = trackA["duration_ms"]
            var valueB = trackB["duration_ms"]
        }

        if (selection == "popularity") {
            var valueA = trackA["popularity"]
            var valueB = trackB["popularity"]
        }

        if (selection == "tempo") {
            console.log(trackA.audio_features)
            var valueA = trackA["audio_features"]["tempo"]
            var valueB = trackB.audio_features.tempo
        }

        if (selection == "danceability") {
            console.log(trackA.audio_features)
            var valueA = trackA.audio_features.danceability
            var valueB = trackB.audio_features.danceability
        }

        if (selection == "valence") {
            console.log(trackA.audio_features)
            var valueA = trackA.audio_features.valence
            var valueB = trackB.audio_features.valence
        }

        if (selection == "energy") {
            console.log(trackA.audio_features)
            var valueA = trackA.audio_features.energy
            var valueB = trackB.audio_features.energy
        }

        if (valueA > valueB) {return 1;}
        else if (valueA < valueB) {return -1;}
        else {return 0;}
    })

    $.each(rows, function(index, row){
        $("table").children("tbody").append(row)
    })
    
})

$(function(){
    // this will get the full URL at the address bar
 
    $(".time-select-buttons").children().each(function() {
            // checks if its the same on the address bar
        if (window.location.href == this.href || window.location.href + "?time_range=short_term" == this.href) { 
            $(this).addClass("link-light").removeClass("link-secondary");
        }
    });
});