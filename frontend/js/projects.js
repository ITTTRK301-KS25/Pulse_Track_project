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

    const deletingProjects = new Set();
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
        const previousFocus = document.activeElement;

        let locked = false;

        back.className = "modal-backdrop";

        back.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true">
                ${html}
            </div>
        `;

        const onKey = event => {
            if (event.key === "Escape" && !locked) {
                close();
            }
        };

        function close() {
            if (locked) return;

            back.remove();

            document.removeEventListener("keydown", onKey);

            if (previousFocus?.isConnected) {
                previousFocus.focus();
            }
        }

        back.addEventListener("mousedown", event => {
            if (event.target === back && !locked) {
                close();
            }
        });

        document.addEventListener("keydown", onKey);
        document.body.appendChild(back);

        return {
            el: back.firstElementChild,
            close,
            setLocked(value) {
                locked = Boolean(value);
            }
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

        const totalEl = document.getElementById("project-stat-total");
        const activeEl = document.getElementById("project-stat-active");
        const archivedEl = document.getElementById("project-stat-archived");

        if (totalEl) totalEl.textContent = total;
        if (activeEl) activeEl.textContent = active;
        if (archivedEl) archivedEl.textContent = archived;
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

        paginationEl.querySelectorAll("[data-page]")
            .forEach(button => {
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
            const [activeResponse, archivedResponse] =
                await Promise.all([
                    API.get("/projects?status=active"),
                    API.get("/projects?status=archived")
                ]);

            const activeData =
                activeResponse?.data ?? activeResponse;

            const archivedData =
                archivedResponse?.data ?? archivedResponse;

            const activeProjects = Array.isArray(activeData)
                ? activeData
                : activeData?.items ?? activeData?.projects ?? [];

            const archivedProjects = Array.isArray(archivedData)
                ? archivedData
                : archivedData?.items ?? archivedData?.projects ?? [];

            allProjects = [
                ...new Map(
                    [...activeProjects, ...archivedProjects].map(
                        project => [String(project.id), project]
                    )
                ).values()
            ];

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

        const emailError = form.querySelector('[data-err="email"]');

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
                        !modal.el.isConnected ||
                        version !== lookupVersion ||
                        emailInput.value.trim().toLowerCase() !== email
                    ) {
                        return;
                    }

                    const account = response?.data;

                    if (!account?.display_name) {
                        throw new Error(
                            "Thông tin tài khoản không hợp lệ"
                        );
                    }

                    nameInput.value = account.display_name;
                    verifiedEmail = email;

                    statusEl.textContent =
                        "Đã tìm thấy tài khoản";

                    statusEl.classList.add("success");
                    submitBtn.disabled = false;

                } catch (err) {
                    if (
                        closed ||
                        !modal.el.isConnected ||
                        version !== lookupVersion
                    ) return;

                    statusEl.textContent = err.status === 404
                        ? "Không tìm thấy tài khoản với email này"
                        : "Không thể kiểm tra tài khoản";

                    statusEl.classList.add("error");
                }
            }, 500);
        });

        modal.el.querySelector("[data-close]").onclick =
            closeMemberModal;

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

                if (description) {
                    try {
                        localStorage.setItem(
                            `pulse_member_description_${project.id}_${email}`,
                            description
                        );
                    } catch (error) {
                        console.warn("Không lưu được mô tả chức vụ.");
                    }
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
            const deleting = deletingProjects.has(String(project.id));

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
                            ${deleting ? "disabled" : ""}
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
                                        ${deleting ? "disabled" : ""}
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
                                        ${deleting ? "disabled" : ""}
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

                        ${
                            owner && archived
                                ? `
                                    <button
                                        type="button"
                                        class="btn btn-small btn-danger"
                                        data-act="delete"
                                        ${deleting ? "disabled" : ""}
                                    >
                                        ${
                                            deleting
                                                ? "Đang xóa..."
                                                : "Xóa dự án"
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
                if (deletingProjects.has(String(project.id))) return;

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

                if (deletingProjects.has(String(project.id))) return;

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
            button.addEventListener("click", event => {
                event.preventDefault();
                event.stopPropagation();

                const card = button.closest("[data-id]");

                if (!card) return;

                const project = items.find(
                    item => String(item.id) === card.dataset.id
                );

                if (!project) return;

                if (deletingProjects.has(String(project.id))) return;

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

                    case "delete":
                        openDeleteModal(project);
                        break;
                }
            });
        });
    }

    function openDeleteModal(project) {
        if (!project || project.id == null) return;

        if (project.my_role !== "OWNER") {
            toast("Chỉ OWNER mới được xóa dự án.", "error");
            return;
        }

        if (!project.archived_at) {
            toast("Phải lưu trữ dự án trước khi xóa.", "error");
            return;
        }

        const projectId = String(project.id);

        if (deletingProjects.has(projectId)) return;

        const firstLetter = (project.name || "D")
            .trim()
            .charAt(0)
            .toLocaleUpperCase("vi") || "D";

        const modal = openModal(`
            <div class="delete-modal-header">
                <div class="delete-modal-icon">
                    <svg
                        width="26"
                        height="26"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        aria-hidden="true"
                    >
                        <path d="M3 6h18"/>
                        <path d="M8 6V4h8v2"/>
                        <path d="M19 6l-1 14H6L5 6"/>
                        <path d="M10 10v6M14 10v6"/>
                    </svg>
                </div>

                <button
                    type="button"
                    class="delete-modal-close"
                    data-dismiss
                    aria-label="Đóng"
                >
                    <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        aria-hidden="true"
                    >
                        <path d="M6 6l12 12M18 6L6 18"/>
                    </svg>
                </button>
            </div>

            <h2
                class="delete-modal-title"
                id="delete-project-title"
            >
                Xóa vĩnh viễn dự án
            </h2>

            <p
                class="delete-modal-subtitle"
                id="delete-project-subtitle"
            >
                Vui lòng xác nhận dự án bạn muốn xóa khỏi hệ thống.
            </p>

            <form class="delete-project-form" novalidate>
                <div class="delete-project-preview">
                    <div class="delete-project-avatar">
                        ${esc(firstLetter)}
                    </div>

                    <div class="delete-project-info">
                        <strong>${esc(project.name)}</strong>

                        <span>
                            Đã lưu trữ · OWNER
                        </span>
                    </div>

                    <div class="delete-project-verified">
                        <svg
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.7"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            aria-hidden="true"
                        >
                            <circle cx="12" cy="12" r="9"/>
                            <path d="m8 12 3 3 5-6"/>
                        </svg>
                    </div>
                </div>

                <div class="delete-project-details">
                    <strong>Dữ liệu sẽ bị xóa bao gồm</strong>

                    <div class="delete-detail-item">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.7"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            aria-hidden="true"
                        >
                            <rect x="4" y="3" width="16" height="18" rx="2"/>
                            <path d="m7 9 2 2 4-4M7 16h10"/>
                        </svg>

                        <span>Công việc và công việc con</span>
                    </div>

                    <div class="delete-detail-item">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.7"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            aria-hidden="true"
                        >
                            <circle cx="9" cy="7" r="3"/>
                            <path d="M3 21v-3a6 6 0 0 1 12 0v3"/>
                            <path d="M16 4a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v2"/>
                        </svg>

                        <span>Thành viên và phân quyền</span>
                    </div>

                    <div class="delete-detail-item">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.7"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            aria-hidden="true"
                        >
                            <path d="M21 11a8 8 0 0 1-8 8H4l2-5a8 8 0 1 1 15-3Z"/>
                        </svg>

                        <span>Bình luận và dữ liệu liên quan</span>
                    </div>
                </div>

                <div class="delete-project-warning">
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        aria-hidden="true"
                    >
                        <circle cx="12" cy="12" r="9"/>
                        <path d="M12 7v6M12 16v1"/>
                    </svg>

                    <span>
                        Hành động này không thể hoàn tác.
                    </span>
                </div>

                <div
                    class="form-banner delete-error-banner"
                    role="alert"
                    hidden
                ></div>

                <div class="delete-modal-actions">
                    <button
                        type="button"
                        class="delete-cancel-btn"
                        data-close
                    >
                        Hủy bỏ
                    </button>

                    <button
                        type="submit"
                        class="delete-confirm-btn"
                    >
                        <svg
                            width="17"
                            height="17"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            aria-hidden="true"
                        >
                            <path d="M3 6h18M8 6V4h8v2"/>
                            <path d="M19 6l-1 14H6L5 6"/>
                            <path d="M10 10v6M14 10v6"/>
                        </svg>

                        <span data-delete-label>
                            Xóa vĩnh viễn
                        </span>
                    </button>
                </div>
            </form>
        `);

        modal.el.classList.add("delete-project-modal");

        modal.el.setAttribute(
            "aria-labelledby",
            "delete-project-title"
        );

        modal.el.setAttribute(
            "aria-describedby",
            "delete-project-subtitle"
        );

        const form = modal.el.querySelector("form");
        const cancelBtn = form.querySelector("[data-close]");
        const dismissBtn = modal.el.querySelector("[data-dismiss]");
        const submitBtn = form.querySelector('button[type="submit"]');
        const submitLabel = submitBtn.querySelector("[data-delete-label]");
        const banner = form.querySelector(".form-banner");

        cancelBtn.onclick = modal.close;
        dismissBtn.onclick = modal.close;

        function setLoading(loading) {
            modal.setLocked(loading);

            submitBtn.disabled = loading;
            cancelBtn.disabled = loading;
            dismissBtn.disabled = loading;

            submitBtn.classList.toggle("is-loading", loading);

            submitLabel.textContent = loading
                ? "Đang xóa..."
                : "Xóa vĩnh viễn";

            form.setAttribute("aria-busy", String(loading));
        }

        function showError(message) {
            banner.textContent = message;
            banner.hidden = false;
        }

        form.addEventListener("submit", async event => {
            event.preventDefault();

            if (deletingProjects.has(projectId)) return;

            banner.hidden = true;
            banner.textContent = "";

            const latestProject = allProjects.find(
                item => String(item.id) === projectId
            );

            if (!latestProject) {
                showError("Dự án không còn tồn tại.");
                return;
            }

            if (latestProject.my_role !== "OWNER") {
                showError("Chỉ OWNER mới được xóa dự án.");
                return;
            }

            if (!latestProject.archived_at) {
                showError("Phải lưu trữ dự án trước khi xóa.");
                return;
            }

            deletingProjects.add(projectId);

            setLoading(true);
            applyProjectFilters();

            try {
                await API.delete(
                    `/projects/${encodeURIComponent(project.id)}`
                );

            } catch (err) {
                deletingProjects.delete(projectId);

                setLoading(false);

                showError(
                    err.message || "Không thể xóa dự án."
                );

                applyProjectFilters();

                return;
            }

            deletingProjects.delete(projectId);

            allProjects = allProjects.filter(
                item => String(item.id) !== projectId
            );

            try {
                if (
                    sessionStorage.getItem("selectedProjectId")
                    === projectId
                ) {
                    sessionStorage.removeItem("selectedProjectId");
                    sessionStorage.removeItem("selectedProjectName");
                }

                const prefix =
                    `pulse_member_description_${projectId}_`;

                const keys = [];

                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);

                    if (key && key.startsWith(prefix)) {
                        keys.push(key);
                    }
                }

                keys.forEach(key => {
                    localStorage.removeItem(key);
                });

            } catch (error) {
                console.warn(
                    "Không thể dọn dữ liệu lưu cục bộ."
                );
            }

            setLoading(false);
            modal.close();

            updateProjectStats();
            applyProjectFilters();

            toast("Xóa dự án thành công.", "success");

            await load();
        });

        cancelBtn.focus();
    }

    async function toggleArchive(project, action) {
        if (!project || project.id == null) return;
        if (!["archive", "restore"].includes(action)) return;

        if (project.my_role !== "OWNER") {
            toast("Chỉ OWNER mới được thực hiện thao tác này.", "error");
            return;
        }

        const projectId = String(project.id);

        if (deletingProjects.has(projectId)) return;

        const isArchiving = action === "archive";

        const title = isArchiving
            ? "Lưu trữ dự án"
            : "Khôi phục dự án";

        const subtitle = isArchiving
            ? "Chuyển dự án khỏi danh sách đang hoạt động."
            : "Đưa dự án trở lại danh sách đang hoạt động.";

        const firstLetter = (project.name || "D")
            .trim()
            .charAt(0)
            .toLocaleUpperCase("vi") || "D";

        function svg(content) {
            return `
                <svg viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true">
                    ${content}
                </svg>
            `;
        }

        const archiveIcon = svg(`
            <rect x="3" y="4" width="18" height="5" rx="1"/>
            <path d="M5 9v11h14V9M10 13h4"/>
        `);

        const restoreIcon = svg(`
            <path d="M3 12a9 9 0 1 1 3 6.7"/>
            <path d="M3 4v8h8"/>
        `);

        const shieldIcon = svg(`
            <path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z"/>
            <path d="m9 12 2 2 4-4"/>
        `);

        const checkIcon = svg(`
            <circle cx="12" cy="12" r="9"/>
            <path d="m8 12 3 3 5-6"/>
        `);

        const closeIcon = svg(`
            <path d="M6 6l12 12M18 6L6 18"/>
        `);

        const actionIcon = isArchiving
            ? archiveIcon
            : restoreIcon;

        const modal = openModal(`
            <div class="delete-modal-header">

                <div class="delete-modal-icon">
                    ${actionIcon}
                </div>

                <button
                    type="button"
                    class="delete-modal-close"
                    data-dismiss
                    aria-label="Đóng"
                >
                    ${closeIcon}
                </button>

            </div>

            <h2
                class="delete-modal-title"
                id="project-status-title"
            >
                ${title}
            </h2>

            <p
                class="delete-modal-subtitle"
                id="project-status-subtitle"
            >
                ${subtitle}
            </p>

            <form class="delete-project-form" novalidate>

                <div class="delete-project-preview">

                    <div class="delete-project-avatar">
                        ${esc(firstLetter)}
                    </div>

                    <div class="delete-project-info">

                        <strong>
                            ${esc(project.name)}
                        </strong>

                        <span>OWNER · Chủ dự án</span>

                    </div>

                    <span class="project-modal-status ${
                        isArchiving
                            ? "status-active"
                            : "status-archived"
                    }">
                        ${
                            isArchiving
                                ? "Đang hoạt động"
                                : "Đã lưu trữ"
                        }
                    </span>

                </div>

                <div class="delete-project-details">

                    <strong>
                        ${
                            isArchiving
                                ? "Sau khi lưu trữ"
                                : "Sau khi khôi phục"
                        }
                    </strong>

                    <div class="delete-detail-item">

                        ${isArchiving ? archiveIcon : checkIcon}

                        <span>
                            ${
                                isArchiving
                                    ? "Chuyển vào danh sách dự án đã lưu trữ."
                                    : "Khôi phục trạng thái hoạt động."
                            }
                        </span>

                    </div>

                    <div class="delete-detail-item">

                        ${shieldIcon}

                        <span>
                            Toàn bộ dữ liệu và thành viên được giữ nguyên.
                        </span>

                    </div>

                    <div class="delete-detail-item">

                        ${isArchiving ? restoreIcon : archiveIcon}

                        <span>
                            ${
                                isArchiving
                                    ? "Có thể khôi phục dự án khi cần."
                                    : "Có thể lưu trữ lại dự án khi cần."
                            }
                        </span>

                    </div>

                </div>

                <div class="project-status-note">

                    ${checkIcon}

                    <span>
                        Thao tác này không làm mất dữ liệu dự án.
                    </span>

                </div>

                <div
                    class="form-banner delete-error-banner"
                    role="alert"
                    hidden
                ></div>

                <div class="delete-modal-actions">

                    <button
                        type="button"
                        class="delete-cancel-btn"
                        data-close
                    >
                        Hủy bỏ
                    </button>

                    <button
                        type="submit"
                        class="delete-confirm-btn"
                    >
                        ${actionIcon}

                        <span data-action-label>
                            ${title}
                        </span>

                    </button>

                </div>

            </form>
        `);

        modal.el.classList.add(
            "delete-project-modal",
            "project-status-modal",
            isArchiving ? "archive-modal" : "restore-modal"
        );

        modal.el.setAttribute(
            "aria-labelledby",
            "project-status-title"
        );

        modal.el.setAttribute(
            "aria-describedby",
            "project-status-subtitle"
        );

        const form = modal.el.querySelector("form");

        const cancelBtn = form.querySelector("[data-close]");

        const dismissBtn = modal.el.querySelector("[data-dismiss]");

        const submitBtn = form.querySelector(
            'button[type="submit"]'
        );

        const submitLabel = submitBtn.querySelector(
            "[data-action-label]"
        );

        const banner = form.querySelector(".form-banner");

        let processing = false;

        cancelBtn.onclick = modal.close;
        dismissBtn.onclick = modal.close;

        function setLoading(loading) {
            processing = loading;

            modal.setLocked(loading);

            cancelBtn.disabled = loading;
            dismissBtn.disabled = loading;
            submitBtn.disabled = loading;

            submitBtn.classList.toggle(
                "is-loading",
                loading
            );

            submitLabel.textContent = loading
                ? isArchiving
                    ? "Đang lưu trữ..."
                    : "Đang khôi phục..."
                : title;

            form.setAttribute(
                "aria-busy",
                String(loading)
            );
        }

        function showError(message) {
            banner.textContent = message;
            banner.hidden = false;
        }

        form.addEventListener("submit", async event => {
            event.preventDefault();
            event.stopPropagation();

            if (processing) return;

            banner.hidden = true;
            banner.textContent = "";

            const latestProject = allProjects.find(
                item => String(item.id) === projectId
            );

            if (!latestProject) {
                showError("Dự án không còn tồn tại.");
                return;
            }

            if (latestProject.my_role !== "OWNER") {
                showError(
                    "Bạn không có quyền thực hiện thao tác này."
                );

                return;
            }

            if (isArchiving && latestProject.archived_at) {
                showError("Dự án đã được lưu trữ.");
                return;
            }

            if (!isArchiving && !latestProject.archived_at) {
                showError("Dự án đang hoạt động.");
                return;
            }

            if (deletingProjects.has(projectId)) {
                showError("Dự án đang được xử lý.");
                return;
            }

            setLoading(true);

            try {
                await API.post(
                    `/projects/${encodeURIComponent(project.id)}/${action}`
                );

            } catch (err) {
                setLoading(false);

                showError(
                    err.message ||
                    "Không thể cập nhật trạng thái dự án."
                );

                return;
            }

            setLoading(false);

            modal.close();

            toast(
                isArchiving
                    ? "Lưu trữ dự án thành công."
                    : "Khôi phục dự án thành công.",
                "success"
            );

            await load();
        });

        cancelBtn.focus();
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
                            name="start_date"
                            type="text"
                            placeholder="dd/mm/yyyy"
                            maxlength="10"
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
                            name="end_date"
                            type="text"
                            placeholder="dd/mm/yyyy"
                            maxlength="10"
                            value="${esc(fmtDate(project?.end_date))}"
                        >

                        <span
                            class="field-error"
                            data-err="end_date"
                        ></span>
                    </label>
                </div>

                <label>
                    Múi giờ

                    <select
                        name="timezone"
                        ${editing ? "disabled" : ""}
                    >
                        ${tzOptions}
                    </select>
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
                    >
                        ${editing ? "Lưu thay đổi" : "Tạo dự án"}
                    </button>
                </div>
            </form>
        `);

        const form = modal.el.querySelector("form");
        const banner = form.querySelector(".form-banner");

        const submitBtn = form.querySelector(
            'button[type="submit"]'
        );

        modal.el.querySelector("[data-close]").onclick =
            modal.close;

        function setError(field, message) {
            const errorEl = form.querySelector(
                `[data-err="${field}"]`
            );

            if (errorEl) {
                errorEl.textContent = message;
            }
        }

        form.addEventListener("submit", async event => {
            event.preventDefault();

            banner.hidden = true;
            banner.textContent = "";

            form.querySelectorAll(".field-error").forEach(el => {
                el.textContent = "";
            });

            const name = form.elements.name.value.trim();

            const description =
                form.elements.description.value.trim();

            const startDate = toApiDate(
                form.elements.start_date.value
            );

            const endDate = toApiDate(
                form.elements.end_date.value
            );

            let valid = true;

            if (!name) {
                setError("name", "Vui lòng nhập tên dự án.");
                valid = false;
            } else if (name.length > 150) {
                setError(
                    "name",
                    "Tên dự án không được vượt quá 150 ký tự."
                );

                valid = false;
            }

            if (description.length > 2000) {
                setError(
                    "description",
                    "Mô tả không được vượt quá 2000 ký tự."
                );

                valid = false;
            }

            if (!startDate.valid) {
                setError(
                    "start_date",
                    "Ngày bắt đầu không hợp lệ."
                );

                valid = false;
            }

            if (!endDate.valid) {
                setError(
                    "end_date",
                    "Ngày kết thúc không hợp lệ."
                );

                valid = false;
            }

            if (
                startDate.valid &&
                endDate.valid &&
                startDate.value &&
                endDate.value &&
                endDate.value < startDate.value
            ) {
                setError(
                    "end_date",
                    "Ngày kết thúc không được trước ngày bắt đầu."
                );

                valid = false;
            }

            if (!valid) return;

            const body = {
                name,
                description: description || null,
                start_date: startDate.value,
                end_date: endDate.value
            };

            if (!editing) {
                body.timezone =
                    form.elements.timezone.value || DEFAULT_TZ;
            }

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