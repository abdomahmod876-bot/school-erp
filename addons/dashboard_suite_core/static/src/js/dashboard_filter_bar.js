/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DashboardFilterBar extends Component {
    static template = "dashboard_suite_core.DashboardFilterBar";
    static props = {
        dashboardId: Number,
        filters: Array,
        values: Object,
        onChange: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ options: {} });
        onWillStart(async () => {
            const options = {};
            for (const filter of this.props.filters) {
                if (filter.filter_type === "date") {
                    continue;
                }
                try {
                    const data = await this.orm.call(
                        "dashboard.suite",
                        "get_filter_options",
                        [[this.props.dashboardId], filter.id]
                    );
                    options[filter.id] = data.options || [];
                } catch {
                    options[filter.id] = [];
                }
            }
            this.state.options = options;
        });
    }

    optionsFor(filter) {
        return this.state.options[filter.id] || [];
    }

    displayValue(filter) {
        const value = this.props.values[filter.id];
        if (value === null || value === undefined) {
            return "";
        }
        if (typeof value === "object") {
            return value.from || value.to || "";
        }
        return String(value);
    }

    isSelected(filter, optionValue) {
        return String(optionValue) === String(this.displayValue(filter));
    }
}
