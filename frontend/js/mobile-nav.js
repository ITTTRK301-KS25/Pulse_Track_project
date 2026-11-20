
"use strict";

(function () {
    const pages = [
        {
            href: "dashboard.html",
            label: "Tổng quan",
            icon: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>'
        },
        {
            href: "projects.html",
            label: "Dự án",
            icon: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        },
        {
            href: "kanban.html",
            label: "Công việc",
            icon: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>'
        },
        {
            href: "weekly-report.html",
            label: "Báo cáo",
            icon: '<path d="M4 20V10M10 20V4M16 20v-8M22 20v-5"/>'
        }
    ];

    function initMobileNav() {
        const currentPage =
            window.location.pathname.split("/").pop() ||
            "dashboard.html";

        if (!pages.some(page => page.href === currentPage)) {
            return;
        }

        if (document.querySelector(".pt-mobile-nav")) {
            return;
        }

        const nav = document.createElement("nav");

        nav.className = "pt-mobile-nav";
        nav.setAttribute(
            "aria-label",
            "Điều hướng chính trên điện thoại"
        );

        pages.forEach(page => {
            const link = document.createElement("a");

            link.href = page.href;

            const isActive = page.href === currentPage;

            if (isActive) {
                link.classList.add("active");
                link.setAttribute("aria-current", "page");
            }

            const svg = document.createElementNS(
                "http://www.w3.org/2000/svg",
                "svg"
            );

            svg.setAttribute("viewBox", "0 0 24 24");
            svg.setAttribute("fill", "none");
            svg.setAttribute("stroke", "currentColor");
            svg.setAttribute("stroke-width", "1.8");
            svg.setAttribute("stroke-linecap", "round");
            svg.setAttribute("stroke-linejoin", "round");
            svg.setAttribute("aria-hidden", "true");

            svg.innerHTML = page.icon;

            const label = document.createElement("span");
            label.textContent = page.label;

            link.appendChild(svg);
            link.appendChild(label);
            nav.appendChild(link);
        });

        document.body.appendChild(nav);
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initMobileNav
        );
    } else {
        initMobileNav();
    }
})();
