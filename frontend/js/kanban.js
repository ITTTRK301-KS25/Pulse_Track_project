
"use strict";
(function () {
    const board = document.getElementById("kanban-board");
    if (!board) return;

    const API = window.PulseAPI;
    const projectId = new URLSearchParams(location.search).get("project");
    const projectName = document.getElementById("current-project-name");
    const message = document.getElementById("kanban-message");
    const newTaskButton = document.getElementById("btn-new-task");
    const plannerButton = document.getElementById("btn-ai-planner");
    const selectProjectSection = document.getElementById("kanban-select-project");
    const kanbanFilters = document.getElementById("kanban-filters");
    const mainActions = document.getElementById("kanban-main-actions");

    function updateProjectView(hasProject) {
        if (selectProjectSection) selectProjectSection.hidden = hasProject;
        if (kanbanFilters) kanbanFilters.hidden = !hasProject;
        if (mainActions) mainActions.hidden = !hasProject;
        board.hidden = !hasProject;
        if (!hasProject) {
            if (newTaskButton) newTaskButton.hidden = true;
            if (plannerButton) plannerButton.hidden = true;
        }
    }

    const titleFilter = document.getElementById("filter-task-title");
    const assigneeFilter = document.getElementById("filter-task-assignee");
    const dueDateFilter = document.getElementById("filter-task-due-date");
    const clearFiltersButton = document.getElementById("clear-task-filters");
    const filterSummary = document.getElementById("kanban-filter-summary");
    const STATUSES = ["TODO", "IN_PROGRESS", "DONE"];

    let project = null;
    let tasks = [];
    let members = [];
    let membersLoaded = false;
    let membersError = "";
    let draggedTaskId = "";
    let loading = false;

    function esc(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);
    }

    function canCreate() {
        return Boolean(
            project &&
            !project.archived_at &&
            ["OWNER", "MEMBER"].includes(project.my_role || project.role)
        );
    }

    function canEdit() {
        return Boolean(
            project &&
            !project.archived_at &&
            (project.my_role || project.role) === "OWNER"
        );
    }

    function showMessage(text, type = "") {
        if (!message) return;
        message.textContent = text || "";
        message.hidden = !text;
        message.classList.toggle("kanban-error", type === "error");
        message.classList.toggle("kanban-success", type === "success");
    }

    function toast(text, type = "") {
        let wrap = document.querySelector(".toast-wrap");
        if (!wrap) {
            wrap = document.createElement("div");
            wrap.className = "toast-wrap";
            wrap.setAttribute("aria-live", "polite");
            document.body.appendChild(wrap);
        }

        const item = document.createElement("div");
        item.className = `toast ${type}`;
        item.textContent = text;
        wrap.appendChild(item);
        setTimeout(() => item.remove(), 4500);
    }

    function taskById(id) {
        return tasks.find(task => String(task.id) === String(id));
    }

    function saveTask(task) {
        if (!task || task.id == null) {
            throw new Error("Dữ liệu task không hợp lệ.");
        }

        const index = tasks.findIndex(
            item => String(item.id) === String(task.id)
        );

        if (index === -1) {
            tasks.push(task);
        } else {
            tasks[index] = task;
        }
    }

    function formatDate(value) {
        if (!value) return "";

        const [year, month, day] = String(value)
            .slice(0, 10)
            .split("-");

        return year && month && day
            ? `${day}/${month}/${year}`
            : "";
    }

    function parseDisplayDate(value) {
        const text = String(value ?? "").trim();
        if (!text) return { valid: true, value: null };

        const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
        if (!match) return { valid: false, value: null };

        const day = Number(match[1]);
        const month = Number(match[2]);
        const year = Number(match[3]);
        const leapYear = year % 4 === 0 &&
            (year % 100 !== 0 || year % 400 === 0);
        const daysInMonth = [
            31, leapYear ? 29 : 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31
        ];

        if (
            year < 1 ||
            month < 1 ||
            month > 12 ||
            day < 1 ||
            day > daysInMonth[month - 1]
        ) {
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

    function memberName(id) {
        if (id == null) return "";

        const member = members.find(
            item => String(item.user_id) === String(id)
        );

        return member?.display_name || "";
    }

    function renderAssigneeFilter() {
        if (!assigneeFilter) return;

        const selectedId = assigneeFilter.value;
        const assignedMembers = new Map();

        tasks
            .filter(task =>
                task.parent_id == null &&
                !task.archived_at &&
                STATUSES.includes(task.status) &&
                task.assignee_id != null
            )
            .forEach(task => {
                const id = String(task.assignee_id);
                const name = memberName(task.assignee_id);
                assignedMembers.set(
                    id,
                    name || `Người thực hiện #${id}`
                );
            });

        const options = Array.from(assignedMembers.entries())
            .sort((left, right) => left[1].localeCompare(right[1], "vi"))
            .map(([id, name]) => `
                <option value="${esc(id)}">${esc(name)}</option>
            `);

        assigneeFilter.innerHTML = [
            '<option value="">Tất cả người thực hiện</option>',
            ...options
        ].join("");

        assigneeFilter.value = assignedMembers.has(selectedId)
            ? selectedId
            : "";
    }

    function hasActiveFilters() {
        return Boolean(
            titleFilter?.value.trim() ||
            assigneeFilter?.value ||
            dueDateFilter?.value
        );
    }

    function filterTasks(parentTasks) {
        const keyword = titleFilter?.value.trim().toLocaleLowerCase() || "";
        const assigneeId = assigneeFilter?.value || "";
        const parsedDueDate = parseDisplayDate(dueDateFilter?.value);

        if (!parsedDueDate.valid) {
            return [];
        }

        return parentTasks.filter(task =>
            (!keyword ||
                String(task.title ?? "")
                    .toLocaleLowerCase()
                    .includes(keyword)) &&
            (!assigneeId ||
                String(task.assignee_id ?? "") === assigneeId) &&
            (!parsedDueDate.value ||
                String(task.due_date ?? "").slice(0, 10) ===
                    parsedDueDate.value)
        );
    }

    function renderCard(task) {
        const assignedTo = memberName(task.assignee_id);

        const subtaskCount = tasks.filter(
            item =>
                item.parent_id != null &&
                String(item.parent_id) === String(task.id) &&
                !item.archived_at
        ).length;

        return `
            <article
                class="kanban-task"
                data-task-id="${esc(task.id)}"
                ${canEdit() ? 'draggable="true"' : ""}
            >
                <button
                    type="button"
                    class="kanban-task-open"
                    data-open-task="${esc(task.id)}"
                    aria-label="Xem chi tiết ${esc(task.title)}"
                >
                    <span class="kanban-task-title">
                        ${esc(task.title)}
                    </span>
                    <span class="kanban-task-action">
                        Mở chi tiết &amp; subtask →
                    </span>
                </button>

                ${
                    task.description
                        ? `<p class="kanban-task-description">
                            ${esc(task.description)}
                           </p>`
                        : ""
                }

                <div class="kanban-task-meta">
                    ${
                        task.due_date
                            ? `<span>Hạn: ${esc(formatDate(task.due_date))}</span>`
                            : ""
                    }
                    ${
                        assignedTo
                            ? `<span>Phụ trách: ${esc(assignedTo)}</span>`
                            : task.assignee_id != null
                                ? "<span>Đã phân công</span>"
                                : ""
                    }
                    ${
                        subtaskCount
                            ? `<span>${subtaskCount} subtask</span>`
                            : ""
                    }
                </div>
            </article>
        `;
    }

    function renderBoard() {
        const allParentTasks = tasks.filter(task =>
            task.parent_id == null &&
            !task.archived_at &&
            STATUSES.includes(task.status)
        );

        const parentTasks = filterTasks(allParentTasks);
        const filtersActive = hasActiveFilters();
        const parsedDueDate = parseDisplayDate(dueDateFilter?.value);

        if (dueDateFilter) {
            dueDateFilter.setAttribute(
                "aria-invalid",
                String(!parsedDueDate.valid)
            );
        }

        if (filterSummary) {
            filterSummary.textContent = parsedDueDate.valid
                ? `Đang hiển thị ${parentTasks.length}/${allParentTasks.length} task`
                : "Ngày không hợp lệ. Hãy nhập theo dd/mm/yyyy.";

            filterSummary.classList.toggle(
                "is-error",
                !parsedDueDate.valid
            );
        }

        if (clearFiltersButton) {
            clearFiltersButton.hidden = !filtersActive;
        }

        board.querySelectorAll(".lane").forEach(lane => {
            const status = lane.dataset.status;
            const count = lane.querySelector("[data-count]");
            const cards = lane.querySelector("[data-cards]");

            if (!count || !cards) return;

            if (!status || !STATUSES.includes(status)) {
                count.textContent = "0";
                cards.innerHTML = `
                    <p class="kanban-empty">
                        Trạng thái này chưa được hỗ trợ bởi API.
                    </p>
                `;
                return;
            }

            const laneTasks = parentTasks.filter(
                task => task.status === status
            );

            count.textContent = String(laneTasks.length);

            cards.innerHTML = laneTasks.length
                ? laneTasks.map(renderCard).join("")
                : `<p class="kanban-empty">${
                    !filtersActive
                        ? "Chưa có công việc"
                        : parentTasks.length
                            ? "Không có task phù hợp trong trạng thái này"
                            : "Không tìm thấy task phù hợp"
                }</p>`;
        });

        board.querySelectorAll("[data-open-task]").forEach(button => {
            button.addEventListener("click", () => {
                const task = taskById(button.dataset.openTask);
                if (task) openTaskModal(task);
            });
        });

        if (newTaskButton) {
            newTaskButton.hidden = !canCreate();
        }
    }

    async function refreshTasks() {
        const response = await API.get(
            `/projects/${encodeURIComponent(projectId)}/tasks`
        );

        if (!Array.isArray(response?.data)) {
            throw new Error(
                "Dữ liệu công việc từ máy chủ không hợp lệ."
            );
        }

        tasks = response.data;
        renderAssigneeFilter();
        renderBoard();
    }

    async function loadWorkspace() {
        if (loading) return;

        if (!projectId) {
            updateProjectView(false);
            if (projectName) projectName.textContent = "";
            showMessage("");
            return;
        }

        updateProjectView(true);

        if (!API) {
            showMessage(
                "Chưa tải được HTTP client PulseAPI.",
                "error"
            );
            return;
        }

        loading = true;

        try {
            const [projectResponse, tasksResponse] =
                await Promise.all([
                    API.get(
                        `/projects/${encodeURIComponent(projectId)}`
                    ),
                    API.get(
                        `/projects/${encodeURIComponent(projectId)}/tasks`
                    )
                ]);

            project = projectResponse?.data;

            if (!project || !Array.isArray(tasksResponse?.data)) {
                throw new Error(
                    "Dữ liệu dự án hoặc công việc không hợp lệ."
                );
            }

            tasks = tasksResponse.data;
            updateProjectView(true);

            if (projectName) {
                projectName.textContent = `Dự án: ${project.name}`;
            }

            if (plannerButton) {
                const canUsePlanner =
                    (project.my_role || project.role) === "OWNER" &&
                    !project.archived_at;

                plannerButton.hidden = !canUsePlanner;
                plannerButton.href = canUsePlanner
                    ? `ai-planner.html?project=${encodeURIComponent(projectId)}`
                    : "projects.html";
            }

            members = [];
            membersLoaded = false;
            membersError = "";

            try {
                const membersResponse = await API.get(
                    `/projects/${encodeURIComponent(projectId)}/members`
                );
                if (!Array.isArray(membersResponse?.data)) {
                    throw new Error(
                        "Danh sách thành viên không hợp lệ."
                    );
                }
                members = membersResponse.data;
                membersLoaded = true;
            } catch (error) {
                if (error.status === 401) return;
                membersError =
                    error.message ||
                    "Không thể tải danh sách thành viên.";
            }

            renderAssigneeFilter();
            renderBoard();

            if (project.archived_at) {
                showMessage(
                    "Dự án đã lưu trữ: bảng chỉ xem, không thể chỉnh sửa."
                );
            } else if (!canCreate()) {
                showMessage(
                    "Bạn có quyền VIEWER: chỉ có thể xem công việc."
                );
            } else if (membersError) {
                showMessage(
                    `Không tải được danh sách thành viên: ${membersError}`,
                    "error"
                );
            } else {
                showMessage("");
            }
        } catch (error) {
            if (error.status === 401) return;

            project = null;
            updateProjectView(false);

            if (projectName) {
                projectName.textContent = "Không tải được dự án.";
            }

            if (newTaskButton) newTaskButton.hidden = true;
            if (plannerButton) plannerButton.hidden = true;

            showMessage(
                error.message || "Không tải được bảng công việc.",
                "error"
            );

            board.querySelectorAll("[data-cards]").forEach(cards => {
                cards.innerHTML = `
                    <p class="kanban-empty">
                        Không tải được công việc
                    </p>
                `;
            });
        } finally {
            loading = false;
        }
    }

    function memberOptions(selectedId) {
        const options = members
            .filter(member =>
                ["OWNER", "MEMBER"].includes(member.role)
            )
            .map(member => `
                <option
                    value="${esc(member.user_id)}"
                    ${
                        String(member.user_id) === String(selectedId ?? "")
                            ? "selected"
                            : ""
                    }
                >
                    ${esc(member.display_name)} (${esc(member.role)})
                </option>
            `);

        if (
            selectedId != null &&
            selectedId !== "" &&
            !members.some(
                member =>
                    String(member.user_id) === String(selectedId)
            )
        ) {
            options.push(`
                <option value="${esc(selectedId)}" selected>
                    Thành viên hiện tại (#${esc(selectedId)})
                </option>
            `);
        }

        return [
            '<option value="">Chưa phân công</option>',
            ...options
        ].join("");
    }

    function openModal(html) {
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";

        backdrop.innerHTML = `
            <div
                class="modal kanban-modal"
                role="dialog"
                aria-modal="true"
            >
                ${html}
            </div>
        `;

        function close() {
            backdrop.remove();
            document.removeEventListener("keydown", onKeyDown);
        }

        function onKeyDown(event) {
            if (event.key === "Escape") close();
        }

        backdrop.addEventListener("mousedown", event => {
            if (event.target === backdrop) close();
        });

        document.addEventListener("keydown", onKeyDown);
        document.body.appendChild(backdrop);

        return {
            element: backdrop.firstElementChild,
            close
        };
    }

    function showTaskMessage(text, type = "") {
        const box = document.querySelector(
            ".kanban-modal [data-task-message]"
        );

        if (!box) return;

        box.textContent = text || "";
        box.className = `form-banner${type ? ` ${type}` : ""}`;
        box.hidden = !text;
    }

    async function reloadTasksAfterConflict() {
        try {
            await refreshTasks();
            return true;
        } catch (error) {
            showTaskMessage(
                `${error.message || "Không thể tải lại công việc."} ` +
                "Hãy đóng cửa sổ và tải lại bảng.",
                "error"
            );
            return false;
        }
    }

    function renderSubtasks(parentTask, list) {
        if (!list) return;

        const subtasks = tasks.filter(task =>
            task.parent_id != null &&
            String(task.parent_id) === String(parentTask.id) &&
            !task.archived_at
        );

        if (!subtasks.length) {
            list.innerHTML = `
                <li class="subtask-empty">
                    Chưa có subtask.
                </li>
            `;
            return;
        }

        list.innerHTML = subtasks.map(task => `
            <li class="subtask-item">
                <label>
                    <input
                        type="checkbox"
                        data-subtask-id="${esc(task.id)}"
                        ${task.status === "DONE" ? "checked" : ""}
                        ${
                            canEdit() && !task.archived_at
                                ? ""
                                : "disabled"
                        }
                    >
                    <span class="${
                        task.status === "DONE" ? "is-done" : ""
                    }">
                        ${esc(task.title)}
                    </span>
                </label>
            </li>
        `).join("");

        list.querySelectorAll("[data-subtask-id]").forEach(input => {
            input.addEventListener("change", async () => {
                const task = taskById(input.dataset.subtaskId);

                if (!task || !canEdit()) {
                    if (task) {
                        input.checked = task.status === "DONE";
                    }
                    return;
                }

                input.disabled = true;
                showTaskMessage("");

                try {
                    const response = await API.patch(
                        `/tasks/${encodeURIComponent(task.id)}/status`,
                        {
                            status: input.checked ? "DONE" : "TODO",
                            version: task.version
                        }
                    );

                    if (!response?.data || response.data.id == null) {
                        throw new Error(
                            "Máy chủ trả về subtask không hợp lệ."
                        );
                    }

                    await refreshTasks();
                    renderSubtasks(parentTask, list);

                    toast(
                        "Đã cập nhật trạng thái subtask.",
                        "success"
                    );
                } catch (error) {
                    input.checked = task.status === "DONE";
                    input.disabled = false;

                    if (error.status === 401) return;

                    if (error.status === 409) {
                        showTaskMessage(
                            "Subtask đã được người khác cập nhật. " +
                            (error.message || "Đang tải lại dữ liệu."),
                            "error"
                        );

                        const reloaded =
                            await reloadTasksAfterConflict();

                        if (reloaded) {
                            renderSubtasks(parentTask, list);
                        }
                        return;
                    }

                    showTaskMessage(
                        error.message ||
                        "Không thể cập nhật subtask.",
                        "error"
                    );
                }
            });
        });
    }

    function openTaskModal(task = null) {
        const isNew = !task;
        const creatable = canCreate();
        const editable = canEdit();

        // OWNER và MEMBER được tạo task.
        // Chỉ OWNER được sửa task đã tồn tại.
        const canModifyForm = isNew ? creatable : editable;

        if (isNew && !creatable) {
            showMessage(
                "Bạn không có quyền tạo task.",
                "error"
            );
            return;
        }

        const assignedId = task?.assignee_id ?? "";

        const subtasksSection = isNew ? "" : `
            <section
                class="task-subtasks"
                aria-labelledby="subtasks-heading"
            >
                <div class="subtask-heading">
                    <h3 id="subtasks-heading">Subtask</h3>
                    <span class="kanban-version">
                        Tối đa một cấp
                    </span>
                </div>

                <ul
                    class="subtask-list"
                    data-subtask-list
                ></ul>

                ${
                    creatable && !task.archived_at
                        ? `
                            <form
                                class="subtask-add-form"
                                data-subtask-form
                            >
                                <label
                                    class="sr-only"
                                    for="new-subtask-title"
                                >
                                    Tên subtask
                                </label>

                                <input
                                    id="new-subtask-title"
                                    name="title"
                                    maxlength="200"
                                    placeholder="Thêm subtask nhanh..."
                                    required
                                >

                                <button
                                    type="submit"
                                    class="btn btn-small"
                                >
                                    Thêm
                                </button>
                            </form>
                        `
                        : ""
                }
            </section>
        `;

        const modal = openModal(`
            <div class="kanban-modal-heading">
                <h2>
                    ${isNew ? "Tạo task mới" : "Chi tiết task"}
                </h2>

                <button
                    type="button"
                    class="modal-close"
                    data-close
                    aria-label="Đóng"
                >
                    ×
                </button>
            </div>

            ${
                !isNew
                    ? `
                        <p class="kanban-version">
                            Trạng thái: ${esc(task.status)}
                            · Phiên bản ${esc(task.version)}
                        </p>
                    `
                    : ""
            }

            <div
                class="form-banner"
                data-task-message
                role="alert"
                hidden
            ></div>

            ${
                membersError
                    ? `
                        <p class="kanban-field-hint">
                            ${esc(membersError)}
                            Không thể thay đổi người phụ trách
                            cho đến khi tải được thành viên.
                        </p>
                    `
                    : ""
            }

            <form
                class="form-grid kanban-task-form"
                data-task-form
            >
                <label>
                    Tiêu đề *
                    <input
                        name="title"
                        value="${esc(task?.title || "")}"
                        maxlength="200"
                        required
                        ${canModifyForm ? "" : "disabled"}
                    >
                </label>

                <label>
                    Mô tả
                    <textarea
                        name="description"
                        maxlength="5000"
                        rows="4"
                        ${canModifyForm ? "" : "disabled"}
                    >${esc(task?.description || "")}</textarea>
                </label>

                <div class="row2">
                    <label>
                        Hạn hoàn thành
                        <input
                            type="text"
                            name="due_date"
                            inputmode="numeric"
                            maxlength="10"
                            placeholder="dd/mm/yyyy"
                            autocomplete="off"
                            value="${esc(
                                formatDate(task?.due_date)
                            )}"
                            ${canModifyForm ? "" : "disabled"}
                        >
                    </label>

                    <label>
                        Người phụ trách
                        <select
                            name="assignee_id"
                            ${
                                canModifyForm && membersLoaded
                                    ? ""
                                    : "disabled"
                            }
                        >
                            ${memberOptions(assignedId)}
                        </select>
                    </label>
                </div>

                <div class="modal-actions">
                    <button
                        type="button"
                        class="btn"
                        data-close
                    >
                        Đóng
                    </button>

                    ${
                        canModifyForm
                            ? `
                                <button
                                    type="submit"
                                    class="btn btn-primary"
                                >
                                    ${
                                        isNew
                                            ? "Tạo task"
                                            : "Lưu thay đổi"
                                    }
                                </button>
                            `
                            : ""
                    }
                </div>
            </form>

            ${subtasksSection}
        `);

        const modalElement = modal.element;
        const taskForm = modalElement.querySelector("[data-task-form]");
        const subtaskList = modalElement.querySelector(
            "[data-subtask-list]"
        );
        const subtaskForm = modalElement.querySelector(
            "[data-subtask-form]"
        );

        modalElement.querySelectorAll("[data-close]").forEach(button => {
            button.addEventListener("click", modal.close);
        });

        if (!isNew && subtaskList) {
            renderSubtasks(task, subtaskList);
        }

        if (taskForm && canModifyForm) {
            taskForm.addEventListener("submit", async event => {
                event.preventDefault();

                const formData = new FormData(taskForm);
                const title = String(
                    formData.get("title") || ""
                ).trim();

                const description = String(
                    formData.get("description") || ""
                ).trim();

                const parsedDate = parseDisplayDate(
                    formData.get("due_date")
                );

                const assigneeValue = String(
                    formData.get("assignee_id") || ""
                ).trim();

                if (!title) {
                    showTaskMessage(
                        "Vui lòng nhập tiêu đề task.",
                        "error"
                    );
                    return;
                }

                if (!parsedDate.valid) {
                    showTaskMessage(
                        "Ngày không hợp lệ. Hãy nhập theo dd/mm/yyyy.",
                        "error"
                    );
                    return;
                }

                const payload = {
                    title,
                    description: description || null,
                    due_date: parsedDate.value
                };

                if (membersLoaded) {
                    payload.assignee_id = assigneeValue
                        ? Number(assigneeValue)
                        : null;
                }

                const submitButton = taskForm.querySelector(
                    'button[type="submit"]'
                );

                if (submitButton) {
                    submitButton.disabled = true;
                }

                showTaskMessage("");

                try {
                    let response;

                    if (isNew) {
                        response = await API.post(
                            `/projects/${encodeURIComponent(projectId)}/tasks`,
                            payload
                        );
                    } else {
                        response = await API.patch(
                            `/tasks/${encodeURIComponent(task.id)}`,
                            {
                                ...payload,
                                version: task.version
                            }
                        );
                    }

                    if (!response?.data || response.data.id == null) {
                        throw new Error(
                            "Máy chủ trả về dữ liệu task không hợp lệ."
                        );
                    }

                    await refreshTasks();

                    modal.close();

                    toast(
                        isNew
                            ? "Đã tạo task thành công."
                            : "Đã cập nhật task thành công.",
                        "success"
                    );
                } catch (error) {
                    if (error.status === 401) return;

                    if (error.status === 409) {
                        showTaskMessage(
                            "Task đã được người khác cập nhật. " +
                            "Vui lòng tải lại dữ liệu trước khi sửa.",
                            "error"
                        );

                        await reloadTasksAfterConflict();
                    } else {
                        showTaskMessage(
                            error.message ||
                            "Không thể lưu thông tin task.",
                            "error"
                        );
                    }
                } finally {
                    if (submitButton && submitButton.isConnected) {
                        submitButton.disabled = false;
                    }
                }
            });
        }

        if (subtaskForm && !isNew) {
            subtaskForm.addEventListener("submit", async event => {
                event.preventDefault();

                if (!canCreate()) {
                    showTaskMessage(
                        "Bạn không có quyền tạo subtask.",
                        "error"
                    );
                    return;
                }

                const titleInput = subtaskForm.querySelector(
                    'input[name="title"]'
                );

                const title = titleInput?.value.trim() || "";

                if (!title) {
                    showTaskMessage(
                        "Vui lòng nhập tên subtask.",
                        "error"
                    );
                    return;
                }

                const submitButton = subtaskForm.querySelector(
                    'button[type="submit"]'
                );

                if (submitButton) {
                    submitButton.disabled = true;
                }

                showTaskMessage("");

                try {
                    const response = await API.post(
                        `/tasks/${encodeURIComponent(task.id)}/subtasks`,
                        { title }
                    );

                    if (!response?.data || response.data.id == null) {
                        throw new Error(
                            "Máy chủ trả về subtask không hợp lệ."
                        );
                    }

                    await refreshTasks();

                    if (subtaskList) {
                        renderSubtasks(task, subtaskList);
                    }

                    if (titleInput) {
                        titleInput.value = "";
                        titleInput.focus();
                    }

                    toast(
                        "Đã thêm subtask thành công.",
                        "success"
                    );
                } catch (error) {
                    if (error.status === 401) return;

                    showTaskMessage(
                        error.message ||
                        "Không thể thêm subtask.",
                        "error"
                    );
                } finally {
                    if (submitButton && submitButton.isConnected) {
                        submitButton.disabled = false;
                    }
                }
            });
        }

        // Tích hợp module bình luận và lịch sử nếu đã được tải.
        if (!isNew) {
            const commentsModule = window.PulseComments;
            const historyModule = window.PulseHistory;

            const taskContext = {
                taskId: task.id,
                projectId,
                task,
                project,
                container: modalElement,
                canCreate: canCreate(),
                canEdit: canEdit()
            };

            if (
                commentsModule &&
                typeof commentsModule.mount === "function"
            ) {
                try {
                    commentsModule.mount(taskContext);
                } catch (error) {
                    console.error(
                        "Không thể khởi tạo bình luận:",
                        error
                    );
                }
            }

            if (
                historyModule &&
                typeof historyModule.mount === "function"
            ) {
                try {
                    historyModule.mount(taskContext);
                } catch (error) {
                    console.error(
                        "Không thể khởi tạo lịch sử:",
                        error
                    );
                }
            }
        }
    }

    // =====================================================
    // KÉO THẢ TASK TRÊN KANBAN
    // =====================================================

    board.addEventListener("dragstart", event => {
        const card = event.target.closest(
            ".kanban-task[data-task-id]"
        );

        if (!card || !canEdit()) {
            event.preventDefault();
            return;
        }

        draggedTaskId = card.dataset.taskId;

        if (event.dataTransfer) {
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData(
                "text/plain",
                draggedTaskId
            );
        }

        card.classList.add("is-dragging");
    });

    board.addEventListener("dragend", event => {
        const card = event.target.closest(".kanban-task");

        if (card) {
            card.classList.remove("is-dragging");
        }

        board.querySelectorAll(".lane").forEach(lane => {
            lane.classList.remove("is-drag-over");
        });

        draggedTaskId = "";
    });

    board.addEventListener("dragover", event => {
        const lane = event.target.closest(
            ".lane[data-status]"
        );

        if (!lane || !canEdit() || !draggedTaskId) {
            return;
        }

        if (!STATUSES.includes(lane.dataset.status)) {
            return;
        }

        event.preventDefault();

        if (event.dataTransfer) {
            event.dataTransfer.dropEffect = "move";
        }

        board.querySelectorAll(".lane").forEach(item => {
            item.classList.toggle(
                "is-drag-over",
                item === lane
            );
        });
    });

    board.addEventListener("dragleave", event => {
        const lane = event.target.closest(
            ".lane[data-status]"
        );

        if (!lane) return;

        if (!lane.contains(event.relatedTarget)) {
            lane.classList.remove("is-drag-over");
        }
    });

    board.addEventListener("drop", async event => {
        const lane = event.target.closest(
            ".lane[data-status]"
        );

        if (!lane || !canEdit()) return;

        const newStatus = lane.dataset.status;

        if (!STATUSES.includes(newStatus)) {
            return;
        }

        event.preventDefault();

        lane.classList.remove("is-drag-over");

        const taskId = draggedTaskId ||
            event.dataTransfer?.getData("text/plain");

        draggedTaskId = "";

        const task = taskById(taskId);

        if (!task || task.status === newStatus) {
            return;
        }

        const previousStatus = task.status;

        task.status = newStatus;
        renderBoard();

        try {
        const response = await API.patch(
            `/tasks/${encodeURIComponent(task.id)}`,   
            {
                status: newStatus,
                version: task.version
            }
        );

            if (!response?.data || response.data.id == null) {
                throw new Error(
                    "Máy chủ trả về dữ liệu task không hợp lệ."
                );
            }

            await refreshTasks();

            toast(
                "Đã cập nhật trạng thái task.",
                "success"
            );
        } catch (error) {
            if (error.status === 401) return;

            task.status = previousStatus;
            renderBoard();

            if (error.status === 409) {
                toast(
                    "Task đã được cập nhật ở nơi khác. " +
                    "Đang tải lại dữ liệu.",
                    "error"
                );

                try {
                    await refreshTasks();
                } catch (reloadError) {
                    showMessage(
                        reloadError.message ||
                        "Không thể tải lại công việc.",
                        "error"
                    );
                }

                return;
            }

            toast(
                error.message ||
                "Không thể cập nhật trạng thái task.",
                "error"
            );
        }
    });

    // =====================================================
    // BỘ LỌC F11
    // =====================================================

    if (titleFilter) {
        titleFilter.addEventListener("input", () => {
            renderBoard();
        });
    }

    if (assigneeFilter) {
        assigneeFilter.addEventListener("change", () => {
            renderBoard();
        });
    }

    if (dueDateFilter) {
        dueDateFilter.addEventListener("input", () => {
            renderBoard();
        });
    }

    if (clearFiltersButton) {
        clearFiltersButton.addEventListener("click", () => {
            if (titleFilter) {
                titleFilter.value = "";
            }

            if (assigneeFilter) {
                assigneeFilter.value = "";
            }

            if (dueDateFilter) {
                dueDateFilter.value = "";
            }

            renderBoard();
        });
    }

    // =====================================================
    // TẠO TASK MỚI
    // =====================================================

    if (newTaskButton) {
        newTaskButton.addEventListener("click", () => {
            if (!canCreate()) {
                toast(
                    "Bạn không có quyền tạo task.",
                    "error"
                );
                return;
            }

            openTaskModal();
        });
    }

    // =====================================================
    // KHỞI TẠO TRANG QUẢN LÝ CÔNG VIỆC
    // =====================================================

    if (!projectId) {
        // Truy cập từ menu Quản lý công việc:
        // Không hiển thị bảng Kanban trống.
        // Chỉ hiển thị màn hình Chọn dự án.
        updateProjectView(false);

        if (projectName) {
            projectName.textContent = "";
        }

        showMessage("");
    } else {
        // Đã chọn dự án:
        // Tải thông tin dự án, thành viên và task.
        updateProjectView(true);
        loadWorkspace();
    }
})();
