$(".sorter").on("change", function () {
    var selection = $(this).val();
    var rows = $("table tbody tr").get();
    rows.sort(function (a, b) {
        var playlistA = $(a).data("playlist");
        var playlistB = $(b).data("playlist");

        if (selection == "owner") {
            var valueA = playlistA["owner"]["name"].toLowerCase();
            var valueB = playlistB["owner"]["name"].toLowerCase();
        }

        if (selection == "order") {
            var valueA = playlistA["rank"];
            var valueB = playlistB["rank"];
        }

        if (selection == "name") {
            var valueA = playlistA["name"].toLowerCase();
            var valueB = playlistB["name"].toLowerCase();
        }


        if (selection == "tracks") {
            var valueA = playlistA["tracks"]["total"];
            var valueB = playlistB["tracks"]["total"];
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
        $("table").children("tbody").append(row);
    });
});
