$(function(){
    // this will get the full URL at the address bar
    // passes on every "a" tag 
    $(".nav-link").each(function() {
        // checks if its the same on the address bar
        if(window.location.href == this.href) { 
            $(this).addClass("active");
        }
    });
});

$(function(){
    // this will get the full URL at the address bar
    // passes on every "a" tag 
    $(".sub-nav .nav-link").each(function() {
        // checks if its the same on the address bar
        if(window.location.href == this.href) { 
            $(this).addClass("disabled");
        }
    });
});
