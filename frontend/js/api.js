
(function () {
    "use strict";

    const config = window.PULSE_CONFIG;

    if (!config) {
        throw new Error("Thiếu js/config.js");
    }

    class ApiError extends Error {
        constructor(message, status, code, details) {
            super(message);
            this.name = "ApiError";
            this.status = status;
            this.code = code || null;
            this.details = details ?? null;
        }
    }

    function baseUrl() {
        const value = String(config.API_BASE_URL || "")
            .trim()
            .replace(/\/+$/, "");

        if (!value) {
            throw new ApiError(
                "Chưa cấu hình API_BASE_URL",
                0,
                "API_NOT_CONFIGURED"
            );
        }

        if (!/^https?:\/\//i.test(value)) {
            throw new ApiError(
                "API_BASE_URL không hợp lệ",
                0,
                "INVALID_API_URL"
            );
        }

        return value;
    }

    function getCsrfToken() {
        const name = config.CSRF_META_NAME;

        return name
            ? document.querySelector(`meta[name="${name}"]`)?.content || ""
            : "";
    }

    async function request(path, options = {}) {
        if (!path.startsWith("/") || path.startsWith("//")) {
            throw new ApiError(
                "Endpoint không hợp lệ",
                0,
                "INVALID_ENDPOINT"
            );
        }

        const {
            query,
            body,
            headers = {},
            timeout = config.REQUEST_TIMEOUT_MS,
            signal,
            skipAuthRedirect = false,
            ...rest
        } = options;

        const url = new URL(baseUrl() + path);

        if (query) {
            Object.entries(query).forEach(([key, value]) => {
                if (
                    value !== undefined &&
                    value !== null &&
                    value !== ""
                ) {
                    url.searchParams.set(key, String(value));
                }
            });
        }

        const outgoing = new Headers(headers);

        outgoing.set("Accept", "application/json");

        const isJson =
            body !== undefined &&
            body !== null &&
            !(body instanceof FormData) &&
            typeof body !== "string";

        if (isJson && !outgoing.has("Content-Type")) {
            outgoing.set("Content-Type", "application/json");
        }

        if (
            config.CSRF_HEADER_NAME &&
            !outgoing.has(config.CSRF_HEADER_NAME)
        ) {
            const csrf = getCsrfToken();

            if (csrf) {
                outgoing.set(config.CSRF_HEADER_NAME, csrf);
            }
        }

        const controller = new AbortController();

        const timer = setTimeout(
            () => controller.abort(),
            timeout
        );

        const onAbort = () => controller.abort();

        if (signal) {
            if (signal.aborted) {
                controller.abort();
            } else {
                signal.addEventListener("abort", onAbort, {
                    once: true
                });
            }
        }

        let response;

        try {
            response = await fetch(url.toString(), {
                ...rest,
                credentials: "include",
                headers: outgoing,
                body: isJson ? JSON.stringify(body) : body,
                signal: controller.signal
            });
        } catch (error) {
            if (error.name === "AbortError") {
                throw new ApiError(
                    "Yêu cầu đã bị hủy hoặc quá thời gian chờ",
                    0,
                    "REQUEST_ABORTED"
                );
            }

            throw new ApiError(
                "Không kết nối được Backend. Kiểm tra server và CORS.",
                0,
                "NETWORK_ERROR"
            );
        } finally {
            clearTimeout(timer);

            if (signal) {
                signal.removeEventListener("abort", onAbort);
            }
        }

        const contentType =
            response.headers.get("content-type") || "";

        let data = null;

        if (response.status !== 204 && response.status !== 205) {
            if (contentType.includes("json")) {
                try {
                    data = await response.json();
                } catch {
                    throw new ApiError(
                        "Backend trả về JSON không hợp lệ",
                        response.status,
                        "INVALID_JSON"
                    );
                }
            } else {
                data = await response.text();
            }
        }

        if (!response.ok) {
            const message =
                (data &&
                    typeof data === "object" &&
                    (data.message || data.detail)) ||
                `Yêu cầu thất bại (HTTP ${response.status})`;

            const error = new ApiError(
                typeof message === "string"
                    ? message
                    : JSON.stringify(message),
                response.status,
                data?.code,
                data?.details
            );

            if (response.status === 401) {
                window.dispatchEvent(
                    new CustomEvent("pulse:unauthorized", {
                        detail: { path }
                    })
                );

                if (
                    !skipAuthRedirect &&
                    !window.location.pathname.endsWith("login.html") &&
                    !window.location.pathname.endsWith("register.html")
                ) {
                    window.location.replace(config.LOGIN_PAGE);
                }
            }

            if (response.status === 403) {
                window.dispatchEvent(
                    new CustomEvent("pulse:forbidden", {
                        detail: { message, path }
                    })
                );
            }

            throw error;
        }

        return data;
    }

    // Backend tách dự án hoạt động và đã lưu trữ.
    // Gộp hai danh sách để projects.js lọc chính xác.
    async function get(path, options = {}) {
        if (path === "/projects" && !options.query) {
            const [active, archived] = await Promise.all([
                request("/projects", {
                    ...options,
                    query: { status: "active" }
                }),
                request("/projects", {
                    ...options,
                    query: { status: "archived" }
                })
            ]);

            if (
                !Array.isArray(active?.data) ||
                !Array.isArray(archived?.data)
            ) {
                throw new ApiError(
                    "Danh sách dự án không hợp lệ",
                    0,
                    "INVALID_PROJECT_DATA"
                );
            }

            const unique = new Map();

            active.data.forEach(project => {
                unique.set(String(project.id), project);
            });

            archived.data.forEach(project => {
                unique.set(String(project.id), project);
            });

            return {
                ...active,
                data: [...unique.values()]
            };
        }

        return request(path, {
            ...options,
            method: "GET"
        });
    }

    const API = Object.freeze({
        request,
        get,
        post: (path, body, options) =>
            request(path, {
                ...options,
                method: "POST",
                body
            }),
        patch: (path, body, options) =>
            request(path, {
                ...options,
                method: "PATCH",
                body
            }),
        delete: (path, options) =>
            request(path, {
                ...options,
                method: "DELETE"
            }),
        ApiError
    });

    window.PulseAPI = API;

    // =========================================
    // POPUP XÁC NHẬN LƯU TRỮ / KHÔI PHỤC
    // =========================================

    function showArchivePopup(projectName, isArchive) {
        return new Promise(resolve => {
            const overlay = document.createElement("div");

            overlay.style.cssText = `
                position: fixed;
                inset: 0;
                z-index: 999999;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: rgba(8, 20, 44, .58);
                backdrop-filter: blur(5px);
            `;

            const dialog = document.createElement("div");

            dialog.setAttribute("role", "dialog");
            dialog.setAttribute("aria-modal", "true");
            dialog.setAttribute(
                "aria-label",
                isArchive ? "Xác nhận lưu trữ" : "Xác nhận khôi phục"
            );

            dialog.style.cssText = `
                width: 100%;
                max-width: 440px;
                padding: 30px;
                background: #ffffff;
                border: 1px solid #e3eaf5;
                border-radius: 20px;
                box-shadow: 0 25px 80px rgba(0,0,0,.22);
                font-family: inherit;
                color: #142442;
            `;

            const icon = document.createElement("div");

            icon.textContent = isArchive ? "▣" : "↺";

            icon.style.cssText = `
                display: grid;
                place-items: center;
                width: 54px;
                height: 54px;
                margin-bottom: 18px;
                border-radius: 15px;
                background: ${isArchive ? "#fff0ee" : "#eaf3ff"};
                color: ${isArchive ? "#d84444" : "#1764d8"};
                font-size: 27px;
                font-weight: 700;
            `;

            const title = document.createElement("h2");

            title.textContent = isArchive
                ? "Lưu trữ dự án?"
                : "Khôi phục dự án?";

            title.style.cssText = `
                margin: 0 0 12px;
                font-size: 22px;
                font-weight: 800;
                color: #11244a;
            `;

            const description = document.createElement("p");

            description.textContent = isArchive
                ? `Dự án "${projectName}" sẽ được chuyển sang danh sách Đã lưu trữ. Bạn có thể khôi phục dự án khi cần.`
                : `Bạn muốn khôi phục dự án "${projectName}" về danh sách Đang hoạt động?`;

            description.style.cssText = `
                margin: 0 0 26px;
                color: #64748b;
                font-size: 14px;
                line-height: 1.7;
            `;

            const actions = document.createElement("div");

            actions.style.cssText = `
                display: flex;
                justify-content: flex-end;
                gap: 12px;
            `;

            function makeButton(text, primary) {
                const button = document.createElement("button");

                button.type = "button";
                button.textContent = text;

                button.style.cssText = `
                    min-height: 43px;
                    padding: 0 20px;
                    border-radius: 10px;
                    border: 1px solid ${
                        primary ? "transparent" : "#d9e3f2"
                    };
                    background: ${
                        primary
                            ? isArchive ? "#e24b4b" : "#1769ed"
                            : "#ffffff"
                    };
                    color: ${primary ? "#ffffff" : "#334155"};
                    font-family: inherit;
                    font-size: 14px;
                    font-weight: 700;
                    cursor: pointer;
                `;

                return button;
            }

            const cancel = makeButton("Hủy", false);

            const confirmButton = makeButton(
                isArchive ? "Lưu trữ dự án" : "Khôi phục",
                true
            );

            actions.append(cancel, confirmButton);

            dialog.append(icon, title, description, actions);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            function finish(value) {
                document.removeEventListener("keydown", onKey);
                overlay.remove();
                resolve(value);
            }

            function onKey(event) {
                if (event.key === "Escape") {
                    finish(false);
                }
            }

            cancel.addEventListener("click", () => finish(false));

            confirmButton.addEventListener(
                "click",
                () => finish(true)
            );

            overlay.addEventListener("click", event => {
                if (event.target === overlay) {
                    finish(false);
                }
            });

            document.addEventListener("keydown", onKey);

            confirmButton.focus();
        });
    }

    // =========================================
    // XỬ LÝ NÚT LƯU TRỮ / KHÔI PHỤC
    // =========================================

    if (window.location.pathname.endsWith("projects.html")) {
        const pendingFilter = sessionStorage.getItem(
            "pulse-project-filter-once"
        );

        if (pendingFilter) {
            const filter = document.getElementById("filter-status");

            if (filter) {
                filter.value = pendingFilter;
            }

            sessionStorage.removeItem(
                "pulse-project-filter-once"
            );
        }

        let processing = false;

        document.addEventListener(
            "click",
            async event => {
                const button = event.target.closest(
                    '[data-act="archive"], [data-act="restore"]'
                );

                if (!button || processing) return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const card = button.closest("[data-id]");

                if (!card) return;

                const projectId = card.dataset.id;
                const projectName =
                    card.querySelector("h3")?.textContent?.trim() ||
                    "Dự án";

                const action = button.dataset.act;
                const isArchive = action === "archive";

                const confirmed = await showArchivePopup(
                    projectName,
                    isArchive
                );

                if (!confirmed) return;

                processing = true;
                button.disabled = true;

                const originalText = button.textContent;

                button.textContent = isArchive
                    ? "Đang lưu trữ..."
                    : "Đang khôi phục...";

                try {
                    await API.post(
                        `/projects/${encodeURIComponent(projectId)}/${action}`
                    );

                    sessionStorage.setItem(
                        "pulse-project-filter-once",
                        isArchive ? "archived" : "active"
                    );

                    window.location.reload();
                } catch (error) {
                    processing = false;
                    button.disabled = false;
                    button.textContent = originalText;

                    alert(
                        error.message ||
                        "Không thể cập nhật trạng thái dự án"
                    );
                }
            },
            true
        );
    }
})();
