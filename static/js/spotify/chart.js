$(function () {
    console.log("ran")

    var ctx = $("#chartcanvas");

    var labels = ctx.data("labels")
    console.log(labels)
    var decades = ctx.data("decades")
    var colors = ctx.data("colors")

    var data = {
        labels: labels,
        datasets: [
            {
                data: decades,
                backgroundColor: colors,
            }
        ]
    };

    var options = {
        responsive: true,
        tooltips: {
            callbacks: {
                label: function (tooltipItem, data) {
                    console.log(data)
                    console.log(tooltipItem)
                    return data['labels'][tooltipItem['index']] + ': ' + data['datasets'][0]['data'][tooltipItem['index']] * 2 + '%';
                }
            }
        },
        legend: {
            display: true,
            position: "right",
            align: "center",
            labels: {
                fontColor: "#333",
                fontSize: 16
            }
        }
    };

    var chart = new Chart(ctx, {
        type: "doughnut",
        data: data,
        options: options
    });

});