
"use strict";

(function () {
    const API = window.PulseAPI;
    const $ = id => document.getElementById(id);

    const form = $("profile-form");
    if (!form) return;

    const nameInput = $("display-name");
    const emailInput = $("profile-email-input");
    const saveButton = $("save-profile");
    const nameError = $("display-name-error");
    const message = $("profile-message");

    let currentUser = null;
    let saving = false;
    let loadingForUser = null;

    function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value == null || value === "" ? "—" : String(value);
    }

    function showMessage(text, type = "error") {
        message.textContent = text;
        message.dataset.type = type;
    }

    function formatDate(value) {
        if (!value) return "—";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";
        return new Intl.DateTimeFormat("vi-VN", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
        }).format(date);
    }

    function initials(name) {
        const words = String(name || "").trim().split(/\s+/).filter(Boolean);
        if (!words.length) return "U";
        if (words.length === 1) return words[0][0].toUpperCase();
        return (words[0][0] + words[words.length - 1][0]).toUpperCase();
    }

    function renderUser(user) {
        currentUser = user;
        const name = user.display_name || user.name || "Người dùng";
        const email = user.email || "";

        setText("profile-name", name);
        setText("profile-email", email);
        setText("profile-info-name", name);
        setText("profile-info-email", email);
        setText("profile-avatar", initials(name));
        setText("profile-created-at", formatDate(user.created_at));

        nameInput.value = user.display_name || user.name || "";
        emailInput.value = email;
        saveButton.disabled = saving;
    }

    function openSection(section) {
        const valid = ["overview", "settings", "password"];
        if (!valid.includes(section)) section = "overview";

        document.querySelectorAll("[data-profile-section]")
            .forEach(el => {
                el.hidden = el.dataset.profileSection !== section;
            });

        document.querySelectorAll("[data-section]")
            .forEach(button => {
                const active = button.dataset.section === section;
                button.classList.toggle("is-active", active);
                if (active) button.setAttribute("aria-current", "page");
                else button.removeAttribute("aria-current");
            });

        if (section !== "password") {
            $("password-preview-form").reset();
            ["current-password", "new-password", "confirm-password"]
                .forEach(id => { $(id).type = "password"; });
        }

        if (section === "settings" && currentUser) {
            nameInput.value =
                currentUser.display_name || currentUser.name || "";
            nameError.textContent = "";
            showMessage("");
        }

        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    document.querySelectorAll("[data-section], [data-open-section]")
        .forEach(button => {
            button.addEventListener("click", () => {
                openSection(
                    button.dataset.section || button.dataset.openSection
                );
            });
        });

    window.addEventListener("hashchange", () => {
        openSection(location.hash.slice(1));
    });

    openSection(location.hash.slice(1));

    $("toggle-password-visibility").addEventListener("change", event => {
        const type = event.target.checked ? "text" : "password";
        ["current-password", "new-password", "confirm-password"]
            .forEach(id => { $(id).type = type; });
    });

    $("password-preview-form").addEventListener("submit", event => {
        event.preventDefault();
    });

    function validateName() {
        const name = nameInput.value.trim().replace(/\s+/g, " ");
        let error = "";

        if (!name) error = "Vui lòng nhập họ và tên.";
        else if (name.length < 2) error = "Họ tên phải có ít nhất 2 ký tự.";
        else if (name.length > 100) error = "Họ tên không quá 100 ký tự.";

        nameError.textContent = error;
        nameInput.setAttribute("aria-invalid", String(Boolean(error)));
        return error ? null : name;
    }

    nameInput.addEventListener("input", () => {
        if (nameError.textContent) validateName();
        showMessage("");
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!currentUser || saving) return;

        const name = validateName();
        if (!name) return;

        const oldName = (
            currentUser.display_name || currentUser.name || ""
        ).trim().replace(/\s+/g, " ");

        if (name === oldName) {
            showMessage("Thông tin chưa có thay đổi.", "success");
            return;
        }

        saving = true;
        saveButton.disabled = true;
        saveButton.textContent = "Đang lưu...";
        showMessage("");

        try {
            const response = await API.patch(
                "/auth/me",
                { display_name: name },
                { skipAuthRedirect: true }
            );

            const user = response?.data;
            if (!user || typeof user !== "object" || !user.email) {
                throw new Error("Backend trả về thông tin không hợp lệ.");
            }

            renderUser(user);
            window.dispatchEvent(new CustomEvent("pulse:user-updated", {
                detail: { user }
            }));
            showMessage("Cập nhật hồ sơ thành công.", "success");
        } catch (error) {
            if (error.status === 401) {
                location.replace("login.html");
                return;
            }
            showMessage(error.message || "Không thể cập nhật hồ sơ.");
        } finally {
            saving = false;
            saveButton.disabled = !currentUser;
            saveButton.textContent = "Lưu thay đổi";
        }
    });

    function projectRow(project) {
        const row = document.createElement("a");
        row.className = "pt-project-row";
        row.href = "kanban.html?project=" + encodeURIComponent(project.id);

        const icon = document.createElement("span");
        icon.className = "pt-project-icon";
        icon.textContent = "▦";

        const info = document.createElement("span");
        info.className = "pt-project-info";

        const title = document.createElement("strong");
        title.textContent = project.name || project.title || "Dự án";

        const description = document.createElement("small");
        description.textContent = project.description || "Quản lý công việc nhóm";

        info.append(title, description);

        const role = document.createElement("span");
        const roleName = project.my_role || project.role || "MEMBER";
        role.className = "pt-role-badge pt-role-" + (
            ["OWNER", "MEMBER", "VIEWER"].includes(roleName)
                ? roleName.toLowerCase()
                : "member"
        );
        role.textContent = roleName;

        const arrow = document.createElement("span");
        arrow.className = "pt-project-arrow";
        arrow.textContent = "›";

        row.append(icon, info, role, arrow);
        return row;
    }

    async function loadProjectsAndStats(user) {
        const container = $("profile-projects");
        const statsMessage = $("stats-message");

        container.textContent = "Đang tải dự án...";
        statsMessage.textContent = "Đang tải thống kê công việc...";

        ["stat-assigned", "stat-progress", "stat-done"]
            .forEach(id => setText(id, "—"));

        let projects;

        try {
            const response = await API.get("/projects");
            if (!Array.isArray(response?.data)) {
                throw new Error("Danh sách dự án không hợp lệ.");
            }
            projects = response.data.filter(project => !project.archived_at);
        } catch (error) {
            container.textContent = "Không tải được danh sách dự án.";
            statsMessage.textContent =
                "Không thể thống kê công việc khi chưa tải được dự án.";
            return;
        }

        container.replaceChildren();

        if (!projects.length) {
            const empty = document.createElement("p");
            empty.className = "pt-data-message";
            empty.textContent = "Bạn chưa tham gia dự án nào.";
            container.appendChild(empty);
        } else {
            projects.forEach(project => {
                container.appendChild(projectRow(project));
            });
        }

        const results = await Promise.allSettled(
            projects.map(project =>
                API.get(`/projects/${encodeURIComponent(project.id)}/tasks`)
            )
        );

        let assigned = 0;
        let progress = 0;
        let done = 0;
        let failed = 0;

        results.forEach(result => {
            if (
                result.status !== "fulfilled" ||
                !Array.isArray(result.value?.data)
            ) {
                failed++;
                return;
            }

            result.value.data.forEach(task => {
                if (
                    task.parent_id != null ||
                    task.archived_at ||
                    task.assignee_id == null ||
                    String(task.assignee_id) !== String(user.id)
                ) return;

                assigned++;
                if (task.status === "IN_PROGRESS") progress++;
                if (task.status === "DONE") done++;
            });
        });

        if (failed) {
            statsMessage.textContent =
                `Chưa tải được công việc của ${failed} dự án. ` +
                "Số liệu chưa đầy đủ.";
            return;
        }

        setText("stat-assigned", assigned);
        setText("stat-progress", progress);
        setText("stat-done", done);
        statsMessage.textContent = "";
    }

    async function onAuthenticated(user) {
        renderUser(user);

        if (user.id == null) {
            $("stats-message").textContent =
                "Backend chưa trả về ID người dùng để thống kê.";
            return;
        }

        const key = String(user.id);
        if (loadingForUser === key) return;
        loadingForUser = key;
        await loadProjectsAndStats(user);
    }

    window.addEventListener("pulse:auth-changed", event => {
        if (event.detail?.status === "authenticated") {
            onAuthenticated(event.detail.user);
        } else {
            currentUser = null;
            loadingForUser = null;
            saveButton.disabled = true;
        }
    });

    if (window.PulseAuth?.status === "authenticated") {
        onAuthenticated(window.PulseAuth.user);
    } else {
        saveButton.disabled = true;
    }
})();
