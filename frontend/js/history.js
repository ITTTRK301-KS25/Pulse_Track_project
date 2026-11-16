
"use strict";

(function () {
    const API = window.PulseAPI;
    const TIME_ZONE = "Asia/Ho_Chi_Minh";
    const PAGE_SIZE = 50;

    const EVENT_NAMES = {
        CREATE: "Tạo công việc",
        STATUS_CHANGE: "Thay đổi trạng thái",
        DUE_CHANGE: "Thay đổi hạn hoàn thành",
        ASSIGNEE_CHANGE: "Thay đổi người phụ trách",
        PARENT_CHANGE: "Thay đổi công việc cha",
        ARCHIVE: "Lưu trữ công việc",
        RESTORE: "Khôi phục công việc",
        DETAIL_CHANGE: "Chỉnh sửa thông tin"
    };

    const FIELD_NAMES = {
        title: "Tiêu đề",
        description: "Mô tả",
        status: "Trạng thái",
        due_date: "Hạn hoàn thành",
        assignee_id: "Người phụ trách",
        parent_id: "Công việc cha",
        archived_at: "Thời gian lưu trữ"
    };

    const STATUS_NAMES = {
        TODO: "Sprint Backlog",
        IN_PROGRESS: "In Progress",
        DONE: "Done"
    };

    function createElement(tag, className, content) {
        const element = document.createElement(tag);

        if (className) element.className = className;

        if (content !== undefined && content !== null) {
            element.textContent = String(content);
        }

        return element;
    }

    function formatTime(value) {
        if (!value) return "Không rõ thời gian";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return "Thời gian không hợp lệ";
        }

        return new Intl.DateTimeFormat("vi-VN", {
            timeZone: TIME_ZONE,
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
        }).format(date);
    }

    function formatDate(value) {
        if (!value) return "Chưa đặt";

        const match = String(value).match(
            /^(\d{4})-(\d{2})-(\d{2})$/
        );

        if (match) {
            return `${match[3]}/${match[2]}/${match[1]}`;
        }

        return formatTime(value);
    }

    function formatValue(field, value) {
        if (value === null || value === undefined || value === "") {
            return "Chưa có";
        }

        if (field === "status") {
            return STATUS_NAMES[value] || String(value);
        }

        if (field === "due_date") {
            return formatDate(value);
        }

        if (field === "archived_at") {
            return formatTime(value);
        }

        if (field === "assignee_id") {
            return `Người dùng #${value}`;
        }

        if (field === "parent_id") {
            return `Task #${value}`;
        }

        if (typeof value === "object") {
            return JSON.stringify(value);
        }

        return String(value);
    }

    function getInitial(name) {
        const words = String(name || "")
            .trim()
            .split(/\s+/)
            .filter(Boolean);

        if (!words.length) return "?";

        return Array.from(words[words.length - 1])[0]
            .toLocaleUpperCase("vi-VN");
    }

    function getEventFields(event) {
        const before = event.before_value;
        const after = event.after_value;

        if (event.event_type === "CREATE") {
            return [];
        }

        if (
            !after ||
            typeof after !== "object" ||
            Array.isArray(after)
        ) {
            return [];
        }

        return Object.keys(after).map(field => ({
            field,
            before: before && typeof before === "object"
                ? before[field]
                : null,
            after: after[field]
        }));
    }

    function renderChanges(event) {
        const changes = createElement(
            "div",
            "history-changes"
        );

        const fields = getEventFields(event);

        if (event.event_type === "CREATE") {
            const title = event.after_value?.title;

            if (title) {
                changes.appendChild(
                    createElement(
                        "p",
                        "history-created-title",
                        `Công việc: ${title}`
                    )
                );
            }

            return changes;
        }

        if (!fields.length) {
            return changes;
        }

        fields.forEach(change => {
            const row = createElement(
                "div",
                "history-change-row"
            );

            const label = createElement(
                "span",
                "history-field",
                FIELD_NAMES[change.field] || change.field
            );

            const values = createElement(
                "div",
                "history-values"
            );

            const before = createElement(
                "span",
                "history-before",
                formatValue(change.field, change.before)
            );

            const arrow = createElement(
                "span",
                "history-arrow",
                "→"
            );

            const after = createElement(
                "span",
                "history-after",
                formatValue(change.field, change.after)
            );

            values.append(before, arrow, after);
            row.append(label, values);
            changes.appendChild(row);
        });

        return changes;
    }

    function renderEvent(event) {
        const item = createElement(
            "article",
            "history-item"
        );

        const marker = createElement(
            "span",
            "history-marker"
        );

        marker.setAttribute("aria-hidden", "true");

        const content = createElement(
            "div",
            "history-item-content"
        );

        const header = createElement(
            "div",
            "history-item-header"
        );

        const actorName = event.actor_name ||
            `Người dùng #${event.actor_id ?? "?"}`;

        const avatar = createElement(
            "span",
            "history-avatar",
            getInitial(actorName)
        );

        const actorInfo = createElement(
            "div",
            "history-actor-info"
        );

        const actor = createElement(
            "strong",
            "history-actor",
            actorName
        );

        const action = createElement(
            "span",
            "history-action",
            EVENT_NAMES[event.event_type] ||
                event.event_type ||
                "Thay đổi công việc"
        );

        actorInfo.append(actor, action);

        const time = createElement(
            "time",
            "history-time",
            formatTime(event.occurred_at)
        );

        if (event.occurred_at) {
            time.dateTime = event.occurred_at;
        }

        header.append(avatar, actorInfo, time);

        content.append(
            header,
            renderChanges(event)
        );

        item.append(marker, content);

        return item;
    }

    function mount(modal, options) {
        if (!modal || !options) return;

        const { projectId, taskId } = options;

        if (projectId == null || taskId == null) return;

        const endpoint =
            `/projects/${encodeURIComponent(projectId)}` +
            `/tasks/${encodeURIComponent(taskId)}/history`;

        const section = createElement(
            "section",
            "history-section"
        );

        section.setAttribute(
            "aria-label",
            "Lịch sử thay đổi công việc"
        );

        const heading = createElement(
            "div",
            "history-heading"
        );

        const title = createElement(
            "h3",
            "",
            "Lịch sử thay đổi"
        );

        const timezone = createElement(
            "span",
            "history-timezone",
            "Giờ Việt Nam (UTC+7)"
        );

        heading.append(title, timezone);

        const status = createElement(
            "p",
            "history-status"
        );

        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.hidden = true;

        const list = createElement(
            "div",
            "history-timeline"
        );

        const actions = createElement(
            "div",
            "history-actions"
        );

        const loadMore = createElement(
            "button",
            "btn history-load-more",
            "Tải thêm lịch sử"
        );

        loadMore.type = "button";
        loadMore.hidden = true;

        actions.appendChild(loadMore);
        section.append(heading, status, list, actions);

        let nextCursor = null;
        let loading = false;
        let loaded = false;
        let disposed = false;
        const seenEvents = new Set();

        function showStatus(text, isError = false) {
            status.textContent = text || "";
            status.hidden = !text;
            status.classList.toggle(
                "is-error",
                isError
            );
        }

        function showEmpty() {
            list.replaceChildren(
                createElement(
                    "p",
                    "history-empty",
                    "Chưa có lịch sử thay đổi."
                )
            );
        }

        function appendEvents(events) {
            if (!events.length) return;

            const empty = list.querySelector(".history-empty");

            if (empty) empty.remove();

            const fragment = document.createDocumentFragment();

            events.forEach(event => {
                const key = String(event.event_seq);

                if (seenEvents.has(key)) return;

                seenEvents.add(key);
                fragment.appendChild(renderEvent(event));
            });

            list.appendChild(fragment);
        }

        async function loadHistory(reset = false) {
            if (loading || disposed || !section.isConnected) {
                return;
            }

            if (!reset && loaded && nextCursor == null) {
                return;
            }

            loading = true;
            loadMore.disabled = true;
            loadMore.textContent = "Đang tải...";

            if (reset) {
                nextCursor = null;
                loaded = false;
                seenEvents.clear();
                list.replaceChildren();
            }

            showStatus("Đang tải lịch sử thay đổi...");

            try {
                if (!API) {
                    throw new Error(
                        "Chưa tải được HTTP client PulseAPI."
                    );
                }

                const params = new URLSearchParams({
                    limit: String(PAGE_SIZE)
                });

                if (nextCursor != null) {
                    params.set("cursor", String(nextCursor));
                }

                const response = await API.get(
                    `${endpoint}?${params.toString()}`
                );

                const data = response?.data;

                if (
                    !data ||
                    !Array.isArray(data.items)
                ) {
                    throw new Error(
                        "Dữ liệu lịch sử từ Backend không hợp lệ."
                    );
                }

                if (disposed || !section.isConnected) return;

                appendEvents(data.items);

                nextCursor = data.next_cursor ?? null;
                loaded = true;

                if (seenEvents.size === 0) {
                    showEmpty();
                }

                loadMore.hidden = nextCursor == null;
                showStatus("");
            } catch (error) {
                if (disposed || !section.isConnected) return;

                showStatus(
                    error.message ||
                        "Không thể tải lịch sử thay đổi.",
                    true
                );

                loadMore.hidden = true;

                const retry = createElement(
                    "button",
                    "btn history-retry",
                    "Thử lại"
                );

                retry.type = "button";

                retry.addEventListener("click", () => {
                    retry.remove();
                    loadHistory(!loaded);
                });

                status.appendChild(retry);
                status.hidden = false;
            } finally {
                loading = false;
                loadMore.disabled = false;
                loadMore.textContent = "Tải thêm lịch sử";
            }
        }

        loadMore.addEventListener("click", () => {
            loadHistory(false);
        });

        return {
            element: section,

            load() {
                if (!loaded) {
                    loadHistory(true);
                }
            },

            refresh() {
                loadHistory(true);
            },

            dispose() {
                disposed = true;
            }
        };
    }

    window.PulseHistory = Object.freeze({
        mount
    });
})();
