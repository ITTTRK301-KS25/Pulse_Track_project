
(function () {
    "use strict";

    const privatePages = new Set([
        "dashboard.html",
        "projects.html",
        "kanban.html"
    ]);

    const currentPage =
        window.location.pathname.split("/").pop() || "index.html";

    const notice = document.getElementById("auth-guard-message");
    const retryButton = document.getElementById("auth-guard-retry");
    const errorMessage = document.getElementById("app-error-message");

    function show(text) {
        if (notice) {
            notice.textContent = text;
        }
    }

    function clearErrors() {
        show("");

        if (retryButton) {
            retryButton.hidden = true;
        }

        if (errorMessage) {
            errorMessage.hidden = true;
            errorMessage.textContent = "";
        }
    }

    async function protect() {
        if (!privatePages.has(currentPage)) {
            return;
        }

        document.body.classList.add("auth-checking");
        show("Đang kiểm tra phiên đăng nhập...");

        if (retryButton) {
            retryButton.hidden = true;
        }

        try {
            const user = await window.PulseAPI.get("/auth/me", {
                skipAuthRedirect: true
            });

            if (!user) {
                throw new Error(
                    "Backend không trả về thông tin người dùng"
                );
            }

            window.PulseCurrentUser = user;

            clearErrors();

            document.body.classList.remove("auth-checking");

        } catch (error) {
            if (error.status === 401) {
                window.location.replace("login.html");
                return;
            }

            show(
                error.message ||
                "Không thể kiểm tra phiên đăng nhập."
            );

            if (retryButton) {
                retryButton.hidden = false;
            }
        }
    }

    if (retryButton) {
        retryButton.addEventListener("click", () => {
            protect();
        });
    }

    window.addEventListener("pulse:forbidden", (event) => {
        if (errorMessage) {
            errorMessage.hidden = false;
            errorMessage.textContent =
                event.detail?.message ||
                "Bạn không có quyền truy cập.";
        }
    });

    protect();
})();
