const copyToClipboard = (elementId) => {
    const text = document.getElementById(elementId).innerHTML;
    navigator.clipboard
        .writeText(text)
        .then(() => {
            console.log(`"${text}" was copied to clipboard.`);
        })
        .catch((err) => {
            console.error(`Error copying text to clipboard: ${err}`);
        });
};

$("#copy-button").click(function () {
    copyToClipboard("profile-link");
    $(this).text("Link Copied").addClass("disabled");
});
