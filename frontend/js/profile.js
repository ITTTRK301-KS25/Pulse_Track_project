
"use strict";

(function () {
    const form = document.getElementById("profile-form");

    if (!form) return;

    const nameInput = document.getElementById("display-name");
    const emailInput = document.getElementById("profile-email-input");
    const nameError = document.getElementById("display-name-error");
    const message = document.getElementById("profile-message");
    const saveButton = document.getElementById("save-profile");

    const profileName = document.getElementById("profile-name");
    const profileEmail = document.getElementById("profile-email");
    const avatar = document.getElementById("profile-avatar");

    let currentUser = null;
    let saving = false;

    function showMessage(text, type = "error") {
        message.textContent = text;
        message.dataset.type = type;
    }

    function showNameError(text) {
        nameError.textContent = text;
        nameInput.classList.toggle("input-error", Boolean(text));
        nameInput.setAttribute("aria-invalid", String(Boolean(text)));
    }

    function validateName() {
        const name = nameInput.value.trim().replace(/\s+/g, " ");

        if (!name) {
            showNameError("Vui lòng nhập tên hiển thị.");
            return null;
        }

        if (name.length < 2) {
            showNameError("Tên hiển thị phải có ít nhất 2 ký tự.");
            return null;
        }

        if (name.length > 100) {
            showNameError("Tên hiển thị không được vượt quá 100 ký tự.");
            return null;
        }

        showNameError("");
        return name;
    }

    function render(user) {
        currentUser = user;

        const name = user.display_name || user.name || "";
        const email = user.email || "";

        profileName.textContent = name || "Người dùng";
        profileEmail.textContent = email;

        avatar.textContent =
            (name || email || "U").trim().charAt(0).toUpperCase();

        nameInput.value = name;
        emailInput.value = email;

        saveButton.disabled = saving;
    }

    window.addEventListener("pulse:auth-changed", (event) => {
        if (event.detail.status === "authenticated") {
            render(event.detail.user);
        } else {
            currentUser = null;
            saveButton.disabled = true;
        }
    });

    if (window.PulseAuth?.status === "authenticated") {
        render(window.PulseAuth.user);
    } else {
        saveButton.disabled = true;
    }

    nameInput.addEventListener("input", () => {
        if (nameError.textContent) {
            validateName();
        }

        showMessage("");
    });

    nameInput.addEventListener("blur", validateName);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (saving || !currentUser) return;

        showMessage("");

        const name = validateName();

        if (!name) return;

        const oldName = (
            currentUser.display_name ||
            currentUser.name ||
            ""
        ).trim().replace(/\s+/g, " ");

        if (name === oldName) {
            showMessage("Thông tin chưa có thay đổi.", "success");
            return;
        }

        saving = true;
        saveButton.disabled = true;
        saveButton.textContent = "Đang lưu...";

        try {
            const response = await window.PulseAPI.patch(
                "/auth/me",
                { display_name: name },
                { skipAuthRedirect: true }
            );

            const updatedUser = response?.data;

            if (
                !updatedUser ||
                typeof updatedUser !== "object" ||
                !updatedUser.email
            ) {
                throw new Error(
                    "Backend không trả về thông tin người dùng hợp lệ."
                );
            }

            window.dispatchEvent(
                new CustomEvent("pulse:user-updated", {
                    detail: { user: updatedUser }
                })
            );

            showNameError("");
            showMessage("Cập nhật hồ sơ thành công.", "success");
        } catch (error) {
            if (error.status === 401) {
                location.replace("login.html");
                return;
            }

            if (error.status === 400 || error.status === 422) {
                showMessage("Tên hiển thị không hợp lệ.");
            } else if (error.status === 403) {
                showMessage("Bạn không có quyền cập nhật hồ sơ.");
            } else if (error.code === "NETWORK_ERROR") {
                showMessage("Không thể kết nối Backend.");
            } else if (error.code === "REQUEST_ABORTED") {
                showMessage("Kết nối quá thời gian chờ.");
            } else {
                showMessage(
                    error.message || "Cập nhật hồ sơ thất bại."
                );
            }
        } finally {
            saving = false;
            saveButton.disabled = !currentUser;
            saveButton.textContent = "Lưu thay đổi";
        }
    });
})();
