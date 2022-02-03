// Javascript for ./templates/spotify/genres.html

$(".view-link").on("click", function () {
    console.log("click")
    var genreName = $(this).text()
    recommendations = getGenreRecommendations(genreName)
    console.log(recommendations)

})