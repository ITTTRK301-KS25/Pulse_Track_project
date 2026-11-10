
"use strict";

(function () {
    const listEl = document.getElementById("project-list");
    const filterEl = document.getElementById("filter-status");
    const newBtn = document.getElementById("btn-new-project");

    if (!listEl || !filterEl || !newBtn) return;

    const API = window.PulseAPI;
    const DEFAULT_TZ = "Asia/Ho_Chi_Minh";

    function esc(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function fmtDate(value) {
        if (!value) return "";
        const [y, m, d] = String(value).slice(0, 10).split("-");
        return y && m && d ? `${d}/${m}/${y}` : "";
    }

    function toApiDate(value) {
        const text = value.trim();
        if (!text) return { valid: true, value: null };

        const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text);
        if (!match) return { valid: false, value: null };

        const d = Number(match[1]);
        const m = Number(match[2]);
        const y = Number(match[3]);

        if (y < 1 || y > 9999 || m < 1 || m > 12) {
            return { valid: false, value: null };
        }

        const leap = y % 4 === 0 &&
            (y % 100 !== 0 || y % 400 === 0);

        const days = [
            31, leap ? 29 : 28, 31, 30, 31,
            30, 31, 31, 30, 31, 30, 31
        ];

        if (d < 1 || d > days[m - 1]) {
            return { valid: false, value: null };
        }

        return {
            valid: true,
            value:
                `${String(y).padStart(4, "0")}-` +
                `${String(m).padStart(2, "0")}-` +
                `${String(d).padStart(2, "0")}`
        };
    }

    function toast(message, type = "") {
        let wrap = document.querySelector(".toast-wrap");

        if (!wrap) {
            wrap = document.createElement("div");
            wrap.className = "toast-wrap";
            wrap.setAttribute("aria-live", "polite");
            document.body.appendChild(wrap);
        }

        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = message;
        wrap.appendChild(el);

        setTimeout(() => el.remove(), 4500);
    }

    function openModal(html) {
        const back = document.createElement("div");
        back.className = "modal-backdrop";

        back.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true">
                ${html}
            </div>
        `;

        const onKey = event => {
            if (event.key === "Escape") close();
        };

        function close() {
            back.remove();
            document.removeEventListener("keydown", onKey);
        }

        back.addEventListener("mousedown", event => {
            if (event.target === back) close();
        });

        document.addEventListener("keydown", onKey);
        document.body.appendChild(back);

        return {
            el: back.firstElementChild,
            close
        };
    }

    function timezones() {
        let list = [];

        try {
            list = Intl.supportedValuesOf("timeZone");
        } catch (error) {
            list = [];
        }

        return Array.from(new Set([
            DEFAULT_TZ,
            "Asia/Bangkok",
            "Asia/Singapore",
            "Asia/Tokyo",
            "Europe/London",
            "America/New_York",
            "UTC",
            ...list
        ]));
    }

    async function load() {
        listEl.innerHTML = `
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
        `;

        try {
            const res = await API.get("/projects", {
                query: { status: filterEl.value }
            });

            render(Array.isArray(res?.data) ? res.data : []);
        } catch (err) {
            if (err.status === 401) return;

            listEl.innerHTML = `
                <div class="empty-box">
                    ${esc(err.message || "Không tải được dự án")}
                    <p>
                        <button
                            type="button"
                            class="btn btn-small"
                            id="retry-load"
                        >
                            Thử lại
                        </button>
                    </p>
                </div>
            `;

            document.getElementById("retry-load").onclick = load;
        }
    }

    function openProjectBoard(project) {
        if (!project || project.id == null) return;

        sessionStorage.setItem(
            "selectedProjectId",
            String(project.id)
        );

        sessionStorage.setItem(
            "selectedProjectName",
            project.name || ""
        );

        window.location.href =
            "kanban.html?project=" +
            encodeURIComponent(project.id);
    }

    function openAddMemberModal(project) {
        if (!project || project.id == null) return;

        const modal = openModal(`
            <h2>Thêm thành viên</h2>

            <form class="form-grid" novalidate>
                <label>
                    Dự án đang chọn
                    <input
                        type="text"
                        name="project_name"
                        value="${esc(project.name)}"
                        class="project-readonly"
                        readonly
                    >
                </label>

                <label>
                    Email thành viên *
                    <input
                        type="email"
                        name="email"
                        placeholder="Nhập email đã đăng ký"
                        maxlength="254"
                        autocomplete="off"
                        required
                    >
                    <span
                        class="field-error"
                        data-err="email"
                    ></span>
                </label>

                <label>
                    Tên thành viên
                    <input
                        type="text"
                        name="display_name"
                        placeholder="Tự động hiển thị khi tìm thấy email"
                        class="project-readonly"
                        readonly
                    >
                    <span
                        class="member-lookup-status"
                        aria-live="polite"
                    ></span>
                </label>

                <label>
                    Vai trò *
                    <select name="role" required>
                        <option value="MEMBER">Member</option>
                        <option value="VIEWER">Viewer</option>
                    </select>
                </label>

                <label>
                    Mô tả chức vụ
                    <textarea
                        name="job_description"
                        placeholder="Ví dụ: Phụ trách Frontend"
                        maxlength="500"
                        rows="4"
                    ></textarea>
                </label>

                <div
                    class="form-banner"
                    role="alert"
                    hidden
                ></div>

                <div class="modal-actions">
                    <button
                        type="button"
                        class="btn"
                        data-close
                    >
                        Hủy
                    </button>

                    <button
                        type="submit"
                        class="btn btn-primary"
                        disabled
                    >
                        Thêm thành viên
                    </button>
                </div>
            </form>
        `);

        const form = modal.el.querySelector("form");
        const banner = form.querySelector(".form-banner");
        const emailInput = form.elements.email;
        const nameInput = form.elements.display_name;
        const roleInput = form.elements.role;
        const descriptionInput = form.elements.job_description;

        const emailError = form.querySelector(
            '[data-err="email"]'
        );

        const statusEl = form.querySelector(
            ".member-lookup-status"
        );

        const submitBtn = form.querySelector(
            'button[type="submit"]'
        );

        let verifiedEmail = "";
        let lookupTimer = null;
        let lookupVersion = 0;
        let closed = false;

        function closeMemberModal() {
            closed = true;
            lookupVersion++;
            clearTimeout(lookupTimer);
            modal.close();
        }

        modal.el.querySelector("[data-close]").onclick =
            closeMemberModal;

        emailInput.addEventListener("input", function () {
            clearTimeout(lookupTimer);
            lookupVersion++;

            const version = lookupVersion;
            const email = emailInput.value.trim().toLowerCase();

            verifiedEmail = "";
            nameInput.value = "";
            submitBtn.disabled = true;
            emailError.textContent = "";
            statusEl.textContent = "";
            statusEl.className = "member-lookup-status";

            if (!email) return;

            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                emailError.textContent = "Email chưa hợp lệ";
                return;
            }

            statusEl.textContent = "Đang kiểm tra tài khoản...";

            lookupTimer = setTimeout(async () => {
                try {
                    // Backend cần hỗ trợ API này.
                    // Phản hồi dự kiến:
                    // { data: { display_name: "Nguyễn Văn A" } }

                    const response = await API.get(
                        "/users/lookup",
                        { query: { email } }
                    );

                    if (
                        closed ||
                        version !== lookupVersion ||
                        emailInput.value.trim().toLowerCase() !== email
                    ) {
                        return;
                    }

                    const user = response?.data;

                    if (user?.display_name) {
                        nameInput.value = user.display_name;
                        verifiedEmail = email;

                        statusEl.textContent =
                            "Đã tìm thấy tài khoản";

                        statusEl.classList.add("success");
                        submitBtn.disabled = false;
                    } else {
                        statusEl.textContent =
                            "Không tìm thấy tài khoản";

                        statusEl.classList.add("error");
                    }
                } catch (err) {
                    if (closed || version !== lookupVersion) {
                        return;
                    }

                    statusEl.textContent =
                        err.status === 404
                            ? "Không tìm thấy tài khoản hoặc API chưa có"
                            : "Không thể kiểm tra tài khoản";

                    statusEl.classList.add("error");
                }
            }, 500);
        });

        form.addEventListener("submit", async event => {
            event.preventDefault();

            banner.hidden = true;
            banner.textContent = "";

            const email = emailInput.value.trim().toLowerCase();
            const role = roleInput.value;
            const description = descriptionInput.value.trim();

            if (!email || verifiedEmail !== email) {
                banner.textContent =
                    "Vui lòng nhập email đã được xác thực.";

                banner.hidden = false;
                return;
            }

            if (!["MEMBER", "VIEWER"].includes(role)) {
                banner.textContent = "Vai trò không hợp lệ.";
                banner.hidden = false;
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = "Đang thêm...";

            try {
                await API.post(
                    `/projects/${encodeURIComponent(project.id)}/members`,
                    { email, role }
                );

                // Chỉ lưu mô tả tại trình duyệt.
                // Chưa đồng bộ mô tả với Backend.
                if (description) {
                    localStorage.setItem(
                        `pulse_member_description_${project.id}_${email}`,
                        description
                    );
                }

                closeMemberModal();
                toast("Thêm thành viên thành công", "success");
                await load();
            } catch (err) {
                if (err.status === 401) return;

                banner.textContent =
                    err.message || "Không thể thêm thành viên";

                banner.hidden = false;
                submitBtn.disabled = false;
                submitBtn.textContent = "Thêm thành viên";
            }
        });

        emailInput.focus();
    }

    function render(items) {
        if (!items.length) {
            listEl.innerHTML = `
                <div class="empty-box">
                    ${
                        filterEl.value === "archived"
                            ? "Chưa có dự án nào được lưu trữ."
                            : "Chưa có dự án nào. Bấm “+ Tạo dự án” để bắt đầu."
                    }
                </div>
            `;
            return;
        }

        listEl.innerHTML = items.map(p => `
            <article
                class="card project-card"
                data-id="${esc(p.id)}"
            >
                <div class="project-meta">
                    <span class="badge role-${esc(p.my_role)}">
                        ${esc(p.my_role)}
                    </span>

                    ${
                        p.archived_at
                            ? '<span class="badge is-archived">ĐÃ LƯU TRỮ</span>'
                            : ""
                    }
                </div>

                <h3>${esc(p.name)}</h3>

                <p>${esc(p.description || "Chưa có mô tả")}</p>

                <div class="project-meta">
                    <span>🕒 ${esc(p.timezone)}</span>
                    <span>👥 ${esc(p.member_count ?? 0)}</span>
                </div>

                ${
                    p.start_date || p.end_date
                        ? `
                            <div class="project-meta">
                                <span>
                                    📅 ${esc(fmtDate(p.start_date) || "—")}
                                    →
                                    ${esc(fmtDate(p.end_date) || "—")}
                                </span>
                            </div>
                        `
                        : ""
                }

                <div class="project-meta">
                    ${
                        p.my_role === "OWNER" && !p.archived_at
                            ? `
                                <button
                                    type="button"
                                    class="btn btn-small"
                                    data-act="add-member"
                                >
                                    Thêm thành viên
                                </button>
                            `
                            : ""
                    }

                    ${
                        p.my_role === "OWNER"
                            ? `
                                <button
                                    type="button"
                                    class="btn btn-small"
                                    data-act="edit"
                                >
                                    Sửa
                                </button>

                                <button
                                    type="button"
                                    class="btn btn-small ${
                                        p.archived_at ? "" : "btn-danger"
                                    }"
                                    data-act="${
                                        p.archived_at ? "restore" : "archive"
                                    }"
                                >
                                    ${
                                        p.archived_at
                                            ? "Khôi phục"
                                            : "Lưu trữ"
                                    }
                                </button>
                            `
                            : ""
                    }
                </div>
            </article>
        `).join("");

        listEl.querySelectorAll(".project-card").forEach(card => {
            const project = items.find(
                item => String(item.id) === card.dataset.id
            );

            if (!project) return;

            card.style.cursor = "pointer";
            card.tabIndex = 0;
            card.setAttribute("role", "link");

            card.setAttribute(
                "aria-label",
                "Mở bảng công việc dự án " + project.name
            );

            card.addEventListener("click", event => {
                if (
                    event.target.closest(
                        "button, a, input, select, textarea"
                    )
                ) {
                    return;
                }

                openProjectBoard(project);
            });

            card.addEventListener("keydown", event => {
                if (event.target !== card) return;

                if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {
                    event.preventDefault();
                    openProjectBoard(project);
                }
            });
        });

        listEl.querySelectorAll("[data-act]").forEach(btn => {
            btn.addEventListener("click", () => {
                const card = btn.closest("[data-id]");

                const project = items.find(
                    item => String(item.id) === card.dataset.id
                );

                if (!project) return;

                if (btn.dataset.act === "add-member") {
                    openAddMemberModal(project);
                } else if (btn.dataset.act === "edit") {
                    openForm(project);
                } else {
                    toggleArchive(project, btn.dataset.act);
                }
            });
        });
    }

    async function toggleArchive(project, action) {
        if (
            action === "archive" &&
            !confirm(
                `Lưu trữ dự án “${project.name}”? Dự án sẽ chỉ còn đọc được.`
            )
        ) {
            return;
        }

        try {
            await API.post(
                `/projects/${encodeURIComponent(project.id)}/${action}`
            );

            toast(
                action === "archive"
                    ? "Đã lưu trữ dự án"
                    : "Đã khôi phục dự án",
                "success"
            );

            await load();
        } catch (err) {
            toast(err.message || "Thao tác thất bại", "error");
        }
    }

    function openForm(project) {
        const editing = Boolean(project);

        const tzOptions = timezones().map(zone => `
            <option
                value="${esc(zone)}"
                ${
                    zone === (project?.timezone || DEFAULT_TZ)
                        ? "selected"
                        : ""
                }
            >
                ${esc(zone)}
            </option>
        `).join("");

        const modal = openModal(`
            <h2>${editing ? "Sửa dự án" : "Tạo dự án mới"}</h2>

            <form class="form-grid" novalidate>
                <label>
                    Tên dự án *
                    <input
                        name="name"
                        maxlength="150"
                        value="${esc(project?.name || "")}"
                        required
                    >
                    <span
                        class="field-error"
                        data-err="name"
                    ></span>
                </label>

                <label>
                    Mô tả
                    <textarea
                        name="description"
                        maxlength="2000"
                    >${esc(project?.description || "")}</textarea>

                    <span
                        class="field-error"
                        data-err="description"
                    ></span>
                </label>

                <div class="row2">
                    <label>
                        Ngày bắt đầu
                        <input
                            type="text"
                            name="start_date"
                            inputmode="numeric"
                            placeholder="dd/mm/yyyy"
                            maxlength="10"
                            autocomplete="off"
                            value="${esc(fmtDate(project?.start_date))}"
                        >
                        <span
                            class="field-error"
                            data-err="start_date"
                        ></span>
                    </label>

                    <label>
                        Ngày kết thúc
                        <input
                            type="text"
                            name="end_date"
                            inputmode="numeric"
                            placeholder="dd/mm/yyyy"
                            maxlength="10"
                            autocomplete="off"
                            value="${esc(fmtDate(project?.end_date))}"
                        >
                        <span
                            class="field-error"
                            data-err="end_date"
                        ></span>
                    </label>
                </div>

                <label>
                    Múi giờ ${
                        editing
                            ? "(không đổi được sau khi tạo)"
                            : ""
                    }

                    <select
                        name="timezone"
                        ${editing ? "disabled" : ""}
                    >
                        ${tzOptions}
                    </select>
                </label>

                <div class="form-banner" hidden></div>

                <div class="modal-actions">
                    <button
                        type="button"
                        class="btn"
                        data-close
                    >
                        Hủy
                    </button>

                    <button
                        type="submit"
                        class="btn btn-primary"
                    >
                        ${editing ? "Lưu" : "Tạo dự án"}
                    </button>
                </div>
            </form>
        `);

        const form = modal.el.querySelector("form");
        const banner = form.querySelector(".form-banner");

        function setErr(field, message = "") {
            const el = form.querySelector(
                `[data-err="${field}"]`
            );

            if (el) el.textContent = message;
        }

        modal.el.querySelector("[data-close]").onclick =
            modal.close;

        form.addEventListener("submit", async event => {
            event.preventDefault();

            [
                "name",
                "description",
                "start_date",
                "end_date"
            ].forEach(field => setErr(field));

            banner.hidden = true;

            const startDate = toApiDate(
                form.elements.start_date.value
            );

            const endDate = toApiDate(
                form.elements.end_date.value
            );

            const body = {
                name: form.elements.name.value.trim(),
                description:
                    form.elements.description.value.trim() || null,
                start_date: startDate.value,
                end_date: endDate.value
            };

            let invalid = false;

            if (!body.name || body.name.length > 150) {
                setErr(
                    "name",
                    "Tên dự án phải từ 1 đến 150 ký tự"
                );
                invalid = true;
            }

            if (
                body.description &&
                body.description.length > 2000
            ) {
                setErr(
                    "description",
                    "Mô tả tối đa 2000 ký tự"
                );
                invalid = true;
            }

            if (!startDate.valid) {
                setErr(
                    "start_date",
                    "Nhập ngày hợp lệ theo dd/mm/yyyy"
                );
                invalid = true;
            }

            if (!endDate.valid) {
                setErr(
                    "end_date",
                    "Nhập ngày hợp lệ theo dd/mm/yyyy"
                );
                invalid = true;
            }

            if (
                startDate.valid &&
                endDate.valid &&
                body.start_date &&
                body.end_date &&
                body.start_date > body.end_date
            ) {
                setErr(
                    "end_date",
                    "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu"
                );
                invalid = true;
            }

            if (invalid) return;

            if (!editing) {
                body.timezone = form.elements.timezone.value;
            }

            const submitBtn = form.querySelector(
                '[type="submit"]'
            );

            submitBtn.disabled = true;

            try {
                if (editing) {
                    await API.patch(
                        `/projects/${encodeURIComponent(project.id)}`,
                        body
                    );
                } else {
                    await API.post("/projects", body);
                }

                modal.close();

                toast(
                    editing
                        ? "Đã cập nhật dự án"
                        : "Đã tạo dự án",
                    "success"
                );

                await load();
            } catch (err) {
                if (err.status === 401) return;

                banner.hidden = false;
                banner.textContent =
                    err.message || "Không lưu được dự án";

                submitBtn.disabled = false;
            }
        });

        form.elements.name.focus();
    }

    newBtn.addEventListener("click", () => {
        openForm(null);
    });

    filterEl.addEventListener("change", load);

    let started = false;

    function start() {
        if (started) return;
        started = true;
        load();
    }

    if (
        window.PulseAuth &&
        window.PulseAuth.status === "authenticated"
    ) {
        start();
    }

    window.addEventListener("pulse:auth-changed", event => {
        if (event.detail?.status === "authenticated") {
            start();
        }
    });
})();
