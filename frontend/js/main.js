
"use strict";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const PASSWORD_REGEX =
    /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9\s])[^\s]{8,}$/;

const AUTH_API = {
    register: "/auth/register",
    login: "/auth/login"
};

function fieldError(form, name) {
    const input = form.elements.namedItem(name);

    if (!input) return "";

    const value = input.value;
    const trimmed = value.trim();
    const register = form.dataset.authForm === "register";

    if (name === "name") {
        if (!trimmed) {
            return "Vui lòng nhập họ và tên.";
        }

        if (trimmed.length < 2) {
            return "Họ và tên phải có ít nhất 2 ký tự.";
        }

        if (trimmed.length > 100) {
            return "Họ và tên không được vượt quá 100 ký tự.";
        }
    }

    if (name === "email") {
        if (!trimmed) {
            return "Vui lòng nhập email.";
        }

        if (!EMAIL_REGEX.test(trimmed)) {
            return "Email không đúng định dạng.";
        }
    }

    if (name === "password") {
        if (!value) {
            return "Vui lòng nhập mật khẩu.";
        }

        if (register) {
            if (!PASSWORD_REGEX.test(value)) {
                return "Mật khẩu phải có ít nhất 8 ký tự, chữ hoa, chữ thường, số, ký tự đặc biệt và không chứa khoảng trắng.";
            }

            if (new TextEncoder().encode(value).length > 72) {
                return "Mật khẩu không được vượt quá 72 byte.";
            }
        }
    }

    if (name === "confirm") {
        if (!value) {
            return "Vui lòng xác nhận mật khẩu.";
        }

        if (
            value !==
            form.elements.namedItem("password")?.value
        ) {
            return "Mật khẩu xác nhận không khớp.";
        }
    }

    return "";
}

function validateField(form, name) {
    const input = form.elements.namedItem(name);

    if (!input) return false;

    const error = fieldError(form, name);
    const errorBox = form.querySelector(`#${name}-error`);

    if (errorBox) {
        errorBox.textContent = error;
    }

    input.classList.toggle(
        "input-error",
        Boolean(error)
    );

    input.setAttribute(
        "aria-invalid",
        String(Boolean(error))
    );

    return !error;
}

function showMessage(form, message, type = "error") {
    const box = form.querySelector(".message");

    if (!box) return;

    box.textContent = message;
    box.dataset.type = type;
}

function apiErrorMessage(error, register) {
    const status = Number(error?.status || 0);

    if (error?.code === "REQUEST_ABORTED") {
        return "Yêu cầu quá thời gian chờ. Vui lòng thử lại.";
    }

    if (error?.code === "NETWORK_ERROR") {
        return "Không thể kết nối Backend. Vui lòng kiểm tra máy chủ và thử lại.";
    }

    if (error?.code === "INVALID_JSON") {
        return "Phản hồi máy chủ không hợp lệ. Vui lòng thử lại.";
    }

    if (status === 400 || status === 422) {
        return "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại thông tin.";
    }

    if (status === 401) {
        return "Email hoặc mật khẩu không chính xác.";
    }

    if (status === 403) {
        return "Bạn không có quyền thực hiện yêu cầu này.";
    }

    if (status === 409) {
        return register
            ? "Email đã được sử dụng. Vui lòng chọn email khác."
            : "Yêu cầu bị xung đột. Vui lòng thử lại.";
    }

    if (status === 404) {
        return "API xác thực chưa được triển khai trên Backend.";
    }

    if (status === 429) {
        return "Bạn gửi quá nhiều yêu cầu. Vui lòng thử lại sau.";
    }

    if (status >= 500) {
        return "Máy chủ đang gặp sự cố. Vui lòng thử lại sau.";
    }

    return "Không thể xử lý yêu cầu. Vui lòng thử lại.";
}

function showRegisterSuccessModal() {
    const modal = document.getElementById(
        "register-success-modal"
    );

    if (!modal) {
        console.error(
            "Không tìm thấy Popup đăng ký thành công."
        );
        return false;
    }

    modal.hidden = false;
    modal.classList.add("show");

    const loginButton = modal.querySelector(
        ".success-login-btn"
    );

    if (loginButton) {
        loginButton.focus();
    }

    return true;
}

function showLoginSuccess(form) {
    const existingBox = form.querySelector(
        ".login-success"
    );

    if (existingBox) {
        existingBox.remove();
    }

    const successBox = document.createElement("div");

    successBox.className = "login-success";
    successBox.setAttribute("role", "status");
    successBox.setAttribute("aria-live", "polite");

    successBox.innerHTML = `
        <div class="login-success-content">
            <span class="login-success-icon">✓</span>

            <div class="login-success-text">
                <strong>Đăng nhập thành công!</strong>
                <p>Đang chuyển đến trang tổng quan...</p>
            </div>
        </div>

        <div class="login-progress">
            <div class="login-progress-bar"></div>
        </div>
    `;

    const messageBox = form.querySelector(".message");

    if (messageBox) {
        messageBox.insertAdjacentElement(
            "afterend",
            successBox
        );
    } else {
        form.appendChild(successBox);
    }
}

document.querySelectorAll(
    "[data-toggle-password]"
).forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById(
            button.dataset.togglePassword
        );

        if (!input) return;

        const hidden = input.type === "password";

        input.type = hidden ? "text" : "password";
        button.textContent = hidden ? "Ẩn" : "Hiện";

        button.setAttribute(
            "aria-label",
            hidden
                ? "Ẩn mật khẩu"
                : "Hiển thị mật khẩu"
        );
    });
});

document.querySelectorAll(
    "[data-auth-form]"
).forEach((form) => {
    const register =
        form.dataset.authForm === "register";

    const fields = register
        ? ["name", "email", "password", "confirm"]
        : ["email", "password"];

    const touched = new Set();

    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    const originalText =
        submitButton?.textContent || "";

    let submitting = false;
    let completed = false;

    fields.forEach((name) => {
        const input = form.elements.namedItem(name);

        if (!input) return;

        input.addEventListener("blur", () => {
            if (completed) return;

            touched.add(name);
            validateField(form, name);
        });

        input.addEventListener("input", () => {
            if (completed) return;

            showMessage(form, "");

            if (touched.has(name)) {
                validateField(form, name);
            }

            if (
                register &&
                name === "password" &&
                touched.has("confirm")
            ) {
                validateField(form, "confirm");
            }
        });
    });

    form.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            if (submitting || completed) return;

            let firstInvalid = null;

            fields.forEach((name) => {
                touched.add(name);

                if (
                    !validateField(form, name) &&
                    !firstInvalid
                ) {
                    firstInvalid =
                        form.elements.namedItem(name);
                }
            });

            if (firstInvalid) {
                showMessage(
                    form,
                    "Vui lòng kiểm tra lại thông tin đã nhập."
                );

                firstInvalid.focus();
                return;
            }

            const email = form.elements
                .namedItem("email")
                .value.trim()
                .toLowerCase();

            const password = form.elements
                .namedItem("password")
                .value;

            const payload = register
                ? {
                    display_name: form.elements
                        .namedItem("name")
                        .value.trim(),
                    email: email,
                    password: password
                }
                : {
                    email: email,
                    password: password
                };

            submitting = true;

            if (submitButton) {
                submitButton.disabled = true;

                submitButton.setAttribute(
                    "aria-busy",
                    "true"
                );

                submitButton.textContent =
                    "Đang xử lý...";
            }

            showMessage(form, "");

            try {
                if (!window.PulseAPI?.post) {
                    throw {
                        code: "NETWORK_ERROR"
                    };
                }

                await window.PulseAPI.post(
                    register
                        ? AUTH_API.register
                        : AUTH_API.login,
                    payload,
                    {
                        skipAuthRedirect: true
                    }
                );

                if (register) {
                    const modalOpened =
                        showRegisterSuccessModal();

                    if (!modalOpened) {
                        showMessage(
                            form,
                            "Đăng ký thành công! Vui lòng chuyển sang trang đăng nhập.",
                            "success"
                        );

                        if (submitButton) {
                            submitButton.hidden = true;
                        }
                    }

                    completed = true;
                } else {
                    showMessage(form, "");

                    if (submitButton) {
                        submitButton.hidden = true;
                    }

                    showLoginSuccess(form);

                    completed = true;

                    await new Promise((resolve) => {
                        setTimeout(resolve, 1500);
                    });

                    window.location.assign(
                        window.PULSE_CONFIG
                            ?.AFTER_LOGIN_PAGE ||
                        "dashboard.html"
                    );
                }
            } catch (error) {
                showMessage(
                    form,
                    apiErrorMessage(error, register)
                );
            } finally {
                submitting = false;

                if (!completed && submitButton) {
                    submitButton.disabled = false;

                    submitButton.setAttribute(
                        "aria-busy",
                        "false"
                    );

                    submitButton.textContent =
                        originalText;
                }
            }
        }
    );
});
