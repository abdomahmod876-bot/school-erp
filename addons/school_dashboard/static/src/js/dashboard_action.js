/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { ChartCard } from "./chart_card";

const PERIODS = [
    { key: "all", label: "All Time" },
    { key: "today", label: "Today" },
    { key: "week", label: "Last 7 Days" },
    { key: "month", label: "This Month" },
    { key: "year", label: "This Year" },
];

export class DashboardAction extends Component {
    static template = "school_dashboard.DashboardAction";
    static components = { ChartCard };
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
        className: { type: String, optional: true },
        updateActionState: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            dashboard: { name: "", items: [] },
            period: "all",
            loading: true,
            error: null,
        });
        this._dragId = null;
        this._dropEl = null;
        this._dropAfter = false;
        onWillStart(() => this.load());
    }

    get periods() {
        return PERIODS;
    }

    get dashboardId() {
        return this.props.action.params && this.props.action.params.dashboard_id;
    }

    _computeRange(period) {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const iso = (date) =>
            `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
                date.getDate()
            ).padStart(2, "0")}`;
        switch (period) {
            case "today":
                return { date_from: iso(start), date_to: iso(start) };
            case "week":
                return {
                    date_from: iso(new Date(start.getTime() - 6 * 86400000)),
                    date_to: iso(now),
                };
            case "month":
                return {
                    date_from: iso(new Date(now.getFullYear(), now.getMonth(), 1)),
                    date_to: iso(now),
                };
            case "year":
                return {
                    date_from: iso(new Date(now.getFullYear(), 0, 1)),
                    date_to: iso(now),
                };
            default:
                return { date_from: false, date_to: false };
        }
    }

    async load() {
        if (!this.dashboardId) {
            this.state.loading = false;
            this.state.error = "No dashboard selected.";
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        const { date_from, date_to } = this._computeRange(this.state.period);
        try {
            this.state.dashboard = await this.orm.call(
                "school.dashboard",
                "get_dashboard_data",
                [[this.dashboardId]],
                { date_from, date_to }
            );
        } catch (error) {
            this.state.error =
                (error.data && error.data.message) || error.message || "Failed to load dashboard.";
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriod(period) {
        if (this.state.period === period) {
            return;
        }
        this.state.period = period;
        await this.load();
    }

    async refresh() {
        await this.load();
    }

    // ------------------------------------------------------------------
    // Drag & drop reordering
    // ------------------------------------------------------------------
    onDragStart(ev) {
        const card = ev.target.closest && ev.target.closest(".o_sd_card");
        if (!card || !ev.dataTransfer) {
            return;
        }
        this._dragId = Number(card.dataset.id);
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", card.dataset.id);
        requestAnimationFrame(() => card.classList.add("o_sd_dragging"));
    }

    onDragOver(ev) {
        if (!this._dragId) {
            return;
        }
        ev.preventDefault();
        if (ev.dataTransfer) {
            ev.dataTransfer.dropEffect = "move";
        }
        const card = ev.target.closest && ev.target.closest(".o_sd_card");
        if (!card || Number(card.dataset.id) === this._dragId) {
            this._clearDrop();
            return;
        }
        const after = this._pointerAfter(ev, card.getBoundingClientRect());
        if (this._dropEl === card && this._dropAfter === after) {
            return;
        }
        this._clearDrop();
        this._dropEl = card;
        this._dropAfter = after;
        card.classList.add(after ? "o_sd_drop_after" : "o_sd_drop_before");
    }

    onDrop(ev) {
        if (!this._dragId) {
            return;
        }
        ev.preventDefault();
        const dragId = this._dragId;
        const card = ev.target.closest && ev.target.closest(".o_sd_card");
        const dropId = card ? Number(card.dataset.id) : null;
        const after = card
            ? this._pointerAfter(ev, card.getBoundingClientRect())
            : true;
        this._clearDrop();
        this._endDrag();
        if (dropId === null) {
            this._moveItem(dragId, null);
        } else if (dropId !== dragId) {
            this._moveItem(dragId, dropId, after);
        }
    }

    onDragEnd() {
        this._clearDrop();
        this._endDrag();
    }

    _pointerAfter(ev, rect) {
        const offsetX = (ev.clientX - (rect.left + rect.width / 2)) / (rect.width / 2 || 1);
        const offsetY = (ev.clientY - (rect.top + rect.height / 2)) / (rect.height / 2 || 1);
        return Math.abs(offsetX) > Math.abs(offsetY) ? offsetX > 0 : offsetY > 0;
    }

    _clearDrop() {
        if (this._dropEl) {
            this._dropEl.classList.remove("o_sd_drop_before", "o_sd_drop_after");
        }
        this._dropEl = null;
        this._dropAfter = false;
    }

    _endDrag() {
        this._dragId = null;
        for (const element of document.querySelectorAll(".o_sd_card.o_sd_dragging")) {
            element.classList.remove("o_sd_dragging");
        }
    }

    async _moveItem(dragId, beforeId, after = false) {
        const items = this.state.dashboard.items;
        const ids = items.map((item) => item.id);
        if (!ids.includes(dragId)) {
            return;
        }
        const without = ids.filter((id) => id !== dragId);
        let index = without.length;
        if (beforeId !== null) {
            index = without.indexOf(beforeId);
            if (index < 0) {
                return;
            }
            if (after) {
                index += 1;
            }
        }
        const ordered = without.slice();
        ordered.splice(index, 0, dragId);
        if (ordered.join(",") === ids.join(",")) {
            return;
        }
        const byId = new Map(items.map((item) => [item.id, item]));
        this.state.dashboard.items = ordered.map((id) => byId.get(id));
        try {
            await this.orm.call("school.dashboard", "set_item_order", [
                [this.dashboardId],
                ordered,
            ]);
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) || "Could not save the new order.",
                { type: "danger" }
            );
            await this.load();
        }
    }

    // ------------------------------------------------------------------
    // Resize grip
    // ------------------------------------------------------------------
    onPointerDown(ev) {
        const grip = ev.target.closest && ev.target.closest(".o_sd_resize");
        if (!grip) {
            return;
        }
        const card = grip.closest(".o_sd_card");
        const grid = ev.currentTarget;
        const itemId = card && Number(card.dataset.id);
        const item = this.state.dashboard.items.find((entry) => entry.id === itemId);
        if (!item) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        card.draggable = false;
        card.classList.add("o_sd_resizing");
        const gap = parseFloat(window.getComputedStyle(grid).columnGap) || 0;
        const columnStep = (grid.getBoundingClientRect().width + gap) / 12;
        const startLeft = card.getBoundingClientRect().left;
        const allowed = [3, 4, 6, 8, 12];
        let span = Number(item.span) || 4;
        const onMove = (moveEv) => {
            const width = moveEv.clientX - startLeft + gap;
            let best = allowed[0];
            let bestDistance = Infinity;
            for (const candidate of allowed) {
                const distance = Math.abs(candidate * columnStep - width);
                if (distance < bestDistance) {
                    bestDistance = distance;
                    best = candidate;
                }
            }
            if (best !== span) {
                span = best;
                card.style.gridColumn = `span ${span}`;
            }
        };
        const onUp = async () => {
            window.removeEventListener("pointermove", onMove);
            card.draggable = true;
            card.classList.remove("o_sd_resizing");
            if (span === (Number(item.span) || 4)) {
                return;
            }
            item.span = String(span);
            try {
                await this.orm.write("school.dashboard.item", [itemId], {
                    span: String(span),
                });
            } catch (error) {
                this.notification.add(
                    (error.data && error.data.message) || "Could not save the card size.",
                    { type: "danger" }
                );
                await this.load();
            }
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp, { once: true });
    }
}

registry.category("actions").add("school_dashboard.dashboard_action", DashboardAction);
