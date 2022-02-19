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

// $(function(){
//     // this will get the full URL at the address bar
//     // passes on every "a" tag 
//     $(".sub-nav .nav-link").each(function() {
//         // checks if its the same on the address bar
//         var base_url = window.location.href.split("?")[0]
//         if(base_url == this.href) { 
//             $(this).addClass("disabled");
//         }
//     });
// });
