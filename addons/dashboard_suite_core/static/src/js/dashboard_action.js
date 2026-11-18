/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

import { DashboardFilterBar } from "./dashboard_filter_bar";
import { DashboardWidget } from "./dashboard_widget";

function errorMessage(error) {
    return (
        (error && error.data && error.data.message) ||
        (error && error.message) ||
        _t("Could not load the dashboard.")
    );
}

export class DashboardAction extends Component {
    static template = "dashboard_suite_core.DashboardAction";
    static components = { DashboardFilterBar, DashboardWidget };
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
        className: { type: String, optional: true },
        updateActionState: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            dashboard: null,
            filters: {},
            loading: true,
            error: null,
            draggingId: null,
        });
        onWillStart(() => this.load());
    }

    get canEdit() {
        return Boolean(this.state.dashboard && this.state.dashboard.can_edit);
    }

    get dashboardId() {
        const params = this.props.action.params || {};
        return params.dashboard_id || null;
    }

    get widgetList() {
        return this.state.dashboard ? this.state.dashboard.widgets : [];
    }

    get filterList() {
        return this.state.dashboard ? this.state.dashboard.filters : [];
    }

    get activeDashboardId() {
        return this.state.dashboard ? this.state.dashboard.id : null;
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const dashboard = this.dashboardId
                ? await this.orm.call(
                      "dashboard.suite",
                      "get_dashboard_data",
                      [[this.dashboardId], this.state.filters]
                  )
                : await this.orm.call(
                      "dashboard.suite",
                      "get_default_dashboard_data",
                      [this.state.filters]
                  );
            this.state.dashboard = dashboard;
        } catch (error) {
            this.state.error = errorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        await this.load();
    }

    async onFilterChange(filterId, value) {
        const filters = { ...this.state.filters };
        if (value === null || value === undefined || value === "") {
            filters[filterId] = null;
        } else {
            filters[filterId] = value;
        }
        this.state.filters = filters;
        await this.load();
    }

    async toggleFavorite() {
        if (!this.state.dashboard) {
            return;
        }
        try {
            await this.orm.call(
                "dashboard.suite",
                "action_toggle_favorite",
                [[this.activeDashboardId]]);
            this.state.dashboard.is_favorite = !this.state.dashboard.is_favorite;
        } catch (error) {
            this.notification.add(errorMessage(error), { type: "danger" });
        }
    }

    async editDashboard() {
        if (!this.state.dashboard) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: this.state.dashboard.name,
            res_model: "dashboard.suite",
            res_id: this.activeDashboardId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // Layout editing (drag & drop + resize)
    // ------------------------------------------------------------------
    onDragStart(event) {
        if (!this.canEdit) {
            return;
        }
        const card = event.target.closest(".o_ds_widget");
        if (!card) {
            return;
        }
        this.state.draggingId = Number(card.dataset.widgetId);
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(this.state.draggingId));
    }

    onDragOver(event) {
        if (!this.canEdit || !this.state.draggingId) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
    }

    async onDrop(event) {
        if (!this.canEdit || !this.state.draggingId) {
            return;
        }
        event.preventDefault();
        const draggedId = this.state.draggingId;
        this.state.draggingId = null;
        const widgets = [...this.widgetList];
        const from = widgets.findIndex((widget) => widget.id === draggedId);
        if (from < 0) {
            return;
        }
        let card = event.target.closest(".o_ds_widget");
        if (!card) {
            card = document
                .elementFromPoint(event.clientX, event.clientY)
                ?.closest(".o_ds_widget");
        }
        let to = widgets.length;
        if (card) {
            const targetIndex = widgets.findIndex(
                (widget) => widget.id === Number(card.dataset.widgetId)
            );
            if (targetIndex >= 0) {
                if (widgets[targetIndex].id === draggedId) {
                    return;
                }
                const rect = card.getBoundingClientRect();
                to = event.clientX < rect.left + rect.width / 2
                    ? targetIndex
                    : targetIndex + 1;
            }
        }
        if (to > from) {
            to -= 1;
        }
        if (to === from || to < 0) {
            return;
        }
        const [moved] = widgets.splice(from, 1);
        widgets.splice(to, 0, moved);
        this.state.dashboard.widgets = widgets;
        await this._persistLayout();
    }

    onDragEnd() {
        this.state.draggingId = null;
    }

    async onWidgetResize(widget, size) {
        if (!this.canEdit) {
            return;
        }
        const width = Math.min(Math.max(size.width, 1), 12);
        const height = Math.min(Math.max(size.height, 1), 6);
        if (width === widget.width && height === widget.height) {
            return;
        }
        widget.width = width;
        widget.height = height;
        try {
            await this.orm.call("dashboard.suite", "save_layout", [
                [this.activeDashboardId],
                [{ id: widget.id, width, height }],
            ]);
        } catch (error) {
            this.notification.add(errorMessage(error), { type: "danger" });
            await this.load();
        }
    }

    async _persistLayout() {
        const layout = this.widgetList.map((widget, index) => ({
            id: widget.id,
            sequence: (index + 1) * 10,
            width: widget.width,
            height: widget.height,
        }));
        for (const entry of layout) {
            const widget = this.widgetList.find((item) => item.id === entry.id);
            if (widget) {
                widget.sequence = entry.sequence;
            }
        }
        try {
            await this.orm.call("dashboard.suite", "save_layout", [
                [this.activeDashboardId],
                layout,
            ]);
        } catch (error) {
            this.notification.add(errorMessage(error), { type: "danger" });
            await this.load();
        }
    }
}

registry.category("actions").add(
    "dashboard_suite_core.dashboard_action", DashboardAction);
