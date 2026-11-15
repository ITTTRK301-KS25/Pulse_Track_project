
"use strict";

(function () {
    const API = window.PulseAPI;

    function formatTime(value) {
        if (!value) return "";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return new Intl.DateTimeFormat("vi-VN", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
            timeZone: "Asia/Ho_Chi_Minh"
        }).format(date);
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

    function createElement(tag, className, text) {
        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        if (text !== undefined && text !== null) {
            element.textContent = String(text);
        }

        return element;
    }

    function mount(modal, options) {
        if (!modal || !options) return;

        const { projectId, taskId, canPost } = options;

        if (!projectId || !taskId) return;

        const endpoint =
            `/projects/${encodeURIComponent(projectId)}` +
            `/tasks/${encodeURIComponent(taskId)}/comments`;

        const section = createElement(
            "section",
            "comments-section"
        );

        section.setAttribute(
            "aria-label",
            "Bình luận công việc"
        );

        const heading = createElement(
            "div",
            "comments-heading"
        );

        const title = createElement(
            "h3",
            "",
            "Bình luận"
        );

        const count = createElement(
            "span",
            "comments-count",
            "0 bình luận"
        );

        heading.append(title, count);

        const message = createElement(
            "p",
            "comments-message"
        );

        message.setAttribute("role", "status");
        message.setAttribute("aria-live", "polite");
        message.hidden = true;

        const list = createElement(
            "div",
            "comments-list"
        );

        section.append(heading, message, list);

        function showMessage(text, isError = false) {
            message.textContent = text || "";
            message.hidden = !text;
            message.classList.toggle(
                "is-error",
                Boolean(isError)
            );
        }

        function renderComments(comments) {
            if (!section.isConnected) return;

            list.replaceChildren();

            count.textContent =
                `${comments.length} bình luận`;

            if (!comments.length) {
                list.appendChild(
                    createElement(
                        "p",
                        "comments-empty",
                        "Chưa có bình luận nào."
                    )
                );
                return;
            }

            const fragment = document.createDocumentFragment();

            comments.forEach(comment => {
                const item = createElement(
                    "article",
                    "comment-item"
                );

                const authorName =
                    comment.author_name ||
                    `Người dùng #${comment.author_id ?? "?"}`;

                const avatar = createElement(
                    "span",
                    "comment-avatar",
                    getInitial(authorName)
                );

                avatar.setAttribute(
                    "aria-label",
                    `Ảnh đại diện ${authorName}`
                );

                const body = createElement(
                    "div",
                    "comment-body"
                );

                const meta = createElement(
                    "div",
                    "comment-meta"
                );

                const author = createElement(
                    "strong",
                    "comment-author",
                    authorName
                );

                const time = createElement(
                    "time",
                    "comment-time",
                    formatTime(comment.created_at)
                );

                if (comment.created_at) {
                    time.dateTime = comment.created_at;
                }

                meta.append(author, time);

                const content = createElement(
                    "p",
                    "comment-content",
                    comment.content || ""
                );

                body.append(meta, content);
                item.append(avatar, body);
                fragment.appendChild(item);
            });

            list.appendChild(fragment);
        }

        async function loadComments() {
            if (!section.isConnected) return false;

            list.replaceChildren(
                createElement(
                    "p",
                    "comments-empty",
                    "Đang tải bình luận..."
                )
            );

            try {
                if (!API) {
                    throw new Error(
                        "Chưa tải được HTTP client PulseAPI."
                    );
                }

                const response = await API.get(endpoint);

                if (!Array.isArray(response?.data)) {
                    throw new Error(
                        "Dữ liệu bình luận không hợp lệ."
                    );
                }

                if (!section.isConnected) return false;

                renderComments(response.data);
                showMessage("");

                return true;
            } catch (error) {
                if (!section.isConnected) return false;

                list.replaceChildren();

                const errorText = createElement(
                    "p",
                    "comments-empty",
                    error.message ||
                    "Không thể tải danh sách bình luận."
                );

                const retry = createElement(
                    "button",
                    "btn",
                    "Thử tải lại"
                );

                retry.type = "button";

                retry.addEventListener("click", () => {
                    loadComments();
                });

                list.append(errorText, retry);

                return false;
            }
        }

        if (canPost) {
            const form = createElement(
                "form",
                "comments-form"
            );

            const textarea = createElement(
                "textarea",
                "comments-textarea"
            );

            textarea.name = "content";
            textarea.placeholder =
                "Viết bình luận của bạn...";

            textarea.rows = 3;
            textarea.maxLength = 2000;
            textarea.required = true;

            textarea.setAttribute(
                "aria-label",
                "Nội dung bình luận"
            );

            const footer = createElement(
                "div",
                "comments-form-footer"
            );

            const counter = createElement(
                "span",
                "comments-counter",
                "0/2000"
            );

            const submitButton = createElement(
                "button",
                "btn btn-primary",
                "Gửi bình luận"
            );

            submitButton.type = "submit";

            textarea.addEventListener("input", () => {
                counter.textContent =
                    `${textarea.value.length}/2000`;
            });

            footer.append(counter, submitButton);
            form.append(textarea, footer);

            form.addEventListener(
                "submit",
                async event => {
                    event.preventDefault();

                    if (submitButton.disabled) return;

                    const content = textarea.value.trim();

                    if (!content) {
                        showMessage(
                            "Vui lòng nhập nội dung bình luận.",
                            true
                        );
                        textarea.focus();
                        return;
                    }

                    if (content.length > 2000) {
                        showMessage(
                            "Bình luận không được vượt quá 2000 ký tự.",
                            true
                        );
                        return;
                    }

                    submitButton.disabled = true;
                    textarea.disabled = true;
                    submitButton.textContent = "Đang gửi...";

                    showMessage("");

                    try {
                        if (!API) {
                            throw new Error(
                                "Chưa tải được HTTP client PulseAPI."
                            );
                        }

                        const response = await API.post(
                            endpoint,
                            { content }
                        );

                        if (
                            !response?.data ||
                            response.data.id == null
                        ) {
                            throw new Error(
                                "Máy chủ trả về bình luận không hợp lệ."
                            );
                        }

                        textarea.value = "";
                        counter.textContent = "0/2000";

                        const refreshed =
                            await loadComments();

                        if (refreshed) {
                            showMessage(
                                "Đã gửi bình luận thành công."
                            );
                        } else {
                            showMessage(
                                "Bình luận đã được gửi nhưng " +
                                "chưa tải lại được danh sách.",
                                true
                            );
                        }
                    } catch (error) {
                        showMessage(
                            error.message ||
                            "Không thể gửi bình luận.",
                            true
                        );
                    } finally {
                        submitButton.disabled = false;
                        textarea.disabled = false;
                        submitButton.textContent =
                            "Gửi bình luận";
                    }
                }
            );

            section.appendChild(form);
        } else {
            section.appendChild(
                createElement(
                    "p",
                    "comments-readonly",
                    "Bạn chỉ có quyền xem bình luận " +
                    "hoặc công việc đã được lưu trữ."
                )
            );
        }

        modal.appendChild(section);

        loadComments();
    }

    window.PulseComments = Object.freeze({
        mount
    });
})();
