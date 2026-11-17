
"use strict";

(function () {
    const privatePages = new Set([
        "dashboard.html",
        "projects.html",
        "kanban.html",
        "profile.html",
        "ai-planner.html"
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

    // ===== PULSE TRACK PROFILE DROPDOWN =====

    function buildProfileMenu() {
        const nav = document.querySelector(".app-header nav");
        if (!nav || nav.querySelector(".pt-nav-profile")) return;

        const oldUserLink = nav.querySelector("[data-user-name]");
        const oldLogout = nav.querySelector("[data-logout]");

        if (!oldUserLink || !oldLogout) return;

        const profile = document.createElement("div");
        profile.className = "pt-nav-profile";


        profile.innerHTML = `
            <button
                type="button"
                class="pt-nav-profile-trigger"
                aria-label="Mở menu tài khoản"
                aria-expanded="false"
                aria-haspopup="true"
                title="Tài khoản của tôi"
            >
                <span class="pt-nav-avatar" data-profile-initials>U</span>
            </button>

            <div class="pt-nav-dropdown" hidden>
                <div class="pt-nav-dropdown-user">
                    <span class="pt-nav-avatar" data-profile-initials>U</span>

                    <span class="pt-nav-dropdown-info">
                        <strong data-profile-nav-name>Tài khoản</strong>
                        <small data-profile-nav-email></small>
                    </span>
                </div>

                <div class="pt-nav-menu-divider"></div>

                <a href="profile.html">
                    <span class="pt-nav-menu-icon">♙</span>
                    <span>Hồ sơ cá nhân</span>
                </a>

                <a href="profile.html#settings">
                    <span class="pt-nav-menu-icon">⚙</span>
                    <span>Cài đặt tài khoản</span>
                </a>

                <a href="profile.html#password">
                    <span class="pt-nav-menu-icon">♢</span>
                    <span>Đổi mật khẩu</span>
                </a>

                <div class="pt-nav-menu-divider"></div>

                <div class="pt-nav-logout-slot"></div>
            </div>
        `;

        oldUserLink.replaceWith(profile);

        oldLogout.classList.add("pt-nav-logout-button");
        oldLogout.innerHTML = `
            <span class="pt-nav-menu-icon" aria-hidden="true">↪</span>
            <span>Đăng xuất</span>
        `;

        profile.querySelector(".pt-nav-logout-slot")
            .appendChild(oldLogout);

        const trigger = profile.querySelector(
            ".pt-nav-profile-trigger"
        );
        const dropdown = profile.querySelector(
            ".pt-nav-dropdown"
        );

        function closeMenu() {
            dropdown.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
            profile.classList.remove("is-open");
        }

        trigger.addEventListener("click", () => {
            const opening = dropdown.hidden;
            dropdown.hidden = !opening;
            trigger.setAttribute("aria-expanded", String(opening));
            profile.classList.toggle("is-open", opening);
        });

        document.addEventListener("click", event => {
            if (!profile.contains(event.target)) closeMenu();
        });

        document.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                closeMenu();
                trigger.focus();
            }
        });
    }

    function updateProfileMenu(user) {
        if (!user) return;

        const name = user.display_name || user.name || user.email || "Tài khoản";
        const parts = String(name).trim().split(/\s+/);
        const initials = parts.length > 1
            ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
            : String(name).slice(0, 2).toUpperCase();

        document.querySelectorAll("[data-profile-initials]")
            .forEach(el => { el.textContent = initials; });

        document.querySelectorAll("[data-profile-nav-name]")
            .forEach(el => { el.textContent = name; });

        document.querySelectorAll("[data-profile-nav-email]")
            .forEach(el => { el.textContent = user.email || ""; });
    }

    function addNavbarIcons() {
        const nav = document.querySelector(".app-header nav");
        if (!nav) return;

        const icons = {
            "dashboard.html": `
                <rect x="3" y="3" width="7" height="7" rx="1.5"/>
                <rect x="14" y="3" width="7" height="7" rx="1.5"/>
                <rect x="3" y="14" width="7" height="7" rx="1.5"/>
                <rect x="14" y="14" width="7" height="7" rx="1.5"/>
            `,
            "projects.html": `
                <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            `,
            "kanban.html": `
                <rect x="3" y="4" width="18" height="16" rx="2"/>
                <path d="M9 4v16M15 4v16"/>
                <path d="M5.5 8h1M11.5 8h1M17.5 8h1"/>
            `
        };

        nav.querySelectorAll("a[href]").forEach(link => {
            const page = link.getAttribute("href")
                .split("?")[0]
                .split("#")[0]
                .split("/")
                .pop();

            if (!icons[page]) return;
            if (link.querySelector(".pt-nav-icon")) return;

            const icon = document.createElement("span");
            icon.className = "pt-nav-icon";
            icon.setAttribute("aria-hidden", "true");

            icon.innerHTML = `
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    ${icons[page]}
                </svg>
            `;

            link.prepend(icon);
        });
    }

    function addNavbarIcons() {
        const nav = document.querySelector(".app-header nav");
        if (!nav) return;

        const icons = {
            "dashboard.html": `
                <rect x="3" y="3" width="7" height="7" rx="1.5"/>
                <rect x="14" y="3" width="7" height="7" rx="1.5"/>
                <rect x="3" y="14" width="7" height="7" rx="1.5"/>
                <rect x="14" y="14" width="7" height="7" rx="1.5"/>
            `,
            "projects.html": `
                <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            `,
            "kanban.html": `
                <rect x="3" y="4" width="18" height="16" rx="2"/>
                <path d="M9 4v16M15 4v16"/>
                <path d="M5.5 8h1M11.5 8h1M17.5 8h1"/>
            `
        };

        nav.querySelectorAll("a[href]").forEach(link => {
            const page = link.getAttribute("href")
                .split("?")[0]
                .split("#")[0]
                .split("/")
                .pop();

            if (!icons[page]) return;
            if (link.querySelector(".pt-nav-icon")) return;

            const icon = document.createElement("span");
            icon.className = "pt-nav-icon";
            icon.setAttribute("aria-hidden", "true");

            icon.innerHTML = `
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    ${icons[page]}
                </svg>
            `;

            link.prepend(icon);
        });
    }

    buildProfileMenu();
    addNavbarIcons();
    addNavbarIcons();
    window.addEventListener("pulse:auth-changed", event => {
        if (event.detail?.status === "authenticated") {
            updateProfileMenu(event.detail.user);
        }
    });

})();
