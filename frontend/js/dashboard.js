
(function () {
    "use strict";

    const API = window.PulseAPI;
    const $ = id => document.getElementById(id);

    const totalEl = $("dashboard-total");
    const progressEl = $("dashboard-progress");
    const doneEl = $("dashboard-done");
    const panel = $("dashboard-task-panel");
    const cards = [...document.querySelectorAll("[data-dashboard-view]")];

    if (!totalEl || !progressEl || !doneEl) return;

    let projects = [];
    let allTasks = [];
    let membersByProject = new Map();
    let activeView = null;
    let page = 1;
    let loading = false;
    let loaded = false;
    let started = false;

    const pageSize = 5;

    const views = {
        all: {
            title: "Tổng công việc",
            description: "Danh sách công việc thuộc các dự án.",
            icon: "▦"
        },
        progress: {
            title: "Công việc đang thực hiện",
            description: "Những công việc đang được triển khai.",
            icon: "◷"
        },
        done: {
            title: "Công việc hoàn thành",
            description: "Những công việc đã được hoàn thành.",
            icon: "✓"
        }
    };

    const statusNames = {
        TODO: "Cần làm",
        IN_PROGRESS: "Đang thực hiện",
        REVIEW: "Đánh giá",
        TESTING: "Kiểm thử",
        QA: "Kiểm thử",
        DONE: "Hoàn thành"
    };

    const statusOptions = [
        "TODO",
        "IN_PROGRESS",
        "REVIEW",
        "TESTING",
        "DONE"
    ];

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function setStats(total, progress, done) {
        totalEl.textContent = total;
        progressEl.textContent = progress;
        doneEl.textContent = done;
    }

    function isArchived(item) {
        return Boolean(
            item.archived_at ||
            item.deleted_at ||
            item.is_archived === true ||
            item.archived === true
        );
    }

    function isParentTask(task) {
        if (task.parent_task_id != null) return false;
        if (task.parent_id != null) return false;
        if (task.is_subtask === true) return false;
        return true;
    }

    function isValidTask(task) {
        if (!task || typeof task !== "object") return false;
        if (isArchived(task)) return false;
        if (!isParentTask(task)) return false;
        return true;
    }

    function normalizeTasks(tasks, project) {
        return tasks
            .filter(isValidTask)
            .map(task => ({
                ...task,
                _projectId: project.id,
                _projectName: project.name || "Dự án"
            }));
    }

    function formatDate(value) {
        if (!value) return "—";

        const datePart = String(value).slice(0, 10);
        const match = datePart.match(
            /^(\d{4})-(\d{2})-(\d{2})$/
        );

        if (match) {
            return `${match[3]}/${match[2]}/${match[1]}`;
        }

        return String(value);
    }

    function getTaskDate(task) {
        return task.due_date ?? task.deadline ?? null;
    }

    function getAssignee(task) {
        if (task.assignee_id == null) {
            return "Chưa phân công";
        }

        const projectId = String(task._projectId);
        const members = membersByProject.get(projectId) || [];

        const member = members.find(item =>
            String(item.user_id) === String(task.assignee_id)
        );

        if (member) {
            return member.display_name ||
                member.email ||
                "Thành viên";
        }

        return `Thành viên #${task.assignee_id}`;
    }

    function getInitials(name) {
        if (!name || name === "Chưa phân công") {
            return "?";
        }

        return name.trim()
            .split(/\s+/)
            .slice(-2)
            .map(word => word[0])
            .join("")
            .toUpperCase();
    }

    function showError(message) {
        setStats("—", "—", "—");

        let errorEl = $("dashboard-stats-error");

        if (!errorEl) {
            errorEl = document.createElement("p");
            errorEl.id = "dashboard-stats-error";
            errorEl.setAttribute("role", "alert");
            errorEl.style.cssText =
                "color:#b42318;font-size:13px;margin:12px 0;";

            document.querySelector(".dashboard-stats")
                ?.insertAdjacentElement("afterend", errorEl);
        }

        errorEl.textContent = message;
    }

    function clearError() {
        $("dashboard-stats-error")?.remove();
    }

    function updateStats() {
        const total = allTasks.length;

        const progress = allTasks.filter(task =>
            task.status === "IN_PROGRESS"
        ).length;

        const done = allTasks.filter(task =>
            task.status === "DONE"
        ).length;

        setStats(total, progress, done);
    }

    async function loadProjectMembers(projectList) {
        const results = await Promise.allSettled(
            projectList.map(project =>
                API.get(
                    `/projects/${encodeURIComponent(project.id)}/members`
                )
            )
        );

        const nextMembers = new Map();
        let failed = 0;

        results.forEach((result, index) => {
            const projectId = String(projectList[index].id);

            if (
                result.status === "fulfilled" &&
                Array.isArray(result.value?.data)
            ) {
                nextMembers.set(projectId, result.value.data);
            } else {
                nextMembers.set(projectId, []);
                failed++;
            }
        });

        if (failed > 0) {
            console.warn(
                `Không tải được thành viên của ${failed}/${projectList.length} dự án.`
            );
        }

        return nextMembers;
    }

    function resetDashboardData() {
        projects = [];
        allTasks = [];
        membersByProject = new Map();
        loaded = false;
    }

    function showTableError(message) {
        const body = $("dt-table-body");
        const empty = $("dt-empty");

        if (body) body.innerHTML = "";

        if (empty) {
            empty.hidden = false;

            const title = empty.querySelector("strong");
            const description = empty.querySelector("p");

            if (title) {
                title.textContent = "Không thể tải công việc";
            }

            if (description) {
                description.textContent = message;
            }
        }

        if ($("dt-panel-count")) {
            $("dt-panel-count").textContent = "Chưa có dữ liệu";
        }

        if ($("dt-results")) {
            $("dt-results").textContent = "Không thể tải dữ liệu";
        }

        if ($("dt-page")) {
            $("dt-page").textContent = "1 / 1";
        }

        if ($("dt-prev")) $("dt-prev").disabled = true;
        if ($("dt-next")) $("dt-next").disabled = true;
    }

    async function loadDashboard() {
        if (loading) return;

        if (!API || typeof API.get !== "function") {
            resetDashboardData();
            showError("Không tìm thấy kết nối PulseAPI.");
            showTableError("Vui lòng kiểm tra cấu hình ứng dụng.");
            return;
        }

        loading = true;
        loaded = false;

        clearError();
        setStats("…", "…", "…");

        try {
            const response = await API.get("/projects");

            if (!Array.isArray(response?.data)) {
                throw new Error("Danh sách dự án không hợp lệ.");
            }

            const nextProjects = response.data.filter(project =>
                project &&
                project.id != null &&
                !isArchived(project)
            );

            const results = await Promise.allSettled(
                nextProjects.map(project =>
                    API.get(
                        `/projects/${encodeURIComponent(project.id)}/tasks`
                    )
                )
            );

            const nextTasks = [];
            let failed = 0;

            results.forEach((result, index) => {
                if (
                    result.status !== "fulfilled" ||
                    !Array.isArray(result.value?.data)
                ) {
                    failed++;
                    return;
                }

                nextTasks.push(
                    ...normalizeTasks(
                        result.value.data,
                        nextProjects[index]
                    )
                );
            });

            if (failed > 0) {
                throw new Error(
                    `Không tải được công việc của ${failed}/${nextProjects.length} dự án.`
                );
            }

            const nextMembers = await loadProjectMembers(nextProjects);

            projects = nextProjects;
            allTasks = nextTasks;
            membersByProject = nextMembers;
            loaded = true;

            updateStats();
            fillProjectOptions();
            fillAssigneeOptions();
            fillStatusOptions();

            if (activeView) render();

        } catch (error) {
            resetDashboardData();

            if (error?.status === 401) return;

            const message = error?.message ||
                "Không thể tải thống kê công việc.";

            showError(message);
            showTableError(message);

        } finally {
            loading = false;
        }
    }

    function fillProjectOptions() {
        const select = $("dt-project");
        if (!select) return;

        const previous = select.value;

        select.innerHTML = "";
        select.add(new Option("Tất cả dự án", ""));

        projects.forEach(project => {
            select.add(new Option(
                project.name || "Dự án",
                String(project.id)
            ));
        });

        select.value = [...select.options].some(
            option => option.value === previous
        ) ? previous : "";
    }

    function fillAssigneeOptions() {
        const select = $("dt-assignee");
        if (!select) return;

        const previous = select.value;
        const projectId = $("dt-project")?.value || "";
        const uniqueMembers = new Map();

        membersByProject.forEach((members, id) => {
            if (projectId && id !== projectId) return;

            members.forEach(member => {
                if (member.user_id == null) return;

                uniqueMembers.set(
                    String(member.user_id),
                    member
                );
            });
        });

        select.innerHTML = "";
        select.add(new Option("Tất cả người phụ trách", ""));
        select.add(new Option("Chưa phân công", "unassigned"));

        [...uniqueMembers.values()]
            .sort((a, b) =>
                (a.display_name || a.email || "").localeCompare(
                    b.display_name || b.email || "",
                    "vi"
                )
            )
            .forEach(member => {
                select.add(new Option(
                    member.display_name ||
                    member.email ||
                    `Thành viên #${member.user_id}`,
                    String(member.user_id)
                ));
            });

        select.value = [...select.options].some(
            option => option.value === previous
        ) ? previous : "";
    }

    function fillStatusOptions() {
        const select = $("dt-status");
        if (!select) return;

        const previous = select.value;

        select.innerHTML = "";
        select.add(new Option("Tất cả trạng thái", ""));

        statusOptions.forEach(status => {
            select.add(new Option(
                statusNames[status],
                status
            ));
        });

        select.value = statusOptions.includes(previous)
            ? previous
            : "";
    }

    function openView(view) {
        if (!panel || !views[view]) return;

        if (activeView === view) {
            closeView();
            return;
        }

        activeView = view;
        page = 1;

        panel.hidden = false;
        panel.dataset.view = view;

        $("dt-panel-title").textContent = views[view].title;
        $("dt-panel-description").textContent =
            views[view].description;
        $("dt-panel-icon").textContent = views[view].icon;

        $("dt-search").value = "";
        $("dt-project").value = "";
        $("dt-status").value = "";
        $("dt-assignee").value = "";

        cards.forEach(card => {
            const selected = card.dataset.dashboardView === view;

            card.classList.toggle("dt-active", selected);
            card.setAttribute("aria-expanded", String(selected));
        });

        fillStatusOptions();
        fillAssigneeOptions();

        if (loaded) {
            render();
        } else {
            showTableError(
                loading
                    ? "Đang tải dữ liệu, vui lòng chờ."
                    : "Chưa có dữ liệu. Vui lòng tải lại trang."
            );
        }

        panel.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });
    }

    function closeView() {
        activeView = null;

        if (panel) panel.hidden = true;

        cards.forEach(card => {
            card.classList.remove("dt-active");
            card.setAttribute("aria-expanded", "false");
        });
    }

    function getViewTasks() {
        return allTasks.filter(task => {
            if (activeView === "progress") {
                return task.status === "IN_PROGRESS";
            }

            if (activeView === "done") {
                return task.status === "DONE";
            }

            return true;
        });
    }

    function getFilteredTasks() {
        const search = ($("dt-search")?.value || "")
            .trim()
            .toLocaleLowerCase("vi");

        const projectId = $("dt-project")?.value || "";
        const status = $("dt-status")?.value || "";
        const assignee = $("dt-assignee")?.value || "";

        return getViewTasks().filter(task => {
            if (
                projectId &&
                String(task._projectId) !== projectId
            ) return false;

            if (status && task.status !== status) {
                return false;
            }

            if (assignee === "unassigned") {
                if (task.assignee_id != null) return false;
            } else if (assignee) {
                if (String(task.assignee_id) !== assignee) {
                    return false;
                }
            }

            if (search) {
                const content = [
                    task.title,
                    task.description,
                    task._projectName,
                    getAssignee(task)
                ].join(" ").toLocaleLowerCase("vi");

                if (!content.includes(search)) return false;
            }

            return true;
        });
    }

    function renderRow(task, index) {
        const status = task.status || "TODO";

        const statusClass =
            status === "DONE" ? "done" :
            status === "IN_PROGRESS" ? "progress" : "";

        const assignee = getAssignee(task);
        const name = task.title || "Chưa có tiêu đề";

        const url =
            `kanban.html?project=${encodeURIComponent(task._projectId)}`;

        return `
            <tr>
                <td>${index}</td>
                <td>
                    <span class="dt-task-name">
                        ${escapeHTML(name)}
                    </span>
                </td>
                <td>
                    <span class="dt-project-tag">
                        ${escapeHTML(task._projectName)}
                    </span>
                </td>
                <td>
                    <span class="dt-status-tag ${statusClass}">
                        ${escapeHTML(statusNames[status] || status)}
                    </span>
                </td>
                <td>
                    <span class="dt-person">
                        <span class="dt-avatar">
                            ${escapeHTML(getInitials(assignee))}
                        </span>
                        ${escapeHTML(assignee)}
                    </span>
                </td>
                <td>
                    ${escapeHTML(formatDate(getTaskDate(task)))}
                </td>
                <td>
                    <a
                        class="dt-open"
                        href="${url}"
                        title="Mở Kanban của dự án"
                        aria-label="Mở dự án chứa công việc ${escapeHTML(name)}"
                    >↗</a>
                </td>
            </tr>
        `;
    }

    function render() {
        if (!activeView || !panel || !loaded) return;

        const viewTasks = getViewTasks();

        $("dt-panel-count").textContent =
            `${viewTasks.length} công việc`;

        const filtered = getFilteredTasks();

        const totalPages = Math.max(
            1,
            Math.ceil(filtered.length / pageSize)
        );

        page = Math.min(Math.max(1, page), totalPages);

        const start = (page - 1) * pageSize;
        const visible = filtered.slice(start, start + pageSize);

        $("dt-table-body").innerHTML = visible
            .map((task, index) =>
                renderRow(task, start + index + 1)
            )
            .join("");

        const empty = $("dt-empty");

        if (empty) {
            empty.hidden = filtered.length !== 0;

            const title = empty.querySelector("strong");
            const description = empty.querySelector("p");

            if (title) {
                title.textContent = "Không tìm thấy công việc";
            }

            if (description) {
                description.textContent =
                    "Thử thay đổi từ khóa hoặc bộ lọc.";
            }
        }

        $("dt-results").textContent = filtered.length
            ? `Hiển thị ${start + 1}–${start + visible.length} / ${filtered.length} công việc`
            : "Hiển thị 0 công việc";

        $("dt-page").textContent = `${page} / ${totalPages}`;

        $("dt-prev").disabled = page <= 1;
        $("dt-next").disabled = page >= totalPages;
    }

    function setupEvents() {
        cards.forEach(card => {
            card.addEventListener("click", () => {
                openView(card.dataset.dashboardView);
            });

            card.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openView(card.dataset.dashboardView);
                }
            });
        });

        $("dt-panel-close")?.addEventListener(
            "click",
            closeView
        );

        $("dt-search")?.addEventListener("input", () => {
            page = 1;
            render();
        });

        $("dt-project")?.addEventListener("change", () => {
            page = 1;
            fillAssigneeOptions();
            fillStatusOptions();
            render();
        });

        $("dt-status")?.addEventListener("change", () => {
            page = 1;
            render();
        });

        $("dt-assignee")?.addEventListener("change", () => {
            page = 1;
            render();
        });

        $("dt-prev")?.addEventListener("click", () => {
            if (page > 1) {
                page--;
                render();
            }
        });

        $("dt-next")?.addEventListener("click", () => {
            page++;
            render();
        });
    }

    function start() {
        if (started) return;
        started = true;

        setupEvents();
        loadDashboard();
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            start,
            { once: true }
        );
    } else {
        start();
    }
})();
