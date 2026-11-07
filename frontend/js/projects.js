"use strict";
// F04: danh sách dự án + modal tạo mới (timezone mặc định Asia/Ho_Chi_Minh).
// Kèm nút Sửa / Lưu trữ / Khôi phục cho OWNER (dùng API của B08).
(function () {
    const listEl = document.getElementById("project-list");
    const filterEl = document.getElementById("filter-status");
    const newBtn = document.getElementById("btn-new-project");
    if (!listEl) return;

    const API = window.PulseAPI;
    const DEFAULT_TZ = "Asia/Ho_Chi_Minh";

    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const fmtDate = (d) => { if (!d) return ""; const [y, m, day] = String(d).slice(0, 10).split("-"); return `${day}/${m}/${y}`; };

    function toast(text, type) {
        let wrap = document.querySelector(".toast-wrap");
        if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; wrap.setAttribute("aria-live", "polite"); document.body.appendChild(wrap); }
        const el = document.createElement("div");
        el.className = "toast " + (type || ""); el.textContent = text;
        wrap.appendChild(el); setTimeout(() => el.remove(), 4500);
    }

    function openModal(html) {
        const back = document.createElement("div");
        back.className = "modal-backdrop";
        back.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${html}</div>`;
        const close = () => { back.remove(); document.removeEventListener("keydown", onKey); };
        const onKey = (e) => { if (e.key === "Escape") close(); };
        back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
        document.addEventListener("keydown", onKey);
        document.body.appendChild(back);
        return { el: back.firstElementChild, close };
    }

    function timezones() {
        let list = [];
        try { list = Intl.supportedValuesOf("timeZone"); } catch (e) { /* trình duyệt cũ */ }
        const base = [DEFAULT_TZ, "Asia/Bangkok", "Asia/Singapore", "Asia/Tokyo", "Europe/London", "America/New_York", "UTC"];
        return Array.from(new Set([...base, ...list]));
    }

    // ---------- tải và hiển thị danh sách ----------
    async function load() {
        listEl.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
        try {
            const res = await API.get("/projects", { query: { status: filterEl.value } });
            render(Array.isArray(res?.data) ? res.data : []);
        } catch (err) {
            if (err.status === 401) return; // router.js tự chuyển về login
            listEl.innerHTML = `<div class="empty-box">${esc(err.message || "Không tải được danh sách dự án")}
                <p><button class="btn btn-small" id="retry-load" type="button">Thử lại</button></p></div>`;
            document.getElementById("retry-load").onclick = load;
        }
    }

    function render(items) {
        if (!items.length) {
            listEl.innerHTML = `<div class="empty-box">${filterEl.value === "archived" ? "Chưa có dự án nào được lưu trữ." : "Chưa có dự án nào. Bấm “+ Tạo dự án” để bắt đầu."}</div>`;
            return;
        }
        listEl.innerHTML = items.map((p) => `
            <article class="card project-card" data-id="${esc(p.id)}">
                <div class="project-meta"><span class="badge role-${esc(p.my_role)}">${esc(p.my_role)}</span>${p.archived_at ? '<span class="badge is-archived">ĐÃ LƯU TRỮ</span>' : ""}</div>
                <h3>${esc(p.name)}</h3>
                <p>${esc(p.description || "Chưa có mô tả")}</p>
                <div class="project-meta"><span>🕒 ${esc(p.timezone)}</span>${p.member_count ? `<span>👥 ${p.member_count}</span>` : ""}
                    ${p.start_date || p.end_date ? `<span>${esc(fmtDate(p.start_date))} → ${esc(fmtDate(p.end_date))}</span>` : ""}</div>
                <div class="project-meta">
                    <a class="btn btn-small" href="kanban.html?project=${encodeURIComponent(p.id)}">Mở bảng</a>
                    ${p.my_role === "OWNER" ? `<button type="button" class="btn btn-small" data-act="edit">Sửa</button>
                    <button type="button" class="btn btn-small ${p.archived_at ? "" : "btn-danger"}" data-act="${p.archived_at ? "restore" : "archive"}">${p.archived_at ? "Khôi phục" : "Lưu trữ"}</button>` : ""}
                </div>
            </article>`).join("");
        listEl.querySelectorAll("[data-act]").forEach((btn) => btn.addEventListener("click", () => {
            const p = items.find((x) => x.id === btn.closest("[data-id]").dataset.id);
            if (btn.dataset.act === "edit") openForm(p); else toggleArchive(p, btn.dataset.act);
        }));
    }

    async function toggleArchive(p, act) {
        if (act === "archive" && !confirm(`Lưu trữ dự án “${p.name}”? Dự án sẽ chỉ còn đọc được.`)) return;
        try {
            await API.post(`/projects/${encodeURIComponent(p.id)}/${act}`);
            toast(act === "archive" ? "Đã lưu trữ dự án" : "Đã khôi phục dự án", "success");
            load();
        } catch (err) { toast(err.message || "Thao tác thất bại", "error"); }
    }

    // ---------- modal tạo / sửa ----------
    function openForm(project) {
        const editing = Boolean(project);
        const tzOptions = timezones().map((z) =>
            `<option value="${esc(z)}" ${z === (project?.timezone || DEFAULT_TZ) ? "selected" : ""}>${esc(z)}</option>`).join("");
        const m = openModal(`<h2>${editing ? "Sửa dự án" : "Tạo dự án mới"}</h2>
            <form class="form-grid" novalidate>
                <label>Tên dự án *<input name="name" maxlength="150" value="${esc(project?.name || "")}" required><span class="field-error" data-err="name"></span></label>
                <label>Mô tả<textarea name="description" maxlength="2000">${esc(project?.description || "")}</textarea><span class="field-error" data-err="description"></span></label>
                <div class="row2">
                    <label>Ngày bắt đầu<input type="date" name="start_date" value="${esc(project?.start_date || "")}"></label>
                    <label>Ngày kết thúc<input type="date" name="end_date" value="${esc(project?.end_date || "")}"><span class="field-error" data-err="end_date"></span></label>
                </div>
                <label>Múi giờ ${editing ? "(không đổi được sau khi tạo)" : ""}<select name="timezone" ${editing ? "disabled" : ""}>${tzOptions}</select></label>
                <div class="form-banner" hidden></div>
                <div class="modal-actions"><button type="button" class="btn" data-close>Hủy</button>
                    <button class="btn btn-primary" type="submit">${editing ? "Lưu" : "Tạo dự án"}</button></div>
            </form>`);
        const form = m.el.querySelector("form");
        const banner = form.querySelector(".form-banner");
        const setErr = (k, t) => { const e = form.querySelector(`[data-err="${k}"]`); if (e) e.textContent = t || ""; };
        m.el.querySelector("[data-close]").onclick = m.close;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            ["name", "description", "end_date"].forEach((k) => setErr(k)); banner.hidden = true;
            const body = {
                name: form.elements.name.value.trim(),
                description: form.elements.description.value.trim() || null,
                start_date: form.elements.start_date.value || null,
                end_date: form.elements.end_date.value || null
            };
            let bad = false;
            if (!body.name || body.name.length > 150) { setErr("name", "Tên dự án phải từ 1 đến 150 ký tự"); bad = true; }
            if (body.description && body.description.length > 2000) { setErr("description", "Mô tả tối đa 2000 ký tự"); bad = true; }
            if (body.start_date && body.end_date && body.start_date > body.end_date) { setErr("end_date", "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu"); bad = true; }
            if (bad) return;
            if (!editing) body.timezone = form.elements.timezone.value;

            const submit = form.querySelector("[type=submit]"); submit.disabled = true;
            try {
                if (editing) await API.patch(`/projects/${encodeURIComponent(project.id)}`, body);
                else await API.post("/projects", body);
                m.close(); toast(editing ? "Đã cập nhật dự án" : "Đã tạo dự án", "success"); load();
            } catch (err) {
                if (err.status === 401) return;
                banner.hidden = false; banner.textContent = err.message || "Không lưu được dự án";
                submit.disabled = false;
            }
        });
        form.elements.name.focus();
    }

    newBtn.addEventListener("click", () => openForm(null));
    filterEl.addEventListener("change", load);

    // Chỉ tải dữ liệu sau khi router.js xác nhận đã đăng nhập (GET /auth/me).
    let started = false;
    function start() { if (started) return; started = true; load(); }
    if (window.PulseAuth && window.PulseAuth.status === "authenticated") start();
    window.addEventListener("pulse:auth-changed", (e) => { if (e.detail?.status === "authenticated") start(); });
})();
