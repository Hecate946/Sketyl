$(function () {
    // this will get the full URL at the address bar
    // passes on every "a" tag 
    $(".nav-link").each(function () {
        // checks if its the same on the address bar
        if (window.location.href.split("?")[0] == this.href) {
            $(this).addClass("active");
        }
    });
});

$(document).ready(function () {
    $('[data-bs-toggle="popover"]').popover();
});