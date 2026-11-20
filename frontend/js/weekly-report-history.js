
"use strict";

(function () {
    const API = window.PulseAPI;
    const $ = id => document.getElementById(id);

    if (!API || !$("report-project")) return;

    const projectSelect = $("report-project");
    const section = $("saved-reports");
    const list = $("saved-report-list");
    const status = $("saved-report-status");
    const pagination = $("saved-report-pagination");
    const detail = $("saved-report-detail");
    const refreshButton = $("saved-report-refresh");
    const reportMessage = $("report-message");

    const PAGE_SIZE = 10;

    let currentPage = 1;
    let currentProjectId = null;
    let currentReportId = null;
    let loadVersion = 0;
    let busy = false;

    const METRIC_LABELS = {
        "MET-01": "Công việc hoàn thành trong tuần",
        "MET-02": "Công việc đang mở cuối tuần",
        "MET-03": "Công việc quá hạn cuối tuần",
        "MET-04": "Công việc đến hạn trong tuần",
        "MET-05": "Công việc hoàn thành đúng hạn",
        "MET-06": "Tỷ lệ hoàn thành đúng hạn"
    };

    function unwrap(response) {
        return response?.data ?? response;
    }

    function formatDate(value) {
        if (!value) return "--";

        const parts = String(value).slice(0, 10).split("-");

        if (parts.length !== 3) return String(value);

        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    function errorMessage(error) {
        if (error.status === 401) {
            return "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
        }

        if (error.status === 403) {
            return "Bạn không có quyền xem báo cáo của dự án này.";
        }

        if (error.status === 404) {
            return "Không tìm thấy báo cáo.";
        }

        if (error.code === "NETWORK_ERROR") {
            return "Không kết nối được Backend.";
        }

        return error.message || "Đã xảy ra lỗi. Vui lòng thử lại.";
    }

    function showStatus(message, type = "info") {
        status.textContent = message;
        status.dataset.type = type;
        status.hidden = !message;
    }

    function makeElement(tag, className, text) {
        const element = document.createElement(tag);

        if (className) element.className = className;

        if (text !== undefined) {
            element.textContent = String(text);
        }

        return element;
    }

    function makeButton(text, className, callback) {
        const button = makeElement(
            "button",
            className,
            text
        );

        button.type = "button";
        button.addEventListener("click", callback);

        return button;
    }

    function getMetrics(report) {
        if (Array.isArray(report.metrics)) {
            return report.metrics;
        }

        const values = report.metrics_raw || report.metrics || {};

        return Object.keys(METRIC_LABELS).map(code => ({
            code,
            label: METRIC_LABELS[code],
            value: values[code] ?? 0,
            unit: code === "MET-06" ? "%" : "task"
        }));
    }

    function createMetricCards(report, container) {
        container.replaceChildren();

        getMetrics(report).forEach(metric => {
            const card = makeElement(
                "article",
                "report-metric"
            );

            const code = makeElement(
                "span",
                "report-metric-code",
                metric.code
            );

            const title = makeElement(
                "h4",
                "",
                metric.label || METRIC_LABELS[metric.code] || metric.code
            );

            const value = makeElement(
                "strong",
                "",
                `${metric.value} ${metric.unit || ""}`.trim()
            );

            card.append(code, title, value);
            container.appendChild(card);
        });
    }

    function renderList(items) {
        list.replaceChildren();

        if (!items.length) {
            showStatus(
                "Dự án này chưa có báo cáo tuần nào được lưu."
            );
            return;
        }

        showStatus("");

        items.forEach(report => {
            const card = makeElement(
                "article",
                "saved-report-item"
            );

            const info = makeElement(
                "div",
                "saved-report-info"
            );

            const title = makeElement(
                "h3",
                "",
                `Báo cáo tuần ${formatDate(report.week_start)} - ${formatDate(report.week_end)}`
            );

            const meta = makeElement(
                "p",
                "",
                `Mã #${report.id} · Đã lưu · ${formatDate(report.created_at)}`
            );

            info.append(title, meta);

            if (report.is_mock) {
                info.appendChild(
                    makeElement(
                        "span",
                        "saved-report-mock",
                        "AI giả lập"
                    )
                );
            }

            const actions = makeElement(
                "div",
                "saved-report-item-actions"
            );

            actions.append(
                makeButton(
                    "Xem chi tiết",
                    "report-button report-button-secondary",
                    () => openDetail(report.id)
                ),
                makeButton(
                    "Tải Markdown",
                    "report-button report-button-primary",
                    () => downloadMarkdown(report.id)
                )
            );

            card.append(info, actions);
            list.appendChild(card);
        });
    }

    function renderPagination(totalPages) {
        pagination.replaceChildren();

        if (totalPages <= 1) return;

        const previous = makeButton(
            "← Trang trước",
            "report-button report-button-secondary",
            () => loadReports(currentPage - 1)
        );

        previous.disabled = currentPage <= 1;

        const pageText = makeElement(
            "span",
            "saved-report-page-label",
            `Trang ${currentPage}/${totalPages}`
        );

        const next = makeButton(
            "Trang sau →",
            "report-button report-button-secondary",
            () => loadReports(currentPage + 1)
        );

        next.disabled = currentPage >= totalPages;

        pagination.append(previous, pageText, next);
    }

    async function loadReports(page = 1) {
        const projectId = Number(projectSelect.value);
        const version = ++loadVersion;

        currentPage = page;
        currentProjectId = projectId || null;
        currentReportId = null;

        list.replaceChildren();
        pagination.replaceChildren();
        detail.hidden = true;

        if (!Number.isSafeInteger(projectId) || projectId <= 0) {
            section.hidden = false;
            showStatus("Chọn dự án để xem các báo cáo đã lưu.");
            return;
        }

        section.hidden = false;
        busy = true;
        refreshButton.disabled = true;

        showStatus("Đang tải danh sách báo cáo...");

        try {
            const response = await API.get("/reports", {
                query: {
                    project_id: projectId,
                    page,
                    page_size: PAGE_SIZE
                }
            });

            if (version !== loadVersion) return;

            const data = unwrap(response);

            if (!data || !Array.isArray(data.items)) {
                throw new Error(
                    "Danh sách báo cáo trả về không hợp lệ."
                );
            }

            renderList(data.items);
            renderPagination(Number(data.total_pages) || 0);
        } catch (error) {
            if (version !== loadVersion) return;

            showStatus(errorMessage(error), "error");
        } finally {
            if (version === loadVersion) {
                busy = false;
                refreshButton.disabled = false;
            }
        }
    }

    async function openDetail(reportId) {
        if (!currentProjectId) return;

        const projectId = currentProjectId;

        currentReportId = reportId;
        detail.hidden = false;
        detail.replaceChildren(
            makeElement("p", "", "Đang tải chi tiết báo cáo...")
        );

        try {
            const response = await API.get(
                `/reports/${encodeURIComponent(reportId)}`
            );

            if (
                currentReportId !== reportId ||
                currentProjectId !== projectId
            ) return;

            const report = unwrap(response);

            if (
                !report ||
                Number(report.project_id) !== projectId
            ) {
                throw new Error(
                    "Báo cáo không thuộc dự án đang chọn."
                );
            }

            renderDetail(report);

            detail.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        } catch (error) {
            if (currentReportId !== reportId) return;

            detail.replaceChildren(
                makeElement(
                    "p",
                    "saved-report-error",
                    errorMessage(error)
                )
            );
        }
    }

    function renderDetail(report) {
        detail.replaceChildren();

        const header = makeElement(
            "div",
            "saved-report-detail-header"
        );

        const heading = makeElement(
            "div",
            ""
        );

        heading.append(
            makeElement(
                "span",
                "report-step",
                "BÁO CÁO ĐÃ LƯU"
            ),
            makeElement(
                "h2",
                "",
                `Báo cáo #${report.id}`
            ),
            makeElement(
                "p",
                "",
                `${formatDate(report.week_start)} - ${formatDate(report.week_end)}`
            )
        );

        const close = makeButton(
            "Đóng",
            "report-button report-button-secondary",
            () => {
                currentReportId = null;
                detail.hidden = true;
            }
        );

        header.append(heading, close);

        const subtitle = makeElement(
            "h3",
            "report-subtitle",
            "Tổng quan các chỉ số"
        );

        const metrics = makeElement(
            "div",
            "report-metrics"
        );

        createMetricCards(report, metrics);

        const aiCard = makeElement(
            "div",
            "report-ai-card"
        );

        const aiTitle = makeElement(
            "h3",
            "",
            "Nhận xét tiến độ"
        );

        const narrative = makeElement(
            "div",
            "report-ai-content",
            report.ai_narrative || "Không có nội dung nhận xét."
        );

        aiCard.append(aiTitle, narrative);

        if (report.is_mock) {
            aiCard.appendChild(
                makeElement(
                    "p",
                    "saved-report-mock-note",
                    "Lưu ý: Đây là nội dung AI giả lập trong chế độ demo."
                )
            );
        }

        const footer = makeElement(
            "div",
            "saved-report-detail-footer"
        );

        footer.appendChild(
            makeButton(
                "Tải báo cáo Markdown",
                "report-button report-button-primary",
                () => downloadMarkdown(report.id)
            )
        );

        detail.append(
            header,
            subtitle,
            metrics,
            aiCard,
            footer
        );
    }

    async function downloadMarkdown(reportId) {
        const projectId = currentProjectId;

        showStatus("Đang chuẩn bị tải báo cáo...");

        try {
            // API.request mặc định đọc JSON, trong khi
            // endpoint export trả về text/markdown.
            // Vì vậy dùng fetch với cookie đăng nhập.
            const base = String(
                window.PULSE_CONFIG?.API_BASE_URL ||
                "http://127.0.0.1:8000"
            ).replace(/\/+$/, "");

            const response = await fetch(
                `${base}/reports/${encodeURIComponent(reportId)}/export`,
                {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        Accept: "text/markdown"
                    },
                    cache: "no-store"
                }
            );

            if (!response.ok) {
                const error = new Error(
                    `Không thể tải báo cáo (HTTP ${response.status}).`
                );
                error.status = response.status;
                throw error;
            }

            const blob = await response.blob();

            if (currentProjectId !== projectId) return;

            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");

            anchor.href = url;
            anchor.download = `weekly-report-${reportId}.md`;

            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();

            setTimeout(() => URL.revokeObjectURL(url), 1000);

            showStatus(
                "Đã tải báo cáo Markdown thành công.",
                "success"
            );
        } catch (error) {
            showStatus(errorMessage(error), "error");
        }
    }

    refreshButton.addEventListener("click", () => {
        if (!busy) loadReports(currentPage);
    });

    projectSelect.addEventListener("change", () => {
        loadReports(1);
    });

    // F14 tải dự án bất đồng bộ, nên theo dõi khi
    // danh sách dự án đã được điền vào select.
    const projectObserver = new MutationObserver(() => {
        const selected = Number(projectSelect.value);

        if (
            selected > 0 &&
            selected !== currentProjectId
        ) {
            loadReports(1);
        }
    });

    projectObserver.observe(projectSelect, {
        childList: true,
        subtree: true
    });

    // Sau khi F14 lưu báo cáo thành công,
    // tự động làm mới danh sách F15.
    const messageObserver = new MutationObserver(() => {
        if (
            reportMessage?.dataset.type === "success" &&
            reportMessage.textContent.includes(
                "đã được lưu thành công"
            )
        ) {
            loadReports(1);
        }
    });

    if (reportMessage) {
        messageObserver.observe(reportMessage, {
            childList: true,
            characterData: true,
            subtree: true
        });
    }

    loadReports(1);
})();
