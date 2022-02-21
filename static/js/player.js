$(function () {
    $(document).on("click", ".play-pause", function () {
        var audio = $(this).children("audio");
        if (audio[0].paused) {
            if (window.audio !== undefined) {
                // audio already existed, pause it.
                pause();
            }
            window.audio = audio;
            play();
        } else {
            window.audio = audio;
            pause();
        }
    });
});


$("audio").on({
    play: function () {
        // the audio is playing!
        $(window.audio)
            .siblings("i")
            .removeClass("fa-play")
            .addClass("fa-pause");
        $(window.audio).parents("span").siblings("h4").addClass("invisible")
        console.log($(window.audio).parents("span").siblings("h4"))
    },
    pause: function () {
        // the audio is paused!
        $(window.audio)
            .siblings("i")
            .removeClass("fa-pause")
            .addClass("fa-play");
        $(window.audio).parents("span").siblings("h4").removeClass("invisible")
    },
});

function play() {
    $(window.audio).siblings("i").removeClass("fa-play").addClass("fa-pause");
    if ($(window.audio[0]).attr("src")) {
        window.audio.trigger("play");
    } else {
        alert("Audio preview unavailable for this track.");
        $(window.audio)
            .siblings("i")
            .removeClass("fa-pause")
            .addClass("fa-play");
    }
}
function pause() {
    $(window.audio).siblings("i").removeClass("fa-pause").addClass("fa-play");
    window.audio.trigger("pause");
}