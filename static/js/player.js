const API_URL = "https://api.spotify.com/v1/";

function put(url, json) {
    $.ajax({
        url: url,
        type: "PUT",
        data: json,
        beforeSend: function(xhr){xhr.setRequestHeader('Authorization', 'Bearer ' + "{{token}}" );},
        success: function(data) { 
          console.log(data)
        }
    });    
}
function play(tracks) {
    var url = API_URL + "me/player/play"
    var query = $.params({
        device_id: window.device_id
    })
    var json = JSON.stringify({"uris": JSON.parse(tracks)})
    make_req(url + query, json)

}
