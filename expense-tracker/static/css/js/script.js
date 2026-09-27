document.addEventListener("DOMContentLoaded", function () {

    // Automatically hide flash messages
    const flashMessages = document.querySelectorAll(".flash");

    flashMessages.forEach(function (message) {

        setTimeout(function () {

            message.style.transition = "opacity 0.5s ease";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 500);

        }, 4000);

    });


    // Set today's date automatically
    const dateInput = document.getElementById("expense_date");

    if (dateInput && !dateInput.value) {

        const today = new Date();

        const year = today.getFullYear();

        const month = String(
            today.getMonth() + 1
        ).padStart(2, "0");

        const day = String(
            today.getDate()
        ).padStart(2, "0");

        dateInput.value =
            `${year}-${month}-${day}`;
    }


    // Confirm delete actions
    const deleteForms = document.querySelectorAll(
        "form[action*='/expense/delete/']"
    );

    deleteForms.forEach(function (form) {

        form.addEventListener("submit", function (event) {

            const confirmed = confirm(
                "Are you sure you want to delete this expense?"
            );

            if (!confirmed) {
                event.preventDefault();
            }

        });

    });


    // Prevent negative values in number inputs
    const numberInputs = document.querySelectorAll(
        "input[type='number']"
    );

    numberInputs.forEach(function (input) {

        input.addEventListener("input", function () {

            if (parseFloat(input.value) < 0) {
                input.value = "";
            }

        });

    });

});