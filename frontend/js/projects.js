
"use strict";

(function () {
    const listEl = document.getElementById("project-list");
    const filterEl = document.getElementById("filter-status");
    const newBtn = document.getElementById("btn-new-project");

    if (!listEl || !filterEl || !newBtn) return;

    const API = window.PulseAPI;
    const DEFAULT_TZ = "Asia/Ho_Chi_Minh";

    const esc = (value) => String(value ?? "").replace(
        /[&<>"']/g,
        (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char])
    );

    function fmtDate(value) {
        if (!value) return "";

        const [year, month, day] = String(value).slice(0, 10).split("-");

        if (!year || !month || !day) return "";

        return `${day}/${month}/${year}`;
    }

    function toDisplayDate(value) {
        return fmtDate(value);
    }

    function toApiDate(value) {
        const text = value.trim();

        if (!text) {
            return { valid: true, value: null };
        }

        const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text);

        if (!match) {
            return { valid: false, value: null };
        }

        const day = Number(match[1]);
        const month = Number(match[2]);
        const year = Number(match[3]);

        if (year < 1 || year > 9999 || month < 1 || month > 12) {
            return { valid: false, value: null };
        }

        const leap = year % 4 === 0 &&
            (year % 100 !== 0 || year % 400 === 0);

        const days = [
            31, leap ? 29 : 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31
        ];

        if (day < 1 || day > days[month - 1]) {
            return { valid: false, value: null };
        }

        return {
            valid: true,
            value:
                `${String(year).padStart(4, "0")}-` +
                `${String(month).padStart(2, "0")}-` +
                `${String(day).padStart(2, "0")}`
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

        const close = () => {
            back.remove();
            document.removeEventListener("keydown", onKey);
        };

        const onKey = (event) => {
            if (event.key === "Escape") {
                close();
            }
        };

        back.addEventListener("mousedown", (event) => {
            if (event.target === back) {
                close();
            }
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

        const base = [
            DEFAULT_TZ,
            "Asia/Bangkok",
            "Asia/Singapore",
            "Asia/Tokyo",
            "Europe/London",
            "America/New_York",
            "UTC"
        ];

        return Array.from(new Set([...base, ...list]));
    }

    async function load() {
        listEl.innerHTML = `
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
        `;

        try {
            const res = await API.get("/projects", {
                query: {
                    status: filterEl.value
                }
            });

            const items = Array.isArray(res?.data) ? res.data : [];

            render(items);
        } catch (err) {
            if (err.status === 401) return;

            listEl.innerHTML = `
                <div class="empty-box">
                    ${esc(err.message || "Không tải được danh sách dự án")}
                    <p>
                        <button
                            class="btn btn-small"
                            id="retry-load"
                            type="button"
                        >
                            Thử lại
                        </button>
                    </p>
                </div>
            `;

            document.getElementById("retry-load").onclick = load;
        }
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

        listEl.innerHTML = items.map((p) => `
            <article class="card project-card" data-id="${esc(p.id)}">

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
                    <a
                        class="btn btn-small"
                        href="kanban.html?project=${encodeURIComponent(p.id)}"
                    >
                        Mở bảng
                    </a>

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

        listEl.querySelectorAll("[data-act]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const card = btn.closest("[data-id]");

                const project = items.find(
                    (item) => String(item.id) === card.dataset.id
                );

                if (!project) return;

                if (btn.dataset.act === "edit") {
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

        const tzOptions = timezones().map((zone) => `
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
                    <span class="field-error" data-err="name"></span>
                </label>

                <label>
                    Mô tả
                    <textarea
                        name="description"
                        maxlength="2000"
                    >${esc(project?.description || "")}</textarea>
                    <span class="field-error" data-err="description"></span>
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
                            value="${esc(toDisplayDate(project?.start_date))}"
                        >
                        <span class="field-error" data-err="start_date"></span>
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
                            value="${esc(toDisplayDate(project?.end_date))}"
                        >
                        <span class="field-error" data-err="end_date"></span>
                    </label>
                </div>

                <label>
                    Múi giờ ${
                        editing ? "(không đổi được sau khi tạo)" : ""
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

        const setErr = (field, message = "") => {
            const el = form.querySelector(`[data-err="${field}"]`);

            if (el) {
                el.textContent = message;
            }
        };

        modal.el.querySelector("[data-close]").onclick = modal.close;

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            ["name", "description", "start_date", "end_date"].forEach(
                (field) => setErr(field)
            );

            banner.hidden = true;

            const startDate = toApiDate(form.elements.start_date.value);
            const endDate = toApiDate(form.elements.end_date.value);

            const body = {
                name: form.elements.name.value.trim(),
                description: form.elements.description.value.trim() || null,
                start_date: startDate.value,
                end_date: endDate.value
            };

            let invalid = false;

            if (!body.name || body.name.length > 150) {
                setErr("name", "Tên dự án phải từ 1 đến 150 ký tự");
                invalid = true;
            }

            if (body.description && body.description.length > 2000) {
                setErr("description", "Mô tả tối đa 2000 ký tự");
                invalid = true;
            }

            if (!startDate.valid) {
                setErr("start_date", "Nhập ngày hợp lệ theo dd/mm/yyyy");
                invalid = true;
            }

            if (!endDate.valid) {
                setErr("end_date", "Nhập ngày hợp lệ theo dd/mm/yyyy");
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

            const submit = form.querySelector('[type="submit"]');
            submit.disabled = true;

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

                submit.disabled = false;
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

    window.addEventListener("pulse:auth-changed", (event) => {
        if (event.detail?.status === "authenticated") {
            start();
        }
    });
})();
