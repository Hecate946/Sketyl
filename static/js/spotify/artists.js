$(".sorter").on("change", function () {
    var selection = $(this).val();
    var items = $(".artist").get();
    items.sort(function (a, b) {
        var artistA = $(a).data("artist");
        var artistB = $(b).data("artist");


        if (selection == "order") {
            var valueA = artistA["rank"];
            var valueB = artistB["rank"];
        }

        if (selection == "name") {
            var valueA = artistA["name"].toLowerCase();
            var valueB = artistB["name"].toLowerCase();
        }

        if (selection == "popularity") {
            var valueA = artistA["popularity"];
            var valueB = artistB["popularity"];
        }

        if (selection == "followers") {
            var valueA = artistA["followers"]["total"];
            var valueB = artistB["followers"]["total"];
        }



        if (valueA > valueB) {
            return 1;
        } else if (valueA < valueB) {
            return -1;
        } else {
            return 0;
        }
    });

    $.each(items, function (index, artist) {
        $(".parent").append(artist);
    });
});