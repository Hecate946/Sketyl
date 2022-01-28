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

