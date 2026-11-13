"use strict";

(function () {
    const board = document.getElementById("kanban-board");
    if (!board) return;

    const API = window.PulseAPI;
    const projectId = new URLSearchParams(location.search).get("project");
    const projectName = document.getElementById("current-project-name");
    const message = document.getElementById("kanban-message");
    const newTaskButton = document.getElementById("btn-new-task");
    const STATUSES = ["TODO", "IN_PROGRESS", "DONE"];

    let project = null;
    let tasks = [];
    let members = [];
    let membersLoaded = false;
    let membersError = "";
    let draggedTaskId = "";

    function esc(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[char]));
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
        const index = tasks.findIndex(item => String(item.id) === String(task.id));
        if (index === -1) tasks.push(task);
        else tasks[index] = task;
    }

    function formatDate(value) {
        if (!value) return "";
        const [year, month, day] = String(value).slice(0, 10).split("-");
        return year && month && day ? `${day}/${month}/${year}` : "";
    }

    function memberName(id) {
        if (id == null) return "";
        const member = members.find(item => String(item.user_id) === String(id));
        return member?.display_name || "";
    }

    function renderCard(task) {
        const assignedTo = memberName(task.assignee_id);
        const subtaskCount = tasks.filter(
            item => String(item.parent_id) === String(task.id)
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
                    <span class="kanban-task-title">${esc(task.title)}</span>
                    <span class="kanban-task-action">Mở chi tiết &amp; subtask →</span>
                </button>
                ${
                    task.description
                        ? `<p class="kanban-task-description">${esc(task.description)}</p>`
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
                                ? `<span>Đã phân công</span>`
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
        const parentTasks = tasks.filter(task =>
            task.parent_id == null &&
            !task.archived_at &&
            STATUSES.includes(task.status)
        );

        board.querySelectorAll(".lane").forEach(lane => {
            const status = lane.dataset.status;
            const count = lane.querySelector("[data-count]");
            const cards = lane.querySelector("[data-cards]");

            if (!status) {
                count.textContent = "0";
                cards.innerHTML = '<p class="kanban-empty">Trạng thái này chưa được hỗ trợ bởi API.</p>';
                return;
            }

            const laneTasks = parentTasks.filter(task => task.status === status);
            count.textContent = String(laneTasks.length);

            cards.innerHTML = laneTasks.length
                ? laneTasks.map(renderCard).join("")
                : '<p class="kanban-empty">Chưa có công việc</p>';
        });

        board.querySelectorAll("[data-open-task]").forEach(button => {
            button.addEventListener("click", () => {
                const task = taskById(button.dataset.openTask);
                if (task) openTaskModal(task);
            });
        });

        newTaskButton.hidden = !canCreate();
    }

    async function refreshTasks() {
        const response = await API.get(
            `/projects/${encodeURIComponent(projectId)}/tasks`
        );
        if (!Array.isArray(response?.data)) {
            throw new Error("Dữ liệu công việc từ máy chủ không hợp lệ.");
        }
        tasks = response.data;
        renderBoard();
    }

    async function loadWorkspace() {
        if (!projectId) {
            projectName.textContent = "Hãy chọn một dự án từ danh sách dự án.";
            showMessage("Thiếu mã dự án. Mở bảng Kanban từ trang Dự án.", "error");
            board.querySelectorAll("[data-cards]").forEach(cards => {
                cards.innerHTML = '<p class="kanban-empty">Chưa chọn dự án</p>';
            });
            return;
        }

        try {
            const [projectResponse, tasksResponse] = await Promise.all([
                API.get(`/projects/${encodeURIComponent(projectId)}`),
                API.get(`/projects/${encodeURIComponent(projectId)}/tasks`)
            ]);

            project = projectResponse?.data;
            if (!project || !Array.isArray(tasksResponse?.data)) {
                throw new Error("Dữ liệu dự án hoặc công việc không hợp lệ.");
            }

            tasks = tasksResponse.data;
            projectName.textContent = `Dự án: ${project.name}`;

            try {
                const membersResponse = await API.get(
                    `/projects/${encodeURIComponent(projectId)}/members`
                );
                if (!Array.isArray(membersResponse?.data)) {
                    throw new Error("Danh sách thành viên từ máy chủ không hợp lệ.");
                }
                members = membersResponse.data;
                membersLoaded = true;
            } catch (error) {
                if (error.status === 401) return;
                membersError = error.message || "Không thể tải danh sách thành viên.";
            }

            renderBoard();
            if (project.archived_at) {
                showMessage("Dự án đã lưu trữ: bảng chỉ xem, không thể chỉnh sửa.");
            } else if (!canCreate()) {
                showMessage("Bạn có quyền VIEWER: chỉ có thể xem công việc.");
            } else if (membersError) {
                showMessage(`Không tải được danh sách thành viên để phân công: ${membersError}`, "error");
            } else {
                showMessage("");
            }
        } catch (error) {
            if (error.status === 401) return;
            projectName.textContent = "Không tải được dự án.";
            showMessage(error.message || "Không tải được bảng công việc.", "error");
            board.querySelectorAll("[data-cards]").forEach(cards => {
                cards.innerHTML = '<p class="kanban-empty">Không tải được công việc</p>';
            });
        }
    }

    function memberOptions(selectedId) {
        const options = members
            .filter(member => ["OWNER", "MEMBER"].includes(member.role))
            .map(member => `
                <option
                    value="${esc(member.user_id)}"
                    ${String(member.user_id) === String(selectedId ?? "") ? "selected" : ""}
                >${esc(member.display_name)} (${esc(member.role)})</option>
            `);

        if (
            selectedId != null &&
            selectedId !== "" &&
            !members.some(member => String(member.user_id) === String(selectedId))
        ) {
            options.push(
                `<option value="${esc(selectedId)}" selected>Thành viên hiện tại (#${esc(selectedId)})</option>`
            );
        }

        return [
            '<option value="">Chưa phân công</option>',
            ...options
        ].join("");
    }

    function openModal(html) {
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";
        backdrop.innerHTML = `<div class="modal kanban-modal" role="dialog" aria-modal="true">${html}</div>`;

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
        return { element: backdrop.firstElementChild, close };
    }

    function renderSubtasks(parentTask, list) {
        const subtasks = tasks.filter(
            task => String(task.parent_id) === String(parentTask.id)
        );

        if (!subtasks.length) {
            list.innerHTML = '<li class="subtask-empty">Chưa có subtask.</li>';
            return;
        }

        list.innerHTML = subtasks.map(task => `
            <li class="subtask-item">
                <label>
                    <input
                        type="checkbox"
                        data-subtask-id="${esc(task.id)}"
                        ${task.status === "DONE" ? "checked" : ""}
                        ${canEdit() && !task.archived_at ? "" : "disabled"}
                    >
                    <span class="${task.status === "DONE" ? "is-done" : ""}">${esc(task.title)}</span>
                </label>
            </li>
        `).join("");

        list.querySelectorAll("[data-subtask-id]").forEach(input => {
            input.addEventListener("change", async () => {
                const task = taskById(input.dataset.subtaskId);
                if (!task) return;
                input.disabled = true;

                try {
                    const response = await API.patch(
                        `/tasks/${encodeURIComponent(task.id)}/status`,
                        {
                            status: input.checked ? "DONE" : "TODO",
                            version: task.version
                        }
                    );
                    saveTask(response?.data);
                    renderBoard();
                    renderSubtasks(parentTask, list);
                } catch (error) {
                    input.checked = task.status === "DONE";
                    input.disabled = false;
                    if (error.status === 401) return;
                    if (error.status === 409) {
                        showTaskMessage(
                            `Subtask đã được người khác cập nhật. ${error.message || "Tải lại dữ liệu trước khi thử lại."}`,
                            "error"
                        );
                        await reloadTasksAfterConflict();
                        renderSubtasks(parentTask, list);
                        return;
                    }
                    showTaskMessage(error.message || "Không thể cập nhật subtask.", "error");
                }
            });
        });
    }

    function showTaskMessage(text, type = "") {
        const box = document.querySelector(".kanban-modal [data-task-message]");
        if (!box) return;
        box.textContent = text || "";
        box.className = `form-banner${type ? ` ${type}` : ""}`;
        box.hidden = !text;
    }

    async function reloadTasksAfterConflict() {
        try {
            await refreshTasks();
        } catch (error) {
            showTaskMessage(
                `${error.message || "Không thể tải lại công việc."} Hãy đóng cửa sổ và tải lại bảng.`,
                "error"
            );
        }
    }

    async function openTaskModal(task = null) {
        const isNew = !task;
        const editable = canEdit();
        const creatable = canCreate();
        const assignedId = task?.assignee_id ?? "";
        const subtasksSection = isNew ? "" : `
            <section class="task-subtasks" aria-labelledby="subtasks-heading">
                <div class="subtask-heading">
                    <h3 id="subtasks-heading">Subtask</h3>
                    <span class="kanban-version">Tối đa một cấp</span>
                </div>
                <ul class="subtask-list" data-subtask-list></ul>
                ${
                    creatable && !task.archived_at
                        ? `
                            <form class="subtask-add-form" data-subtask-form>
                                <label class="sr-only" for="new-subtask-title">Tên subtask</label>
                                <input
                                    id="new-subtask-title"
                                    name="title"
                                    maxlength="200"
                                    placeholder="Thêm subtask nhanh..."
                                    required
                                >
                                <button type="submit" class="btn btn-small">Thêm</button>
                            </form>
                        `
                        : ""
                }
            </section>
        `;

        const modal = openModal(`
            <div class="kanban-modal-heading">
                <h2>${isNew ? "Tạo task mới" : "Chi tiết task"}</h2>
                <button type="button" class="modal-close" data-close aria-label="Đóng">×</button>
            </div>
            ${
                !isNew
                    ? `<p class="kanban-version">Trạng thái: ${esc(task.status)} · Phiên bản ${esc(task.version)}</p>`
                    : ""
            }
            <div class="form-banner" data-task-message role="alert" hidden></div>
            ${
                membersError
                    ? `<p class="kanban-field-hint">${esc(membersError)} Task sẽ được lưu mà không thay đổi người phụ trách.</p>`
                    : ""
            }
            <form class="form-grid kanban-task-form" data-task-form>
                <label>
                    Tiêu đề *
                    <input
                        name="title"
                        value="${esc(task?.title || "")}"
                        maxlength="200"
                        required
                        ${editable ? "" : "disabled"}
                    >
                </label>
                <label>
                    Mô tả
                    <textarea
                        name="description"
                        maxlength="5000"
                        rows="4"
                        ${editable ? "" : "disabled"}
                    >${esc(task?.description || "")}</textarea>
                </label>
                <div class="row2">
                    <label>
                        Hạn hoàn thành
                        <input
                            type="date"
                            name="due_date"
                            value="${esc(task?.due_date || "")}"
                            ${editable ? "" : "disabled"}
                        >
                    </label>
                    <label>
                        Người phụ trách
                        <select
                            name="assignee_id"
                            ${editable && membersLoaded ? "" : "disabled"}
                        >${memberOptions(assignedId)}</select>
                    </label>
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn" data-close>Đóng</button>
                    ${
                        isNew
                            ? creatable
                                ? '<button type="submit" class="btn btn-primary">Tạo task</button>'
                                : ""
                            : '<button type="submit" class="btn btn-primary">Lưu thay đổi</button>'
                    }
                </div>
            </form>
            ${subtasksSection}
        `);

        modal.element.querySelectorAll("[data-close]").forEach(button => {
            button.addEventListener("click", modal.close);
        });

        const taskForm = modal.element.querySelector("[data-task-form]");
        taskForm.addEventListener("submit", async event => {
            event.preventDefault();
            if (isNew ? !canCreate() : !canEdit()) {
                showTaskMessage(
                    project?.archived_at
                        ? "Dự án đã lưu trữ, không thể chỉnh sửa."
                        : "Bạn không có quyền chỉnh sửa task.",
                    "error"
                );
                return;
            }

            const title = taskForm.elements.title.value.trim();
            if (!title) {
                showTaskMessage("Tiêu đề task không được để trống.", "error");
                taskForm.elements.title.focus();
                return;
            }

            const payload = {
                title,
                description: taskForm.elements.description.value.trim() || null,
                due_date: taskForm.elements.due_date.value || null
            };
            if (membersLoaded) {
                payload.assignee_id = taskForm.elements.assignee_id.value
                    ? Number(taskForm.elements.assignee_id.value)
                    : null;
            }
            if (!isNew) payload.version = task.version;

            const submit = taskForm.querySelector('[type="submit"]');
            submit.disabled = true;
            showTaskMessage("");

            try {
                const response = isNew
                    ? await API.post(
                        `/projects/${encodeURIComponent(projectId)}/tasks`,
                        payload
                    )
                    : await API.patch(
                        `/tasks/${encodeURIComponent(task.id)}`,
                        payload
                    );

                if (!response?.data || response.data.id == null) {
                    throw new Error("Máy chủ trả về task không hợp lệ.");
                }
                saveTask(response.data);
                renderBoard();
                modal.close();
                toast(isNew ? "Đã tạo task." : "Đã cập nhật task.", "success");
            } catch (error) {
                if (error.status === 401) return;
                submit.disabled = false;
                if (error.status === 409 && !isNew) {
                    showTaskMessage(
                        `Xung đột phiên bản (409): ${error.message || "Task đã được người khác cập nhật."} Thay đổi của bạn chưa được lưu. Tải lại bảng rồi mở task mới nhất.`,
                        "error"
                    );
                    return;
                }
                showTaskMessage(error.message || "Không thể lưu task.", "error");
            }
        });

        if (!isNew) {
            const subtaskList = modal.element.querySelector("[data-subtask-list]");
            renderSubtasks(task, subtaskList);

            const subtaskForm = modal.element.querySelector("[data-subtask-form]");
            if (subtaskForm) {
                subtaskForm.addEventListener("submit", async event => {
                    event.preventDefault();
                    const titleInput = subtaskForm.elements.title;
                    const title = titleInput.value.trim();
                    if (!title) return;

                    const submit = subtaskForm.querySelector('[type="submit"]');
                    submit.disabled = true;
                    showTaskMessage("");

                    try {
                        const response = await API.post(
                            `/tasks/${encodeURIComponent(task.id)}/subtasks`,
                            { title }
                        );
                        if (!response?.data || response.data.id == null) {
                            throw new Error("Máy chủ trả về subtask không hợp lệ.");
                        }
                        saveTask(response.data);
                        renderBoard();
                        renderSubtasks(task, subtaskList);
                        subtaskForm.reset();
                    } catch (error) {
                        if (error.status === 401) return;
                        showTaskMessage(error.message || "Không thể thêm subtask.", "error");
                    } finally {
                        submit.disabled = false;
                    }
                });
            }
        }

        const titleInput = taskForm.elements.title;
        if (editable) titleInput.focus();
    }

    async function moveTask(task, status) {
        if (!canEdit() || !task || task.status === status) return;

        try {
            const response = await API.patch(
                `/tasks/${encodeURIComponent(task.id)}`,
                { status, version: task.version }
            );
            if (!response?.data) {
                throw new Error("Máy chủ trả về task không hợp lệ.");
            }
            saveTask(response.data);
            renderBoard();
            showMessage(`Đã chuyển task sang ${status}.`, "success");
        } catch (error) {
            if (error.status === 401) return;
            if (error.status === 409) {
                showMessage(
                    `Xung đột phiên bản (409): ${error.message || "Task đã được người khác cập nhật."} Đang tải lại bảng.`,
                    "error"
                );
                try {
                    await refreshTasks();
                } catch (reloadError) {
                    showMessage(reloadError.message || "Không tải lại được bảng.", "error");
                }
                return;
            }
            showMessage(error.message || "Không thể đổi trạng thái task.", "error");
        }
    }

    board.addEventListener("dragstart", event => {
        const card = event.target.closest(".kanban-task");
        if (!canEdit() || !card) return;

        draggedTaskId = card.dataset.taskId;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", draggedTaskId);
        card.classList.add("is-dragging");
    });

    board.addEventListener("dragend", event => {
        const card = event.target.closest(".kanban-task");
        if (card) card.classList.remove("is-dragging");
        draggedTaskId = "";
        board.querySelectorAll(".lane.kanban-drop-target").forEach(lane => {
            lane.classList.remove("kanban-drop-target");
        });
    });

    board.querySelectorAll(".lane").forEach(lane => {
        lane.addEventListener("dragover", event => {
            if (!canEdit() || !draggedTaskId || !lane.dataset.status) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            lane.classList.add("kanban-drop-target");
        });

        lane.addEventListener("dragleave", event => {
            if (!lane.contains(event.relatedTarget)) {
                lane.classList.remove("kanban-drop-target");
            }
        });

        lane.addEventListener("drop", async event => {
            if (!canEdit() || !lane.dataset.status) return;
            event.preventDefault();
            lane.classList.remove("kanban-drop-target");
            const taskId = event.dataTransfer.getData("text/plain") || draggedTaskId;
            const task = taskById(taskId);
            await moveTask(task, lane.dataset.status);
        });
    });

    newTaskButton.addEventListener("click", () => openTaskModal());

    function start() {
        loadWorkspace();
    }

    if (!window.PulseAuth || window.PulseAuth.status === "authenticated") {
        start();
    }
    window.addEventListener("pulse:auth-changed", event => {
        if (event.detail?.status === "authenticated") start();
    });
})();
