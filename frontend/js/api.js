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
                (
                    data &&
                    typeof data === "object" &&
                    (data.message || data.detail)
                ) ||
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

    // Gộp danh sách dự án hoạt động và đã lưu trữ.

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

})();