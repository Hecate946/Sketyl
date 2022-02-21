const pluralize = (text, len) => {
    if (len === 1) {
        return text;
    } else {
        return text + "s";
    }
};
$(function () {
    var ctx = $("#chartcanvas");

    var labels = ctx.data("labels")
    var decades = ctx.data("decades")
    var colors = ctx.data("colors")

    console.log(decades.length)

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
                    return data['labels'][tooltipItem['index']] + ': ' + decades[tooltipItem['index']] + pluralize(" Track", decades[tooltipItem['index']]);
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