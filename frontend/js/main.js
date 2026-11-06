
"use strict";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9\s])[^\s]{8,}$/;

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
        if (!trimmed) return "Vui lòng nhập họ và tên.";
        if (trimmed.length < 2) {
            return "Họ và tên phải có ít nhất 2 ký tự.";
        }
    }

    if (name === "email") {
        if (!trimmed) return "Vui lòng nhập email.";
        if (!EMAIL_REGEX.test(trimmed)) {
            return "Email không đúng định dạng.";
        }
    }

    if (name === "password") {
        if (!value) return "Vui lòng nhập mật khẩu.";

        if (register && !PASSWORD_REGEX.test(value)) {
            return "Mật khẩu phải có ít nhất 8 ký tự, chữ hoa, chữ thường, số, ký tự đặc biệt và không chứa khoảng trắng.";
        }
    }

    if (name === "confirm") {
        if (!value) return "Vui lòng xác nhận mật khẩu.";

        if (value !== form.elements.namedItem("password")?.value) {
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

    input.classList.toggle("input-error", Boolean(error));
    input.setAttribute("aria-invalid", String(Boolean(error)));

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

document.querySelectorAll("[data-toggle-password]").forEach((button) => {
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
            hidden ? "Ẩn mật khẩu" : "Hiển thị mật khẩu"
        );
    });
});

document.querySelectorAll("[data-auth-form]").forEach((form) => {
    const register = form.dataset.authForm === "register";

    const fields = register
        ? ["name", "email", "password", "confirm"]
        : ["email", "password"];

    const touched = new Set();

    const submitButton = form.querySelector(
        'button[type="submit"]'
    );

    const originalText = submitButton?.textContent || "";

    let submitting = false;

    fields.forEach((name) => {
        const input = form.elements.namedItem(name);

        if (!input) return;

        input.addEventListener("blur", () => {
            touched.add(name);
            validateField(form, name);
        });

        input.addEventListener("input", () => {
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

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (submitting) return;

        let firstInvalid = null;

        fields.forEach((name) => {
            touched.add(name);

            if (!validateField(form, name) && !firstInvalid) {
                firstInvalid = form.elements.namedItem(name);
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

        const email = form.elements.namedItem("email")
            .value.trim().toLowerCase();

        const password = form.elements.namedItem("password").value;

        const payload = register
            ? {
                display_name: form.elements.namedItem("name").value.trim(),
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
            submitButton.setAttribute("aria-busy", "true");
            submitButton.textContent = "Đang xử lý...";
        }

        showMessage(form, "");

        try {
            if (!window.PulseAPI?.post) {
                showMessage(
                    form,
                    "Không tải được HTTP client. Kiểm tra js/api.js."
                );
                return;
            }

            await window.PulseAPI.post(
                register ? AUTH_API.register : AUTH_API.login,
                payload,
                { skipAuthRedirect: true }
            );

            showMessage(
                form,
                register
                    ? "Đăng ký thành công!"
                    : "Đăng nhập thành công!",
                "success"
            );

            if (register) {
                window.location.assign("login.html");
            } else {
                window.location.assign(
                    window.PULSE_CONFIG?.AFTER_LOGIN_PAGE ||
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

            if (submitButton) {
                submitButton.disabled = false;
                submitButton.setAttribute("aria-busy", "false");
                submitButton.textContent = originalText;
            }
        }
    });
});
