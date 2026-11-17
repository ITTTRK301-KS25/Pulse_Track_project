
"use strict";

(function () {
    const params = new URLSearchParams(location.search);
    const projectId = params.get("project");

    const $ = id => document.getElementById(id);

    const form = $("planner-form");
    if (!form) return;

    const goalInput = $("planner-goal");
    const scopeInput = $("planner-scope");
    const generateButton = $("planner-generate");
    const loadingBox = $("planner-loading");
    const draftBox = $("planner-draft");
    const taskList = $("planner-task-list");
    const taskCount = $("planner-draft-count");
    const approveButton = $("planner-approve");
    const cancelButton = $("planner-cancel");
    const messageBox = $("planner-message");
    const projectName = $("planner-project-name");
    const backLink = $("planner-back-link");
    const kanbanLink = $("planner-kanban-link");

    let project = null;
    let draftId = null;
    let suggestions = [];
    let busy = false;
    let started = false;
    let approvalKey = null;
    let approvalPending = false;

    const validProjectId =
        Number.isSafeInteger(Number(projectId)) &&
        Number(projectId) > 0;

    if (validProjectId) {
        const url =
            `kanban.html?project=${encodeURIComponent(projectId)}`;

        backLink.href = url;
        kanbanLink.href = url;
    }

    function showMessage(text, type = "") {
        messageBox.textContent = text;
        messageBox.className =
            `ai-message${type ? ` is-${type}` : ""}`;
        messageBox.hidden = !text;
    }

    function isOwner() {
        return Boolean(
            project &&
            !project.archived_at &&
            project.my_role === "OWNER"
        );
    }

    function setBusy(value) {
        busy = value;
        loadingBox.hidden = !value;

        goalInput.disabled = value || !isOwner() || draftId !== null;
        scopeInput.disabled = value || !isOwner() || draftId !== null;

        generateButton.disabled =
            value || !isOwner() || draftId !== null;

        approveButton.disabled =
            value || !isOwner() ||
            draftId === null || suggestions.length === 0;

        cancelButton.disabled = value || !isOwner() || draftId === null;

        taskList.querySelectorAll("input, textarea, button")
            .forEach(control => {
                control.disabled = value || !isOwner() || approvalPending;
            });
    }

    function getAPI() {
        if (!window.PulsePlannerAPI) {
            throw new Error("Chưa tải planner-api.js.");
        }

        return window.PulsePlannerAPI;
    }

    function unwrap(response) {
        return response?.data ?? response;
    }

    function errorText(error) {
        if (error.status === 403) {
            return "Bạn không có quyền thực hiện thao tác này.";
        }

        if (error.status === 409) {
            return "Bản nháp đã thay đổi trạng thái hoặc có xung đột. " +
                "Vui lòng kiểm tra lại trước khi tiếp tục.";
        }

        if (error.status === 429) {
            return "AI đang nhận quá nhiều yêu cầu. Vui lòng thử lại sau.";
        }

        if (error.status === 503) {
            return "Dịch vụ AI hiện không khả dụng.";
        }

        if (error.code === "REQUEST_ABORTED") {
            return "Yêu cầu quá thời gian chờ. " +
                "Hãy kiểm tra trạng thái trên Backend trước khi thử lại.";
        }

        return error.message || "Đã xảy ra lỗi không xác định.";
    }

    function readDraft(response) {
        const data = unwrap(response);

        if (
            !data ||
            data.draft_id === null ||
            data.draft_id === undefined ||
            !Array.isArray(data.suggestions)
        ) {
            throw new Error(
                "Phản hồi AI không đúng API Contract: " +
                "thiếu draft_id hoặc suggestions[]."
            );
        }

        if (!data.suggestions.every(
            item => item && typeof item === "object" &&
                !Array.isArray(item)
        )) {
            throw new Error("Danh sách AI đề xuất không hợp lệ.");
        }

        return data;
    }

    function createField(labelText, value, multiline, onChange) {
        const wrapper = document.createElement("div");
        wrapper.className = "ai-field";

        const label = document.createElement("label");
        label.textContent = labelText;

        const input = document.createElement(
            multiline ? "textarea" : "input"
        );

        if (!multiline) {
            input.type = "text";
        } else {
            input.rows = 3;
        }

        input.className = multiline
            ? "ai-task-description"
            : "ai-task-title";

        input.maxLength = multiline ? 5000 : 200;
        input.value = String(value ?? "");
        input.disabled = busy || !isOwner() || approvalPending;

        input.addEventListener("input", () => {
            onChange(input.value);
        });

        wrapper.append(label, input);
        return wrapper;
    }

    function renderSuggestions() {
        taskList.replaceChildren();

        taskCount.textContent =
            `${suggestions.length} công việc`;

        if (!suggestions.length) {
            const empty = document.createElement("p");
            empty.className = "ai-empty";
            empty.textContent =
                "Không còn công việc nào trong bản nháp.";
            taskList.appendChild(empty);
        }

        suggestions.forEach((item, index) => {
            const card = document.createElement("article");
            card.className = "ai-task-card";

            const top = document.createElement("div");
            top.className = "ai-task-top";

            const number = document.createElement("span");
            number.className = "ai-task-number";
            number.textContent = `Công việc ${index + 1}`;

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "ai-remove";
            remove.textContent = "Xóa";
            remove.disabled = busy || !isOwner() || approvalPending;

            remove.addEventListener("click", () => {
                if (busy || !isOwner() || approvalPending) return;

                suggestions.splice(index, 1);
                renderSuggestions();
            });

            top.append(number, remove);

            const titleField = createField(
                "Tiêu đề công việc *",
                item.title,
                false,
                value => {
                    item.title = value;
                }
            );

            const descriptionField = createField(
                "Mô tả công việc",
                item.description,
                true,
                value => {
                    item.description = value;
                }
            );

            card.append(top, titleField, descriptionField);
            taskList.appendChild(card);
        });

        setBusy(busy);
    }

    function validateSuggestions() {
        if (!suggestions.length) {
            throw new Error(
                "Cần ít nhất một công việc để phê duyệt."
            );
        }

        suggestions.forEach((item, index) => {
            const title = String(item.title ?? "").trim();

            if (!title) {
                throw new Error(
                    `Công việc ${index + 1} chưa có tiêu đề.`
                );
            }

            if (title.length > 200) {
                throw new Error(
                    `Tiêu đề công việc ${index + 1} quá dài.`
                );
            }
        });
    }

    function clearDraft() {
        draftId = null;
        suggestions = [];
        approvalKey = null;
        approvalPending = false;
        draftBox.hidden = true;
        setBusy(false);
    }

    async function loadProject() {
        if (!validProjectId) {
            showMessage(
                "Thiếu mã dự án hợp lệ. Hãy mở từ Kanban.",
                "error"
            );
            return;
        }

        try {
            const response = await window.PulseAPI.get(
                `/projects/${encodeURIComponent(projectId)}`
            );

            project = unwrap(response);

            if (!project || !project.id) {
                throw new Error("Không tìm thấy dự án.");
            }

            projectName.textContent =
                `Dự án: ${project.name || `#${projectId}`}`;

            if (!isOwner()) {
                showMessage(
                    "Chỉ OWNER của dự án đang hoạt động " +
                    "mới được sử dụng Trợ lý AI.",
                    "error"
                );
                setBusy(false);
                return;
            }

            showMessage("");
            setBusy(false);
        } catch (error) {
            showMessage(errorText(error), "error");
            setBusy(false);
        }
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        if (busy || !isOwner() || draftId !== null) return;

        const goal = goalInput.value.trim();
        const scope = scopeInput.value.trim();

        if (!goal || !scope) {
            showMessage(
                "Vui lòng nhập đầy đủ mục tiêu và phạm vi dự án.",
                "error"
            );
            return;
        }

        setBusy(true);
        showMessage("");

        try {
            const response = await getAPI().generate({
                projectId,
                goal,
                scope
            });

            const data = readDraft(response);

            draftId = data.draft_id;
            suggestions = data.suggestions.map(
                item => ({ ...item })
            );

            approvalKey = null;
            approvalPending = false;

            draftBox.hidden = false;
            renderSuggestions();

            showMessage(
                "AI đã tạo danh sách đề xuất. " +
                "Hãy kiểm tra trước khi phê duyệt.",
                "success"
            );
        } catch (error) {
            showMessage(errorText(error), "error");
        } finally {
            setBusy(false);
        }
    });

    cancelButton.addEventListener("click", async () => {
        if (busy || !isOwner() || draftId === null) return;

        if (approvalPending) {
            showMessage(
                "Lần phê duyệt trước chưa được xác nhận. " +
                "Hãy kiểm tra Backend trước khi hủy.",
                "error"
            );
            return;
        }

        if (!confirm("Bạn chắc chắn muốn hủy bản nháp AI?")) {
            return;
        }

        setBusy(true);
        showMessage("");

        try {
            await getAPI().discard({ draftId });

            clearDraft();
            showMessage("Đã hủy bản nháp AI.", "success");
        } catch (error) {
            showMessage(errorText(error), "error");
        } finally {
            setBusy(false);
        }
    });

    approveButton.addEventListener("click", async () => {
        if (busy || !isOwner() || draftId === null) return;

        try {
            validateSuggestions();
        } catch (error) {
            showMessage(error.message, "error");
            return;
        }

        if (!confirm(
            `Phê duyệt ${suggestions.length} công việc và tạo Task thật?`
        )) {
            return;
        }

        setBusy(true);
        showMessage("");

        try {
            const plannerAPI = getAPI();

            if (!approvalPending) {
                // Lưu nội dung người dùng đã chỉnh sửa.
                await plannerAPI.update({
                    draftId,
                    suggestions: suggestions.map(item => ({
                        ...item,
                        title: String(item.title).trim(),
                        description: String(
                            item.description ?? ""
                        ).trim()
                    }))
                });

                approvalKey = crypto.randomUUID();
                approvalPending = true;
            }

            // Chỉ Backend mới tạo Task thật.
            await plannerAPI.approve({
                draftId,
                idempotencyKey: approvalKey
            });

            clearDraft();

            showMessage(
                "Phê duyệt thành công. Đang mở Kanban...",
                "success"
            );

            location.assign(
                `kanban.html?project=${encodeURIComponent(projectId)}`
            );
        } catch (error) {
            if (approvalPending) {
                showMessage(
                    errorText(error) +
                    " Không chỉnh sửa hoặc hủy bản nháp lúc này. " +
                    "Nếu yêu cầu trước đã tới Backend, " +
                    "cần xác nhận trạng thái để tránh tạo trùng.",
                    "error"
                );
            } else {
                showMessage(errorText(error), "error");
            }
        } finally {
            setBusy(false);
        }
    });

    function start() {
        if (started) return;
        started = true;
        loadProject();
    }

    window.addEventListener("pulse:auth-changed", event => {
        if (event.detail?.status === "authenticated") {
            start();
        }
    });

    if (window.PulseAuth?.status === "authenticated") {
        start();
    }
})();
