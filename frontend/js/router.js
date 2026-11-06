
"use strict";

(function () {
    const privatePages = new Set([
        "dashboard.html",
        "projects.html",
        "kanban.html",
        "profile.html"
    ]);

    const currentPage =
        location.pathname.split("/").pop() || "index.html";

    if (!privatePages.has(currentPage)) return;

    const guardMessage = document.getElementById("auth-guard-message");
    const retryButton = document.getElementById("auth-guard-retry");
    const appError = document.getElementById("app-error-message");

    const Auth = {
        status: "checking",
        user: null
    };

    window.PulseAuth = Auth;
    window.PulseCurrentUser = null;

    function setStatus(status, user = null) {
        Auth.status = status;
        Auth.user = user;
        window.PulseCurrentUser = user;

        window.dispatchEvent(
            new CustomEvent("pulse:auth-changed", {
                detail: { status, user }
            })
        );
    }

    function showGuard(text) {
        if (guardMessage) {
            guardMessage.textContent = text;
        }
    }

    function setAuthenticated(user) {
        if (!user || typeof user !== "object" || !user.email) {
            throw new Error("Dữ liệu người dùng không hợp lệ.");
        }

        document.querySelectorAll("[data-user-name]").forEach((element) => {
            element.textContent =
                user.display_name || user.name || user.email;
        });

        document.querySelectorAll("[data-user-email]").forEach((element) => {
            element.textContent = user.email;
        });

        setStatus("authenticated", user);

        document.body.classList.remove("auth-checking");
        showGuard("");

        if (retryButton) {
            retryButton.hidden = true;
        }
    }

    function redirectToLogin() {
        setStatus("unauthenticated");
        document.body.classList.add("auth-checking");
        location.replace("login.html");
    }

    async function checkAuth() {
        setStatus("checking");

        document.body.classList.add("auth-checking");
        showGuard("Đang kiểm tra phiên đăng nhập...");

        if (retryButton) {
            retryButton.hidden = true;
        }

        try {
            const response = await window.PulseAPI.get(
                "/auth/me",
                { skipAuthRedirect: true }
            );

            setAuthenticated(response?.data);
        } catch (error) {
            if (error.status === 401) {
                redirectToLogin();
                return;
            }

            setStatus("error");

            const text =
                error.status === 403
                    ? "Bạn không có quyền truy cập trang này."
                    : error.code === "NETWORK_ERROR"
                    ? "Không thể kết nối Backend. Vui lòng kiểm tra máy chủ."
                    : error.code === "REQUEST_ABORTED"
                    ? "Kết nối quá thời gian chờ."
                    : error.message || "Không thể kiểm tra phiên đăng nhập.";

            showGuard(text);

            if (retryButton) {
                retryButton.hidden = false;
            }
        }
    }

    if (retryButton) {
        retryButton.addEventListener("click", checkAuth);
    }

    window.addEventListener("pulse:unauthorized", () => {
        redirectToLogin();
    });

    window.addEventListener("pulse:forbidden", (event) => {
        if (appError) {
            appError.hidden = false;
            appError.textContent =
                event.detail?.message ||
                "Bạn không có quyền thực hiện thao tác.";
        }
    });

    window.addEventListener("pulse:user-updated", (event) => {
        if (
            Auth.status === "authenticated" &&
            event.detail?.user
        ) {
            setAuthenticated(event.detail.user);
        }
    });

    document.querySelectorAll("[data-logout]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (Auth.status !== "authenticated" || button.disabled) {
                return;
            }

            button.disabled = true;
            button.textContent = "Đang đăng xuất...";

            try {
                await window.PulseAPI.post(
                    "/auth/logout",
                    undefined,
                    { skipAuthRedirect: true }
                );

                redirectToLogin();
            } catch (error) {
                if (error.status === 401) {
                    redirectToLogin();
                    return;
                }

                if (appError) {
                    appError.hidden = false;
                    appError.textContent =
                        error.code === "NETWORK_ERROR"
                            ? "Không thể kết nối Backend để đăng xuất."
                            : error.message || "Đăng xuất thất bại.";
                }

                button.disabled = false;
                button.textContent = "Đăng xuất";
            }
        });
    });

    checkAuth();
})();
