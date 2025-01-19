// Example: Alert when a match ID is clicked
document.addEventListener("DOMContentLoaded", function () {
    const matchElements = document.querySelectorAll(".match-id");
    matchElements.forEach((element) => {
        element.addEventListener("click", () => {
            alert(`Match ID: ${element.textContent}`);
        });
    });
});
