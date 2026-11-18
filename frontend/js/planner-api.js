
"use strict";

(function () {
    function api() {
        if (!window.PulseAPI) {
            throw new Error("Chưa khởi tạo PulseAPI.");
        }

        return window.PulseAPI;
    }

    function positiveId(value, fieldName) {
        const id = Number(value);

        if (!Number.isSafeInteger(id) || id <= 0) {
            throw new Error(`${fieldName} không hợp lệ.`);
        }

        return id;
    }

    function draftPath(draftId) {
        const id = positiveId(draftId, "Mã bản nháp AI");

        return `/ai/planner/drafts/${encodeURIComponent(id)}`;
    }

    function optionalVersion(value) {
        if (value === null || value === undefined || value === "") {
            return undefined;
        }

        return positiveId(value, "Phiên bản bản nháp");
    }

    function generate({ projectId, goal, scope = "" }) {
        const id = positiveId(projectId, "Mã dự án");
        const cleanGoal = String(goal || "").trim();
        const cleanScope = String(scope || "").trim();

        if (cleanGoal.length < 10 || cleanGoal.length > 2000) {
            throw new Error(
                "Mục tiêu dự án phải từ 10 đến 2000 ký tự."
            );
        }

        if (cleanScope.length > 1000) {
            throw new Error(
                "Phạm vi dự án không được vượt quá 1000 ký tự."
            );
        }

        if (cleanGoal.length + cleanScope.length > 3000) {
            throw new Error(
                "Tổng mục tiêu và phạm vi không được vượt quá 3000 ký tự."
            );
        }

        return api().post(
            "/ai/planner",
            {
                project_id: id,
                goal: cleanGoal,
                scope: cleanScope
            },
            {
                timeout: 60000
            }
        );
    }

    function update({ draftId, suggestions, version }) {
        if (
            !Array.isArray(suggestions) ||
            suggestions.length < 1 ||
            suggestions.length > 20
        ) {
            throw new Error(
                "Bản nháp phải có từ 1 đến 20 công việc."
            );
        }

        const cleanSuggestions = suggestions.map((item, index) => {
            const title = String(item?.title || "").trim();

            if (!title || title.length > 200) {
                throw new Error(
                    `Tiêu đề công việc ${index + 1} phải từ 1 đến 200 ký tự.`
                );
            }

            const description =
                item?.description == null
                    ? null
                    : String(item.description).trim() || null;

            if (description && description.length > 5000) {
                throw new Error(
                    `Mô tả công việc ${index + 1} vượt quá 5000 ký tự.`
                );
            }

            return {
                title,
                description,
                due_date: item?.due_date || null
            };
        });

        const body = {
            suggestions: cleanSuggestions
        };

        const draftVersion = optionalVersion(version);

        if (draftVersion !== undefined) {
            body.version = draftVersion;
        }

        return api().patch(
            draftPath(draftId),
            body
        );
    }

    function discard({ draftId }) {
        return api().post(
            `${draftPath(draftId)}/discard`
        );
    }

    function approve({
        draftId,
        idempotencyKey,
        expectedVersion
    }) {
        if (
            typeof idempotencyKey !== "string" ||
            !/^[A-Za-z0-9._:-]{8,160}$/.test(idempotencyKey)
        ) {
            throw new Error(
                "Khóa chống gửi trùng không hợp lệ."
            );
        }

        const id = positiveId(draftId, "Mã bản nháp AI");

        const body = {
            draft_id: id
        };

        const version = optionalVersion(expectedVersion);

        if (version !== undefined) {
            body.expected_version = version;
        }

        return api().post(
            `${draftPath(id)}/approve`,
            body,
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
