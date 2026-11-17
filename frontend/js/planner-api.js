
"use strict";

(function () {
    function api() {
        if (!window.PulseAPI) {
            throw new Error("Chưa khởi tạo PulseAPI.");
        }
        return window.PulseAPI;
    }

    function draftPath(id) {
        if (id === null || id === undefined || id === "") {
            throw new Error("Thiếu mã bản nháp AI.");
        }

        return `/ai/planner/drafts/${encodeURIComponent(String(id))}`;
    }

    function generate({ projectId, goal, scope }) {
        const id = Number(projectId);

        if (!Number.isSafeInteger(id) || id <= 0) {
            throw new Error("Mã dự án không hợp lệ.");
        }

        if (!String(goal || "").trim()) {
            throw new Error("Vui lòng nhập mục tiêu dự án.");
        }

        if (!String(scope || "").trim()) {
            throw new Error("Vui lòng nhập phạm vi dự án.");
        }

        return api().post("/ai/planner", {
            project_id: id,
            goal: String(goal).trim(),
            scope: String(scope).trim()
        }, {
            timeout: 60000
        });
    }

    function update({ draftId, suggestions }) {
        if (!Array.isArray(suggestions)) {
            throw new Error("Danh sách đề xuất không hợp lệ.");
        }

        return api().patch(draftPath(draftId), {
            suggestions
        });
    }

    function discard({ draftId }) {
        return api().post(
            `${draftPath(draftId)}/discard`,
            { draft_id: draftId }
        );
    }

    function approve({ draftId, idempotencyKey }) {
        if (!idempotencyKey) {
            throw new Error("Thiếu khóa chống gửi trùng.");
        }

        // Cách truyền Idempotency-Key cần Backend xác nhận.
        // Hiện dùng HTTP header; không đưa key vào JSON body.
        return api().post(
            `${draftPath(draftId)}/approve`,
            { draft_id: draftId },
            {
                headers: {
                    "Idempotency-Key": idempotencyKey
                },
                timeout: 30000
            }
        );
    }

    window.PulsePlannerAPI = Object.freeze({
        generate,
        update,
        discard,
        approve
    });
})();
