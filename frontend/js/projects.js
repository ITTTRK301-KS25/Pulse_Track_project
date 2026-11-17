
"use strict";

(function () {
    const listEl = document.getElementById("project-list");
    const filterEl = document.getElementById("filter-status");
    const newBtn = document.getElementById("btn-new-project");

    if (!listEl || !filterEl || !newBtn) return;

    const API = window.PulseAPI;
    const DEFAULT_TZ = "Asia/Ho_Chi_Minh";

    const searchEl = document.getElementById("project-search");
    const roleEl = document.getElementById("filter-role");
    const countEl = document.getElementById("project-result-count");
    const paginationEl = document.getElementById("projects-pagination");
    const gridBtn = document.getElementById("project-view-grid");
    const listBtn = document.getElementById("project-view-list");

    let allProjects = [];
    let currentPage = 1;
    let currentView = "grid";

    const PAGE_SIZE = 6;

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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


function updateProjectStats() {
    const total = allProjects.length;

    const active = allProjects.filter(
        project => !project.archived_at
    ).length;

    const archived = total - active;

    document.getElementById(
        "project-stat-total"
    ).textContent = total;

    document.getElementById(
        "project-stat-active"
    ).textContent = active;

    document.getElementById(
        "project-stat-archived"
    ).textContent = archived;
}


    function applyProjectFilters() {
        const keyword = (searchEl?.value || "")
            .trim()
            .toLocaleLowerCase("vi");

        const status = filterEl.value;
        const role = roleEl?.value || "all";

        const isSearching = keyword.length > 0;

        const filtered = allProjects.filter(project => {
            const searchableText = [
                project.name || "",
                project.description || ""
            ].join(" ").toLocaleLowerCase("vi");

            const matchesSearch =
                !isSearching || searchableText.includes(keyword);

            // Có từ khóa: tìm trên cả dự án hoạt động và đã lưu trữ.
            // Không có từ khóa: lọc theo trạng thái đang chọn.
            const matchesStatus =
                isSearching ||
                status === "all" ||
                (status === "active" && !project.archived_at) ||
                (status === "archived" && !!project.archived_at);

            const matchesRole =
                role === "all" ||
                project.my_role === role;

            return matchesSearch && matchesStatus && matchesRole;
        });

        const totalPages = Math.max(
            1,
            Math.ceil(filtered.length / PAGE_SIZE)
        );

        currentPage = Math.max(
            1,
            Math.min(currentPage, totalPages)
        );

        const start = (currentPage - 1) * PAGE_SIZE;

        const visibleProjects = filtered.slice(
            start,
            start + PAGE_SIZE
        );

        if (countEl) {
            countEl.textContent = isSearching
                ? `Tìm thấy ${filtered.length} dự án trên tất cả trạng thái`
                : `Hiển thị ${filtered.length} / ${allProjects.length} dự án`;
        }

        render(visibleProjects);

        listEl.classList.toggle(
            "is-list-view",
            currentView === "list"
        );

        if (!paginationEl) return;

        paginationEl.hidden = totalPages <= 1;

        if (totalPages <= 1) {
            paginationEl.innerHTML = "";
            return;
        }

        paginationEl.innerHTML = `
            <span>Trang ${currentPage} / ${totalPages}</span>

            <div>
                <button
                    type="button"
                    data-page="prev"
                    ${currentPage === 1 ? "disabled" : ""}
                >
                    ← Trước
                </button>

                <button
                    type="button"
                    data-page="next"
                    ${currentPage === totalPages ? "disabled" : ""}
                >
                    Tiếp →
                </button>
            </div>
        `;

        paginationEl.querySelectorAll("[data-page]").forEach(button => {
            button.addEventListener("click", () => {
                if (button.dataset.page === "prev") {
                    currentPage--;
                } else {
                    currentPage++;
                }

                applyProjectFilters();
            });
        });
    }


    async function load() {
        listEl.innerHTML = `
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
        `;

        try {
            const response = await API.get("/projects");

            if (!Array.isArray(response?.data)) {
                throw new Error("Dữ liệu dự án không hợp lệ");
            }

            allProjects = response.data;

            updateProjectStats();
            applyProjectFilters();

        } catch (err) {
            if (err.status === 401) return;

            if (countEl) {
                countEl.textContent = "Không tải được dự án";
            }

            if (paginationEl) {
                paginationEl.hidden = true;
            }

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

        emailInput.addEventListener("input", function () {
            clearTimeout(lookupTimer);
            lookupVersion++;

            const version = lookupVersion;
            const email = emailInput.value.trim().toLowerCase();

            verifiedEmail = "";
            nameInput.value = "";
            emailError.textContent = "";
            statusEl.textContent = "";
            statusEl.className = "member-lookup-status";
            submitBtn.disabled = true;

            if (!email) return;

            if (!EMAIL_RE.test(email)) {
                emailError.textContent = "Email chưa hợp lệ";
                return;
            }

            statusEl.textContent = "Đang kiểm tra tài khoản...";
            lookupTimer = setTimeout(async () => {
                try {
                    const response = await API.get(
                        `/projects/${encodeURIComponent(project.id)}/members/lookup`,
                        { query: { email } }
                    );

                    if (
                        closed ||
                        version !== lookupVersion ||
                        emailInput.value.trim().toLowerCase() !== email
                    ) {
                        return;
                    }

                    const account = response?.data;
                    if (!account?.display_name) {
                        throw new Error("Thông tin tài khoản không hợp lệ");
                    }

                    nameInput.value = account.display_name;
                    verifiedEmail = email;
                    statusEl.textContent = "Đã tìm thấy tài khoản";
                    statusEl.classList.add("success");
                    submitBtn.disabled = false;
                } catch (err) {
                    if (closed || version !== lookupVersion) return;

                    statusEl.textContent = err.status === 404
                        ? "Không tìm thấy tài khoản với email này"
                        : "Không thể kiểm tra tài khoản";
                    statusEl.classList.add("error");
                }
            }, 500);
        });

        modal.el.querySelector("[data-close]").onclick = closeMemberModal;

        form.addEventListener("submit", async event => {
            event.preventDefault();

            banner.hidden = true;
            banner.textContent = "";

            const email = emailInput.value.trim().toLowerCase();
            const role = roleInput.value;
            const description = descriptionInput.value.trim();

            if (!email || verifiedEmail !== email) {
                banner.textContent = "Vui lòng nhập email đã được xác thực.";

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
                    <div class="empty-box upgraded-empty">
                        <strong>Không tìm thấy dự án phù hợp</strong>
                        <p>
                            Thử thay đổi từ khóa hoặc bộ lọc
                            để xem thêm dự án.
                        </p>
                    </div>
                `;
                return;
            }

            listEl.innerHTML = items.map(project => {
                const archived = Boolean(project.archived_at);
                const owner = project.my_role === "OWNER";

                const firstLetter = (project.name || "D")
                    .trim()
                    .slice(0, 1)
                    .toLocaleUpperCase("vi");

                const startDate = fmtDate(project.start_date) || "—";
                const endDate = fmtDate(project.end_date) || "—";

                return `
                    <article
                        class="card project-card upgraded-project-card"
                        data-id="${esc(project.id)}"
                    >
                        <div class="project-card-top">
                            <div class="project-avatar" aria-hidden="true">
                                ${esc(firstLetter)}
                            </div>

                            <div class="project-badges">
                                <span class="badge role-${esc(project.my_role)}">
                                    ${esc(project.my_role || "MEMBER")}
                                </span>

                                <span class="project-state ${
                                    archived ? "is-archived" : ""
                                }">
                                    ${
                                        archived
                                            ? "Đã lưu trữ"
                                            : "Đang hoạt động"
                                    }
                                </span>
                            </div>
                        </div>

                        <h3>${esc(project.name)}</h3>

                        <p class="project-description">
                            ${esc(project.description || "Chưa có mô tả dự án")}
                        </p>

                        <div class="project-facts">
                            <span>
                                👥 ${esc(project.member_count ?? 0)}
                                thành viên
                            </span>

                            <span>
                                ◷ ${esc(project.timezone || DEFAULT_TZ)}
                            </span>
                        </div>

                        <div class="project-dates">
                            ${
                                project.start_date || project.end_date
                                    ? `📅 ${esc(startDate)} – ${esc(endDate)}`
                                    : "📅 Chưa thiết lập thời gian"
                            }
                        </div>

                        <div class="project-card-actions">
                            <button
                                type="button"
                                class="btn btn-small project-open"
                                data-act="open"
                            >
                                Mở dự án ↗
                            </button>

                            ${
                                owner && !archived
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
                                owner
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
                                                archived ? "" : "btn-danger"
                                            }"
                                            data-act="${
                                                archived ? "restore" : "archive"
                                            }"
                                        >
                                            ${
                                                archived
                                                    ? "Khôi phục"
                                                    : "Lưu trữ"
                                            }
                                        </button>
                                    `
                                    : ""
                            }
                        </div>
                    </article>
                `;
            }).join("");

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

            listEl.querySelectorAll("[data-act]").forEach(button => {
                button.addEventListener("click", () => {
                    const card = button.closest("[data-id]");

                    const project = items.find(
                        item => String(item.id) === card.dataset.id
                    );

                    if (!project) return;

                    switch (button.dataset.act) {
                        case "open":
                            openProjectBoard(project);
                            break;

                        case "add-member":
                            openAddMemberModal(project);
                            break;

                        case "edit":
                            openForm(project);
                            break;

                        case "archive":
                        case "restore":
                            toggleArchive(project, button.dataset.act);
                            break;
                    }
                });
            });
        }




        async function toggleArchive(project, action) {
            const isArchiving = action === "archive";

            if (
                isArchiving &&
                !confirm(
                    `Bạn có chắc muốn lưu trữ dự án "${project.name}"?`
                )
            ) {
                return;
            }

            try {
                await API.post(
                    `/projects/${encodeURIComponent(project.id)}/${action}`
                );

                // Hiển thị danh sách tương ứng sau thao tác
                filterEl.value = isArchiving ? "archived" : "active";

                // Bỏ bộ lọc có thể khiến dự án bị ẩn
                if (searchEl) {
                    searchEl.value = "";
                }

                if (roleEl) {
                    roleEl.value = "all";
                }

                currentPage = 1;

                // Tải lại danh sách từ Backend
                await load();

                toast(
                    isArchiving
                        ? "Đã lưu trữ dự án. Đang hiển thị danh sách lưu trữ."
                        : "Đã khôi phục dự án về danh sách hoạt động.",
                    "success"
                );

            } catch (err) {
                toast(
                    err.message || "Không thể cập nhật dự án",
                    "error"
                );
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

    filterEl.addEventListener("change", () => {
        currentPage = 1;
        applyProjectFilters();
    });

    searchEl?.addEventListener("input", () => {
        currentPage = 1;
        applyProjectFilters();
    });

    roleEl?.addEventListener("change", () => {
        currentPage = 1;
        applyProjectFilters();
    });

    function setProjectView(nextView) {
        currentView = nextView;

        gridBtn?.classList.toggle(
            "is-active",
            currentView === "grid"
        );

        listBtn?.classList.toggle(
            "is-active",
            currentView === "list"
        );

        gridBtn?.setAttribute(
            "aria-pressed",
            String(currentView === "grid")
        );

        listBtn?.setAttribute(
            "aria-pressed",
            String(currentView === "list")
        );

        applyProjectFilters();
    }

    gridBtn?.addEventListener("click", () => {
        setProjectView("grid");
    });

    listBtn?.addEventListener("click", () => {
        setProjectView("list");
    });


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
