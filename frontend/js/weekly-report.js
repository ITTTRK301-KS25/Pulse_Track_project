
"use strict";

(function () {
    const API = window.PulseAPI;
    const $ = id => document.getElementById(id);

    const form = $("report-form");
    const projectSelect = $("report-project");
    const weekSelect = $("report-week");
    const previewButton = $("report-preview-button");
    const previewSection = $("report-preview");
    const metricsContainer = $("report-metrics");
    const aiContent = $("report-ai-content");
    const periodText = $("report-period");
    const messageBox = $("report-message");
    const saveButton = $("report-save-button");

    const overlay = $("report-confirm-overlay");
    const cancelSave = $("report-cancel-save");
    const confirmSave = $("report-confirm-save");

    if (!API || !form) return;

    const TIME_ZONE = "Asia/Ho_Chi_Minh";

    const METRIC_CODES = [
        "MET-01",
        "MET-02",
        "MET-03",
        "MET-04",
        "MET-05",
        "MET-06"
    ];

    let projects = [];
    let previewData = null;
    let previewId = null;
    let previewProjectId = null;
    let previewWeekStart = null;
    let busy = false;
    let saved = false;
    let saveAttempted = false;

    function showMessage(message, type = "info") {
        messageBox.textContent = message;
        messageBox.dataset.type = type;
        messageBox.hidden = !message;
    }

    function unwrap(response) {
        return response?.data ?? response;
    }

    function errorText(error) {
        if (error.status === 401) {
            return "Phiên đăng nhập đã hết hạn.";
        }

        if (error.status === 403) {
            return "Bạn không có quyền thực hiện thao tác này.";
        }

        if (error.status === 404) {
            return "API báo cáo chưa tồn tại hoặc không tìm thấy dữ liệu.";
        }

        if (error.status === 409) {
            return "Báo cáo đã tồn tại hoặc dữ liệu bị xung đột.";
        }

        if (error.status === 422) {
            return "Dữ liệu gửi lên chưa đúng yêu cầu của Backend.";
        }

        if (error.status === 429) {
            return "Hệ thống đang giới hạn yêu cầu. Vui lòng thử lại sau.";
        }

        if (error.status === 503) {
            return "Dịch vụ báo cáo AI hiện không khả dụng.";
        }

        if (error.code === "NETWORK_ERROR") {
            return "Không kết nối được Backend. Kiểm tra server và CORS.";
        }

        return error.message || "Đã xảy ra lỗi. Vui lòng thử lại.";
    }

    function setBusy(value) {
        busy = value;

        projectSelect.disabled =
            value || projectSelect.options.length <= 1;

        weekSelect.disabled =
            value ||
            !projectSelect.value ||
            weekSelect.options.length <= 1;

        previewButton.disabled =
            value ||
            !projectSelect.value ||
            !weekSelect.value;

        saveButton.disabled =
            value ||
            !previewId ||
            saved ||
            saveAttempted;

        confirmSave.disabled = value;
        cancelSave.disabled = value;

        previewButton.textContent = value
            ? "Đang xử lý..."
            : "✦ Xem trước báo cáo AI";

        confirmSave.textContent = value
            ? "Đang lưu..."
            : "Xác nhận lưu";
    }

    function formatDate(date) {
        const year = date.getUTCFullYear();
        const month = String(
            date.getUTCMonth() + 1
        ).padStart(2, "0");

        const day = String(
            date.getUTCDate()
        ).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function displayDate(value) {
        const parts = String(value).split("-");

        if (parts.length !== 3) return value;

        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    function getVietnamToday() {
        const parts = new Intl.DateTimeFormat("en-US", {
            timeZone: TIME_ZONE,
            year: "numeric",
            month: "2-digit",
            day: "2-digit"
        }).formatToParts(new Date());

        const values = {};

        parts.forEach(part => {
            values[part.type] = part.value;
        });

        return new Date(Date.UTC(
            Number(values.year),
            Number(values.month) - 1,
            Number(values.day)
        ));
    }

    function parseProjectDate(value) {
        if (!value) return null;

        const text = String(value).trim();

        const match = text.match(
            /^(\d{4})-(\d{2})-(\d{2})/
        );

        if (!match) return null;

        const year = Number(match[1]);
        const month = Number(match[2]);
        const day = Number(match[3]);

        const date = new Date(Date.UTC(
            year,
            month - 1,
            day
        ));

        if (
            date.getUTCFullYear() !== year ||
            date.getUTCMonth() !== month - 1 ||
            date.getUTCDate() !== day
        ) {
            return null;
        }

        return date;
    }

    function getProjectCreatedDate(project) {
        if (!project) return null;

        const value =
            project.created_at ??
            project.createdAt ??
            project.created_date ??
            project.createdDate ??
            null;

        return parseProjectDate(value);
    }

    function getCurrentMonday() {
        const today = getVietnamToday();

        const dayOfWeek = today.getUTCDay();
        const daysSinceMonday = (dayOfWeek + 6) % 7;

        const monday = new Date(today);

        monday.setUTCDate(
            monday.getUTCDate() - daysSinceMonday
        );

        return monday;
    }

    function getSelectedProject() {
        return projects.find(project =>
            String(project.id) === projectSelect.value
        ) || null;
    }

    function resetWeekSelect(
        message = "Chọn dự án trước"
    ) {
        weekSelect.replaceChildren();

        const option = document.createElement("option");

        option.value = "";
        option.textContent = message;

        weekSelect.appendChild(option);
        weekSelect.value = "";
        weekSelect.disabled = true;
    }

    function populateWeeks() {
        resetWeekSelect("Chọn tuần đã kết thúc");

        const project = getSelectedProject();

        if (!project) {
            resetWeekSelect("Chọn dự án trước");
            setBusy(false);
            return;
        }

        const createdDate = getProjectCreatedDate(project);

        if (!createdDate) {
            resetWeekSelect("Không có ngày tạo dự án");

            showMessage(
                "Không xác định được ngày tạo dự án. " +
                "Backend cần trả về created_at để xác định " +
                "các tuần báo cáo hợp lệ.",
                "error"
            );

            setBusy(false);
            return;
        }

        const today = getVietnamToday();

        if (createdDate > today) {
            resetWeekSelect("Ngày tạo dự án không hợp lệ");

            showMessage(
                "Ngày tạo dự án lớn hơn ngày hiện tại.",
                "error"
            );

            setBusy(false);
            return;
        }

        const currentMonday = getCurrentMonday();

        const latestCompletedMonday = new Date(
            currentMonday
        );

        latestCompletedMonday.setUTCDate(
            latestCompletedMonday.getUTCDate() - 7
        );

        const latestCompletedSunday = new Date(
            latestCompletedMonday
        );

        latestCompletedSunday.setUTCDate(
            latestCompletedSunday.getUTCDate() + 6
        );

        // Tuần hợp lệ nếu:
        // 1. Tuần đã kết thúc.
        // 2. Ngày tạo dự án <= Chủ nhật của tuần.
        if (latestCompletedSunday < createdDate) {
            resetWeekSelect("Chưa có tuần phù hợp");

            showMessage(
                "Dự án chưa có tuần báo cáo đã kết thúc. " +
                "Bạn có thể lập báo cáo sau khi tuần " +
                "hoạt động đầu tiên kết thúc.",
                "info"
            );

            setBusy(false);
            return;
        }

        let monday = new Date(latestCompletedMonday);
        let totalWeeks = 0;

        while (true) {
            const sunday = new Date(monday);

            sunday.setUTCDate(
                sunday.getUTCDate() + 6
            );

            // Dừng khi tuần hoàn toàn trước ngày tạo dự án.
            if (sunday < createdDate) {
                break;
            }

            const start = formatDate(monday);
            const end = formatDate(sunday);

            const option = document.createElement("option");

            option.value = start;
            option.textContent =
                `${displayDate(start)} - ${displayDate(end)}`;

            weekSelect.appendChild(option);

            totalWeeks++;

            monday.setUTCDate(
                monday.getUTCDate() - 7
            );
        }

        if (totalWeeks === 0) {
            resetWeekSelect("Chưa có tuần phù hợp");

            showMessage(
                "Dự án chưa có tuần báo cáo hợp lệ.",
                "info"
            );

            setBusy(false);
            return;
        }

        showMessage("");
        setBusy(false);
    }

    function clearPreview() {
        previewData = null;
        previewId = null;
        previewProjectId = null;
        previewWeekStart = null;
        saved = false;
        saveAttempted = false;

        previewSection.hidden = true;
        metricsContainer.replaceChildren();
        aiContent.textContent = "";
        periodText.textContent = "";

        overlay.hidden = true;

        setBusy(false);
    }

    function normalizeMetrics(data) {
        const source = data.metrics;

        if (!source || typeof source !== "object") {
            throw new Error(
                "Backend chưa trả về danh sách 6 chỉ số MET."
            );
        }

        if (Array.isArray(source)) {
            return METRIC_CODES.map(code => {
                const item = source.find(metric =>
                    String(
                        metric.code ??
                        metric.id ??
                        metric.key ??
                        ""
                    ).toUpperCase() === code
                );

                if (!item) {
                    throw new Error(`Thiếu chỉ số ${code}.`);
                }

                const value = item.value;

                if (value === undefined || value === null) {
                    throw new Error(
                        `${code} chưa có giá trị hợp lệ.`
                    );
                }

                return {
                    code,
                    label: String(
                        item.label ??
                        item.name ??
                        item.title ??
                        code
                    ),
                    value,
                    unit: item.unit ?? ""
                };
            });
        }

        return METRIC_CODES.map(code => {
            const key = Object.keys(source).find(
                item => item.toUpperCase() === code
            );

            if (!key) {
                throw new Error(`Thiếu chỉ số ${code}.`);
            }

            const raw = source[key];

            const value = raw &&
                typeof raw === "object" &&
                !Array.isArray(raw)
                ? raw.value
                : raw;

            if (value === undefined || value === null) {
                throw new Error(
                    `${code} chưa có giá trị hợp lệ.`
                );
            }

            return {
                code,
                label: raw &&
                    typeof raw === "object"
                    ? String(raw.label ?? raw.name ?? code)
                    : code,
                value,
                unit: raw &&
                    typeof raw === "object"
                    ? raw.unit ?? ""
                    : ""
            };
        });
    }

    function normalizeNarrative(data) {
        const value =
            data.ai_narrative ??
            data.narrative ??
            data.ai_comment ??
            data.ai_analysis;

        if (typeof value === "string" && value.trim()) {
            return value.trim();
        }

        if (
            value &&
            typeof value === "object" &&
            !Array.isArray(value)
        ) {
            const sections = [
                value.summary,
                value.highlights,
                value.risks,
                value.recommendations
            ];

            const text = sections
                .flatMap(item =>
                    Array.isArray(item) ? item : [item]
                )
                .filter(item =>
                    typeof item === "string" && item.trim()
                )
                .join("\n\n");

            if (text) return text;
        }

        throw new Error(
            "Backend chưa trả về nhận xét AI đúng định dạng."
        );
    }

    function renderMetrics(metrics) {
        metricsContainer.replaceChildren();

        metrics.forEach(metric => {
            const card = document.createElement("article");
            card.className = "report-metric";

            const code = document.createElement("span");
            code.className = "report-metric-code";
            code.textContent = metric.code;

            const title = document.createElement("h4");
            title.textContent = metric.label;

            const value = document.createElement("strong");

            value.textContent =
                String(metric.value) +
                (metric.unit ? ` ${metric.unit}` : "");

            card.append(code, title, value);
            metricsContainer.appendChild(card);
        });
    }

    async function loadProjects() {
        showMessage("Đang tải danh sách dự án...");

        projectSelect.disabled = true;
        resetWeekSelect();

        try {
            const response = await API.get("/projects");
            const result = unwrap(response);

            if (!Array.isArray(result)) {
                throw new Error(
                    "Backend trả về danh sách dự án không hợp lệ."
                );
            }

            projects = result;

            projectSelect.innerHTML =
                '<option value="">Chọn dự án</option>';

            projects.forEach(project => {
                if (!project.id || !project.name) return;

                const option = document.createElement("option");

                option.value = String(project.id);
                option.textContent = project.name;

                projectSelect.appendChild(option);
            });

            const requestedProject = new URLSearchParams(
                location.search
            ).get("project");

            if (
                requestedProject &&
                [...projectSelect.options].some(
                    option => option.value === requestedProject
                )
            ) {
                projectSelect.value = requestedProject;
            }

            if (projectSelect.options.length <= 1) {
                showMessage(
                    "Tài khoản hiện chưa có dự án để lập báo cáo."
                );
            } else if (projectSelect.value) {
                populateWeeks();
            } else {
                showMessage("");
            }
        } catch (error) {
            showMessage(errorText(error), "error");
        } finally {
            setBusy(false);
        }
    }

    async function checkAuth() {
        showMessage("Đang kiểm tra phiên đăng nhập...");
        form.hidden = true;

        try {
            const response = await API.get("/auth/me", {
                skipAuthRedirect: true
            });

            const user = unwrap(response);

            if (!user || !user.email) {
                throw new Error(
                    "Thông tin đăng nhập không hợp lệ."
                );
            }

            form.hidden = false;

            await loadProjects();
        } catch (error) {
            if (error.status === 401) {
                location.replace("login.html");
                return;
            }

            showMessage(errorText(error), "error");
        }
    }

    projectSelect.addEventListener("change", () => {
        clearPreview();
        populateWeeks();
    });

    weekSelect.addEventListener("change", () => {
        clearPreview();
        showMessage("");
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();

        if (busy) return;

        const projectId = Number(projectSelect.value);
        const weekStart = weekSelect.value;

        if (
            !Number.isSafeInteger(projectId) ||
            projectId <= 0 ||
            !weekStart
        ) {
            showMessage(
                "Vui lòng chọn dự án và tuần báo cáo.",
                "error"
            );
            return;
        }

        const project = getSelectedProject();
        const createdDate = getProjectCreatedDate(project);
        const selectedMonday = parseProjectDate(weekStart);

        const latestMonday = getCurrentMonday();

        latestMonday.setUTCDate(
            latestMonday.getUTCDate() - 7
        );

        if (!createdDate || !selectedMonday) {
            showMessage(
                "Không xác định được ngày tạo dự án " +
                "hoặc tuần báo cáo.",
                "error"
            );
            return;
        }

        const selectedSunday = new Date(selectedMonday);

        selectedSunday.setUTCDate(
            selectedSunday.getUTCDate() + 6
        );

        // Kiểm tra tuần đã kết thúc và có giao với
        // khoảng thời gian dự án tồn tại.
        if (
            selectedSunday < createdDate ||
            selectedMonday > latestMonday
        ) {
            showMessage(
                "Tuần báo cáo không hợp lệ với ngày tạo dự án.",
                "error"
            );
            return;
        }

        clearPreview();
        setBusy(true);

        showMessage("Đang tạo bản xem trước báo cáo...");

        try {
            const response = await API.get(
                "/reports/preview",
                {
                    query: {
                        project_id: projectId,
                        week_start: weekStart
                    }
                }
            );

            const data = unwrap(response);

            if (!data || typeof data !== "object") {
                throw new Error(
                    "Dữ liệu báo cáo không hợp lệ."
                );
            }

            const metrics = normalizeMetrics(data);
            const narrative = normalizeNarrative(data);

            renderMetrics(metrics);

            aiContent.textContent = narrative;

            periodText.textContent =
                weekSelect.selectedOptions[0].textContent;

            previewData = data;
            previewProjectId = projectId;
            previewWeekStart = weekStart;

            previewId =
                data.preview_id ??
                data.previewId ??
                null;

            previewSection.hidden = false;

            if (!previewId) {
                showMessage(
                    "Đã xem trước báo cáo, nhưng Backend chưa " +
                    "trả về preview_id nên chưa thể lưu.",
                    "error"
                );
            } else {
                showMessage(
                    "Đã tạo bản xem trước. " +
                    "Vui lòng kiểm tra trước khi lưu.",
                    "success"
                );
            }

            previewSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        } catch (error) {
            clearPreview();
            showMessage(errorText(error), "error");
        } finally {
            setBusy(false);
        }
    });

    function closeConfirm() {
        if (busy) return;

        overlay.hidden = true;
        saveButton.focus();
    }

    saveButton.addEventListener("click", () => {
        if (
            busy ||
            saved ||
            saveAttempted ||
            !previewId
        ) return;

        overlay.hidden = false;
        cancelSave.focus();
    });

    cancelSave.addEventListener("click", closeConfirm);

    overlay.addEventListener("click", event => {
        if (event.target === overlay) {
            closeConfirm();
        }
    });

    document.addEventListener("keydown", event => {
        if (overlay.hidden) return;

        if (event.key === "Escape" && !busy) {
            closeConfirm();
        }

        if (event.key === "Tab") {
            const buttons = [cancelSave, confirmSave];

            if (
                event.shiftKey &&
                document.activeElement === buttons[0]
            ) {
                event.preventDefault();
                buttons[1].focus();
            } else if (
                !event.shiftKey &&
                document.activeElement === buttons[1]
            ) {
                event.preventDefault();
                buttons[0].focus();
            }
        }
    });

    confirmSave.addEventListener("click", async () => {
        if (
            busy ||
            saved ||
            saveAttempted ||
            !previewId
        ) return;

        setBusy(true);
        saveAttempted = true;

        showMessage("Đang lưu báo cáo...");

        try {
            await API.post("/reports", {
                project_id: previewProjectId,
                week_start: previewWeekStart,
                preview_id: previewId
            });

            saved = true;
            overlay.hidden = true;

            showMessage(
                "Báo cáo tuần đã được lưu thành công.",
                "success"
            );
        } catch (error) {
            overlay.hidden = true;

            showMessage(
                errorText(error) +
                " Nếu yêu cầu đã tới Backend, hãy kiểm tra " +
                "báo cáo đã lưu trước khi gửi lại để tránh trùng.",
                "error"
            );
        } finally {
            setBusy(false);
        }
    });

    resetWeekSelect();
    checkAuth();
})();
