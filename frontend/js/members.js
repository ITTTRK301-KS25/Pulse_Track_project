"use strict";
// F05: quản lý thành viên dự án — danh sách, badge vai trò, thêm / đổi vai trò / xóa (chỉ OWNER).
// Dùng API B09 (GET, POST /projects/{id}/members) và B10 (PATCH, DELETE /projects/{id}/members/{user_id}).
(function () {
    const body = document.getElementById("members-body");
    if (!body) return;

    const API = window.PulseAPI;
    const projectId = new URLSearchParams(location.search).get("project");
    const banner = document.getElementById("members-banner");
    const addBox = document.getElementById("add-member-box");
    const addForm = document.getElementById("add-member-form");
    const titleEl = document.getElementById("members-title");
    const subEl = document.getElementById("members-subtitle");
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const ROLES = ["OWNER", "MEMBER", "VIEWER"];

    let project = null;
    let members = [];

    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const fmt = (iso) => { if (!iso) return ""; const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString("vi-VN"); };
    let selfId = null; // router.js chỉ lưu user cho trang riêng tư; nếu thiếu thì tự hỏi GET /auth/me
    const meId = () => window.PulseCurrentUser?.id || window.PulseAuth?.user?.id || selfId;

    function toast(text, type) {
        let wrap = document.querySelector(".toast-wrap");
        if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; wrap.setAttribute("aria-live", "polite"); document.body.appendChild(wrap); }
        const el = document.createElement("div");
        el.className = "toast " + (type || ""); el.textContent = text;
        wrap.appendChild(el); setTimeout(() => el.remove(), 4500);
    }
    function showBanner(text) { banner.hidden = !text; banner.textContent = text || ""; }
    function setFieldError(text) { addForm.querySelector('[data-err="email"]').textContent = text || ""; }

    const isOwner = () => project?.my_role === "OWNER";
    const writable = () => isOwner() && !project?.archived_at;

    // ---------- tải dữ liệu ----------
    async function load() {
        if (!projectId) { subEl.textContent = ""; showBanner("Thiếu mã dự án. Hãy mở trang này từ danh sách dự án."); body.innerHTML = ""; return; }
        body.innerHTML = '<tr><td colspan="5" class="members-empty">Đang tải...</td></tr>';
        try {
            const [p, m, me] = await Promise.all([
                API.get(`/projects/${encodeURIComponent(projectId)}`),
                API.get(`/projects/${encodeURIComponent(projectId)}/members`),
                meId() ? Promise.resolve(null) : API.get("/auth/me")
            ]);
            if (me?.data?.id) selfId = me.data.id;
            project = p?.data; members = Array.isArray(m?.data) ? m.data : [];
            render();
        } catch (err) {
            if (err.status === 401) return;
            body.innerHTML = "";
            subEl.textContent = "";
            showBanner(err.status === 403 ? "Bạn không thuộc dự án này hoặc dự án không tồn tại." : (err.message || "Không tải được danh sách thành viên."));
        }
    }

    // ---------- hiển thị ----------
    function render() {
        titleEl.textContent = `Thành viên — ${project.name}`;
        subEl.textContent = project.archived_at
            ? "Dự án đã lưu trữ: chỉ xem, không thể thay đổi thành viên."
            : isOwner() ? "Bạn là OWNER: có thể thêm, đổi vai trò và xóa thành viên." : `Vai trò của bạn: ${project.my_role} (chỉ xem).`;
        showBanner("");
        addBox.hidden = !writable();

        if (!members.length) { body.innerHTML = '<tr><td colspan="5" class="members-empty">Chưa có thành viên.</td></tr>'; return; }
        const me = meId();
        body.innerHTML = members.map((m) => `
            <tr data-uid="${esc(m.user_id)}">
                <td><span class="members-name">${esc(m.display_name)}</span>${m.user_id === me ? '<span class="members-you">(Bạn)</span>' : ""}</td>
                <td>${esc(m.email)}</td>
                <td>${writable()
                    ? `<select data-role aria-label="Vai trò của ${esc(m.display_name)}">${ROLES.map((r) => `<option value="${r}" ${r === m.role ? "selected" : ""}>${r}</option>`).join("")}</select>`
                    : `<span class="badge role-${esc(m.role)}">${esc(m.role)}</span>`}</td>
                <td>${esc(fmt(m.joined_at))}</td>
                <td class="members-actions">${writable() ? '<button type="button" class="btn btn-small btn-danger" data-remove>Xóa</button>' : ""}</td>
            </tr>`).join("");

        body.querySelectorAll("[data-role]").forEach((sel) => sel.addEventListener("change", () => changeRole(sel)));
        body.querySelectorAll("[data-remove]").forEach((btn) => btn.addEventListener("click", () => removeMember(btn)));
    }

    // ---------- thao tác ----------
    async function changeRole(sel) {
        const uid = sel.closest("tr").dataset.uid;
        const current = members.find((x) => x.user_id === uid);
        const next = sel.value;
        sel.disabled = true;
        try {
            await API.patch(`/projects/${encodeURIComponent(projectId)}/members/${encodeURIComponent(uid)}`, { role: next });
            toast("Đã đổi vai trò", "success");
            await load();                     // vai trò của chính mình có thể đã đổi => tải lại quyền
        } catch (err) {
            if (err.status === 401) return;
            sel.value = current.role; sel.disabled = false;
            toast(err.message || "Không đổi được vai trò", "error");
        }
    }

    async function removeMember(btn) {
        const uid = btn.closest("tr").dataset.uid;
        const m = members.find((x) => x.user_id === uid);
        if (!confirm(`Xóa “${m.display_name}” khỏi dự án?`)) return;
        btn.disabled = true;
        try {
            await API.delete(`/projects/${encodeURIComponent(projectId)}/members/${encodeURIComponent(uid)}`);
            toast("Đã xóa thành viên", "success");
            if (uid === meId()) { location.replace("projects.html"); return; }
            await load();
        } catch (err) {
            if (err.status === 401) return;
            btn.disabled = false;
            toast(err.message || "Không xóa được thành viên", "error");
        }
    }

    addForm.addEventListener("submit", async (e) => {
        e.preventDefault(); setFieldError("");
        const email = addForm.elements.email.value.trim().toLowerCase();
        const role = addForm.elements.role.value;
        if (!EMAIL_RE.test(email)) { setFieldError("Email không hợp lệ"); return; }
        const btn = addForm.querySelector("[type=submit]"); btn.disabled = true;
        try {
            await API.post(`/projects/${encodeURIComponent(projectId)}/members`, { email, role });
            addForm.reset(); toast("Đã thêm thành viên", "success");
            await load();
        } catch (err) {
            if (err.status === 401) return;
            if (err.status === 404 || err.status === 409 || err.status === 422) setFieldError(err.message);
            else toast(err.message || "Không thêm được thành viên", "error");
        } finally { btn.disabled = false; }
    });

    // Chỉ tải sau khi router.js xác nhận phiên đăng nhập (nếu trang đã được thêm vào danh sách trang riêng tư).
    let started = false;
    function start() { if (started) return; started = true; load(); }
    if (!window.PulseAuth || window.PulseAuth.status === "authenticated") start();
    window.addEventListener("pulse:auth-changed", (e) => { if (e.detail?.status === "authenticated") start(); });
})();
