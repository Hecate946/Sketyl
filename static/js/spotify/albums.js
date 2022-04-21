$(".sorter").on("change", function () {
    var selection = $(this).val();
    var rows = $("table tbody tr").get();
    rows.sort(function (a, b) {
        var albumA = $(a).data("album");
        var albumB = $(b).data("album");
        console.log("test");
        console.log("selection:" + selection);


        if (selection == "artist") {
            var valueA = albumA["album"]["artists"][0]["name"].toLowerCase();
            var valueB = albumB["album"]["artists"][0]["name"].toLowerCase();
        }

        else if (selection == "order") {
            var valueA = albumA["rank"];
            var valueB = albumB["rank"];
        }

        else if (selection == "name") {
            var valueA = albumA["album"]["name"].toLowerCase();
            var valueB = albumB["album"]["name"].toLowerCase();
        }

        else if (selection == "date") { // how to do?
            var valueA = new Date(albumA["album"]["release-date"]);
            var valueB = new Date(albumB["album"]["release-date"]);
            console.log(valueA)
        }

        else if (selection == "tracks") {
            var valueA = albumA["album"]["total_tracks"];
            var valueB = albumB["album"]["total_tracks"];
        }

        if (valueA > valueB) {
            return 1;
        } else if (valueA < valueB) {
            return -1;
        } else {
            console.log("test")
            return 0;
        }
    });

    $.each(rows, function (index, row) {
        $("table").children("tbody").append(row);
    });
});
