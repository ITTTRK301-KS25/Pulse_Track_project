
document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
        const input = document.getElementById(btn.dataset.togglePassword);

        if (!input) {
            return;
        }

        if (input.type === "password") {
            input.type = "text";
            btn.textContent = "Ẩn";
        } else {
            input.type = "password";
            btn.textContent = "Hiện";
        }
    });
});

document.querySelectorAll("[data-demo-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        event.preventDefault();

        const msg = form.querySelector(".message");

        if (msg) {
            msg.textContent =
                "Giao diện đã sẵn sàng. Chức năng xác thực sẽ được kết nối với Backend ở F02.";
        }
    });
});
