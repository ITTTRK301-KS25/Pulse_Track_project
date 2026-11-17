
"use strict";

(function () {
    const DRAFT_PATH = "/ai/breakdown/drafts";

    function getAPI() {
        const api = window.PulseAPI;

        if (!api) {
            throw new Error("Chưa khởi tạo PulseAPI.");
        }

        return api;
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]);
    }

    function errorMessage(error) {
        if (error?.status === 401) {
            return "Phiên đăng nhập đã hết hạn.";
        }

        if (error?.status === 403) {
            return "Bạn không có quyền sử dụng AI Breakdown.";
        }

        if (error?.status === 404) {
            return "Backend chưa hỗ trợ API AI Breakdown hoặc đường dẫn chưa đúng.";
        }

        if (error?.status === 409) {
            return "Bản nháp đã thay đổi. Vui lòng kiểm tra lại.";
        }

        if (error?.status === 429) {
            return "AI đang quá tải. Vui lòng thử lại sau.";
        }

        return error?.message || "Có lỗi xảy ra. Vui lòng thử lại.";
    }

    function normalizeResponse(response) {
        const data = response?.data ?? response;

        if (!Array.isArray(data?.subtasks)) {
            throw new Error(
                "Dữ liệu AI trả về không có danh sách Subtask hợp lệ."
            );
        }

        const draftId = data.draft_id ?? data.id;

        if (draftId == null) {
            throw new Error("Backend không trả về mã bản nháp AI.");
        }

        return {
            draftId,
            subtasks: data.subtasks.map(item => ({
                title: String(item.title ?? "").trim(),
                description: String(item.description ?? "").trim()
            }))
        };
    }

    function mount({ task, project, container, onApproved }) {
        if (!task || !project || !container) return;

        const role = project.my_role || project.role;

        if (
            !["OWNER", "MEMBER"].includes(role) ||
            project.archived_at ||
            task.archived_at ||
            task.parent_id != null
        ) {
            return;
        }

        const section = container.querySelector(".task-subtasks");

        if (!section) return;

        if (section.querySelector(".ai-breakdown-trigger")) {
            return;
        }

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-primary ai-breakdown-trigger";
        button.textContent = "✦ Phân rã với AI";

        section.appendChild(button);

        button.addEventListener("click", () => {
            openBreakdown(task, onApproved);
        });
    }

    function openBreakdown(task, onApproved) {
        const backdrop = document.createElement("div");
        backdrop.className = "ai-breakdown-backdrop";

        backdrop.innerHTML = `
            <section
                class="ai-breakdown-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="ai-breakdown-title"
            >
                <header class="ai-studio-header">
                    <div class="ai-studio-brand">
                        <div class="ai-studio-logo">✦</div>

                        <div>
                            <h2 id="ai-breakdown-title">
                                AI Breakdown Studio
                            </h2>

                            <p>
                                Trợ lý phân rã công việc thông minh
                            </p>
                        </div>
                    </div>

                    <button
                        type="button"
                        class="ai-studio-close"
                        data-close
                        aria-label="Đóng"
                    >×</button>
                </header>

                <div class="ai-studio-task">
                    <div class="ai-studio-task-icon">☷</div>

                    <div class="ai-studio-task-info">
                        <span>CÔNG VIỆC ĐANG PHÂN TÍCH</span>

                        <h3>${escapeHTML(task.title)}</h3>

                        <p>
                            ${escapeHTML(
                                task.description ||
                                "Chưa có mô tả công việc."
                            )}
                        </p>
                    </div>

                    <div class="ai-studio-sparkles">✦</div>
                </div>

                <nav
                    class="ai-studio-steps"
                    aria-label="Các bước phân rã công việc"
                >
                    <button
                        type="button"
                        class="ai-studio-step is-active"
                        data-step="1"
                        aria-current="step"
                    >
                        <span class="ai-step-icon">◈</span>

                        <span class="ai-step-text">
                            <strong>1. Phân tích</strong>
                            <small>Hiểu nội dung Task</small>
                        </span>
                    </button>

                    <button
                        type="button"
                        class="ai-studio-step"
                        data-step="2"
                        disabled
                    >
                        <span class="ai-step-icon">☷</span>

                        <span class="ai-step-text">
                            <strong>2. Đề xuất</strong>
                            <small>Chỉnh sửa Subtask</small>
                        </span>
                    </button>

                    <button
                        type="button"
                        class="ai-studio-step"
                        data-step="3"
                        disabled
                    >
                        <span class="ai-step-icon">✓</span>

                        <span class="ai-step-text">
                            <strong>3. Phê duyệt</strong>
                            <small>Xác nhận tạo</small>
                        </span>
                    </button>
                </nav>

                <div
                    class="ai-studio-message"
                    data-message
                    role="status"
                    aria-live="polite"
                    hidden
                ></div>

                <section class="ai-studio-content" data-panel="1">
                    <p class="ai-studio-description">
                        AI sẽ phân tích công việc và đề xuất các Subtask cụ thể để bạn dễ triển khai,phân công và theo dõi tiến độ.
                    </p>

                    <button
                        type="button"
                        class="ai-studio-primary"
                        data-generate
                    >
                        ✦ Bắt đầu phân rã với AI
                        <span>→</span>
                    </button>

                    <p class="ai-studio-note">
                        Các Subtask chỉ được tạo sau khi bạn xác nhận.
                    </p>
                </section>

                <section
                    class="ai-studio-content"
                    data-panel="2"
                    hidden
                >
                    <div class="ai-studio-section-heading">
                        <div>
                            <h3>Subtask AI đề xuất</h3>
                            <p>
                                Chỉnh sửa danh sách trước khi phê duyệt.
                            </p>
                        </div>

                        <span data-count>0 Subtask</span>
                    </div>

                    <div class="ai-studio-list" data-list></div>

                    <button
                        type="button"
                        class="ai-studio-add"
                        data-add
                    >
                        + Thêm Subtask
                    </button>

                    <div class="ai-studio-actions">
                        <button
                            type="button"
                            class="ai-studio-secondary"
                            data-discard
                        >
                            Hủy bản nháp
                        </button>

                        <button
                            type="button"
                            class="ai-studio-primary"
                            data-next
                        >
                            Tiếp tục phê duyệt →
                        </button>
                    </div>
                </section>

                <section
                    class="ai-studio-content"
                    data-panel="3"
                    hidden
                >
                    <div class="ai-studio-section-heading">
                        <div>
                            <h3>Kiểm tra và phê duyệt</h3>
                            <p>
                                Xem lại các Subtask trước khi tạo.
                            </p>
                        </div>

                        <span data-review-count>0 Subtask</span>
                    </div>

                    <div
                        class="ai-studio-review"
                        data-review
                    ></div>

                    <p class="ai-studio-warning">
                        Sau khi xác nhận, các Subtask sẽ được
                        tạo vào công việc hiện tại.
                    </p>

                    <div class="ai-studio-actions">
                        <button
                            type="button"
                            class="ai-studio-secondary"
                            data-back
                        >
                            ← Quay lại chỉnh sửa
                        </button>

                        <button
                            type="button"
                            class="ai-studio-primary"
                            data-approve
                        >
                            ✓ Xác nhận tạo Subtask
                        </button>
                    </div>
                </section>

                <div class="ai-studio-loading" data-loading hidden>
                    <span class="ai-studio-spinner"></span>

                    <strong>AI đang phân tích công việc...</strong>

                    <p>
                        Vui lòng chờ trong khi hệ thống
                        tạo danh sách Subtask đề xuất.
                    </p>
                </div>
            </section>
        `;

        document.body.appendChild(backdrop);

        const dialog = backdrop.querySelector(".ai-breakdown-dialog");
        const message = dialog.querySelector("[data-message]");
        const loading = dialog.querySelector("[data-loading]");
        const list = dialog.querySelector("[data-list]");
        const review = dialog.querySelector("[data-review]");
        const stepButtons = Array.from(
            dialog.querySelectorAll("[data-step]")
        );

        const panels = Array.from(
            dialog.querySelectorAll("[data-panel]")
        );

        const previousFocus = document.activeElement;

        let currentStep = 1;
        let unlockedStep = 1;
        let draftId = null;
        let subtasks = [];
        let busy = false;
        let approvalKey = null;

        function showMessage(text, isError = false) {
            message.textContent = text || "";
            message.hidden = !text;
            message.classList.toggle("is-error", isError);
        }

        function setBusy(value) {
            busy = value;

            dialog.querySelectorAll("button").forEach(button => {
                button.disabled = value;
            });

            if (!value) {
                updateSteps();
            }
        }

        function updateSteps() {
            stepButtons.forEach(button => {
                const number = Number(button.dataset.step);

                button.classList.toggle(
                    "is-active",
                    number === currentStep
                );

                button.classList.toggle(
                    "is-completed",
                    number < currentStep
                );

                button.disabled = busy || number > unlockedStep;

                if (number === currentStep) {
                    button.setAttribute("aria-current", "step");
                } else {
                    button.removeAttribute("aria-current");
                }
            });
        }

        function changeStep(step) {
            if (busy || step > unlockedStep || step < 1) {
                return;
            }

            if (currentStep === 2) {
                subtasks = readSubtasks();
            }

            currentStep = step;

            panels.forEach(panel => {
                panel.hidden =
                    Number(panel.dataset.panel) !== currentStep;
            });

            showMessage("");

            if (currentStep === 2) {
                renderSubtasks();
            }

            if (currentStep === 3) {
                renderReview();
            }

            updateSteps();
        }

        function close() {
            if (busy) return;

            backdrop.remove();
            document.removeEventListener("keydown", onKeyDown);

            if (previousFocus?.isConnected) {
                previousFocus.focus();
            }
        }

        function onKeyDown(event) {
            if (event.key === "Escape") {
                close();
            }
        }

        document.addEventListener("keydown", onKeyDown);

        dialog.querySelector("[data-close]").addEventListener(
            "click",
            close
        );

        stepButtons.forEach(button => {
            button.addEventListener("click", () => {
                changeStep(Number(button.dataset.step));
            });
        });

        function readSubtasks() {
            return Array.from(
                list.querySelectorAll(".ai-studio-item")
            ).map(item => ({
                title: item.querySelector("[data-title]").value.trim(),
                description: item.querySelector(
                    "[data-description]"
                ).value.trim()
            }));
        }

        function renderSubtasks() {
            list.innerHTML = subtasks.map((item, index) => `
                <article class="ai-studio-item">
                    <div class="ai-studio-item-heading">
                        <strong>Subtask ${index + 1}</strong>

                        <button
                            type="button"
                            class="ai-studio-remove"
                            data-remove="${index}"
                        >
                            Xóa
                        </button>
                    </div>

                    <label>
                        Tên Subtask
                        <input
                            data-title
                            maxlength="200"
                            value="${escapeHTML(item.title)}"
                        >
                    </label>

                    <label>
                        Mô tả
                        <textarea
                            data-description
                            rows="2"
                            maxlength="5000"
                        >${escapeHTML(item.description)}</textarea>
                    </label>
                </article>
            `).join("");

            dialog.querySelector("[data-count]").textContent =
                `${subtasks.length} Subtask`;

            list.querySelectorAll("[data-remove]").forEach(button => {
                button.addEventListener("click", () => {
                    subtasks = readSubtasks();
                    subtasks.splice(Number(button.dataset.remove), 1);
                    renderSubtasks();
                });
            });
        }

        function renderReview() {
            review.innerHTML = subtasks.map((item, index) => `
                <div class="ai-studio-review-item">
                    <span class="ai-studio-review-number">
                        ${index + 1}
                    </span>

                    <div>
                        <strong>${escapeHTML(item.title)}</strong>

                        <p>
                            ${escapeHTML(
                                item.description || "Không có mô tả."
                            )}
                        </p>
                    </div>
                </div>
            `).join("");

            dialog.querySelector("[data-review-count]").textContent =
                `${subtasks.length} Subtask`;
        }

        dialog.querySelector("[data-generate]").addEventListener(
            "click",
            async () => {
                if (busy) return;

                setBusy(true);
                showMessage("");
                loading.hidden = false;

                try {
                    const response = await getAPI().post(
                        `/tasks/${encodeURIComponent(task.id)}/ai/breakdown`,
                        {},
                        { timeout: 60000 }
                    );

                    const result = normalizeResponse(response);

                    draftId = result.draftId;
                    subtasks = result.subtasks;
                    approvalKey = null;

                    unlockedStep = 2;

                    loading.hidden = true;
                    setBusy(false);
                    changeStep(2);
                } catch (error) {
                    loading.hidden = true;
                    showMessage(errorMessage(error), true);
                    setBusy(false);
                }
            }
        );

        dialog.querySelector("[data-add]").addEventListener(
            "click",
            () => {
                subtasks = readSubtasks();

                subtasks.push({
                    title: "",
                    description: ""
                });

                renderSubtasks();

                const inputs = list.querySelectorAll("[data-title]");
                inputs[inputs.length - 1]?.focus();
            }
        );

        dialog.querySelector("[data-next]").addEventListener(
            "click",
            () => {
                subtasks = readSubtasks();

                if (
                    !subtasks.length ||
                    subtasks.some(item => !item.title)
                ) {
                    showMessage(
                        "Cần ít nhất một Subtask và tất cả phải có tên.",
                        true
                    );
                    return;
                }

                unlockedStep = 3;
                changeStep(3);
            }
        );

        dialog.querySelector("[data-back]").addEventListener(
            "click",
            () => changeStep(2)
        );

        dialog.querySelector("[data-discard]").addEventListener(
            "click",
            async () => {
                if (busy || draftId == null) return;

                setBusy(true);
                showMessage("");

                try {
                    await getAPI().post(
                        `${DRAFT_PATH}/${encodeURIComponent(draftId)}/discard`,
                        { draft_id: draftId }
                    );

                    setBusy(false);
                    close();
                } catch (error) {
                    showMessage(errorMessage(error), true);
                    setBusy(false);
                }
            }
        );

        dialog.querySelector("[data-approve]").addEventListener(
            "click",
            async () => {
                if (busy || draftId == null) return;

                if (
                    !subtasks.length ||
                    subtasks.some(item => !item.title)
                ) {
                    showMessage(
                        "Danh sách Subtask không hợp lệ.",
                        true
                    );
                    return;
                }

                setBusy(true);
                showMessage("");

                try {
                    await getAPI().patch(
                        `${DRAFT_PATH}/${encodeURIComponent(draftId)}`,
                        { subtasks }
                    );

                    if (!approvalKey) {
                        approvalKey = window.crypto?.randomUUID
                            ? window.crypto.randomUUID()
                            : `${Date.now()}-${Math.random()}`;
                    }

                    await getAPI().post(
                        `${DRAFT_PATH}/${encodeURIComponent(draftId)}/approve`,
                        { draft_id: draftId },
                        {
                            headers: {
                                "Idempotency-Key": approvalKey
                            },
                            timeout: 30000
                        }
                    );

                    if (typeof onApproved === "function") {
                        await onApproved();
                    }

                    setBusy(false);
                    close();
                } catch (error) {
                    showMessage(errorMessage(error), true);
                    setBusy(false);
                }
            }
        );

        updateSteps();
        dialog.querySelector("[data-generate]")?.focus();
    }

    window.PulseAIBreakdown = Object.freeze({ mount });
})();
