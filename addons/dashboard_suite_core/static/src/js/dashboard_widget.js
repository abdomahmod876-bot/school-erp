/** @odoo-module **/

import {
    Component,
    onWillUpdateProps,
    useEffect,
    useRef,
    useState,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const PALETTE = [
    "#6366f1",
    "#22c55e",
    "#f59e0b",
    "#ef4444",
    "#0ea5e9",
    "#a855f7",
    "#14b8a6",
    "#f97316",
    "#64748b",
    "#e11d48",
];

function hexToRgba(hex, alpha) {
    let value = (hex || "#6366f1").replace("#", "");
    if (value.length === 3) {
        value = value
            .split("")
            .map((char) => char + char)
            .join("");
    }
    const number = parseInt(value, 16);
    return `rgba(${(number >> 16) & 255}, ${(number >> 8) & 255}, ${number & 255}, ${alpha})`;
}

function formatNumber(value, maximumFractionDigits = 2) {
    if (value === null || value === undefined) {
        return "0";
    }
    return new Intl.NumberFormat(undefined, {
        maximumFractionDigits,
    }).format(value);
}

export class DashboardWidget extends Component {
    static template = "dashboard_suite_core.DashboardWidget";
    static props = {
        widget: Object,
        dashboardId: Number,
        filters: Object,
        canEdit: { type: Boolean, optional: true },
        dragging: { type: Boolean, optional: true },
        onResize: { type: Function, optional: true },
    };

    setup() {
        this.rootRef = useRef("root");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ preview: null, resizing: false });
    }

    get widgetStyle() {
        const widget = this.props.widget;
        const width = Math.min(
            Math.max((this.state.preview || widget).width || 4, 1),
            12
        );
        const height = Math.max((this.state.preview || widget).height || 2, 1);
        return `grid-column: span ${width}; min-height: ${height * 92}px;`;
    }

    get progressWidth() {
        const progress = this.props.widget.progress;
        if (progress === null || progress === undefined) {
            return 0;
        }
        return Math.min(Math.max(progress, 0), 100);
    }

    formatNumber(value) {
        return formatNumber(value);
    }

    get canExport() {
        const widget = this.props.widget;
        return (
            !widget.error &&
            (widget.widget_type === "table" || widget.widget_type === "chart")
        );
    }

    async exportCsv() {
        try {
            const data = await this.orm.call(
                "dashboard.suite",
                "export_widget_data",
                [
                    [this.props.dashboardId],
                    this.props.widget.id,
                    this.props.filters,
                    null,
                ]
            );
            const binary = atob(data.content);
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index++) {
                bytes[index] = binary.charCodeAt(index);
            }
            const blob = new Blob([bytes], {
                type: data.mimetype || "text/csv",
            });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = data.filename || "dashboard.csv";
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) ||
                    error.message ||
                    _t("Could not export the widget."),
                { type: "danger" }
            );
        }
    }

    measureLabel(widget) {
        if (widget.measure && widget.measure.label) {
            return widget.measure.label;
        }
        return _t("Count");
    }

    onResizeStart(event) {
        if (!this.props.canEdit || !this.props.onResize) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const card = this.rootRef.el;
        const grid = card.closest(".o_ds_grid");
        if (!grid) {
            return;
        }
        const widget = this.props.widget;
        const startX = event.clientX;
        const startY = event.clientY;
        const startWidth = Math.min(Math.max(widget.width || 4, 1), 12);
        const startHeight = Math.max(widget.height || 2, 1);
        const startWidthPx = card.offsetWidth;
        const gap = parseFloat(getComputedStyle(grid).columnGap) || 16;
        const columnWidth = (grid.clientWidth - gap * 11) / 12;
        this.state.resizing = true;
        const onMove = (moveEvent) => {
            const widthPx = startWidthPx + moveEvent.clientX - startX;
            const width = Math.min(
                Math.max(Math.round((widthPx + gap) / (columnWidth + gap)), 1),
                12
            );
            const height = Math.min(
                Math.max(
                    startHeight +
                        Math.round((moveEvent.clientY - startY) / 92),
                    1
                ),
                6
            );
            this.state.preview = { width, height };
        };
        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            const preview = this.state.preview;
            this.state.preview = null;
            this.state.resizing = false;
            if (
                preview &&
                (preview.width !== startWidth || preview.height !== startHeight)
            ) {
                this.props.onResize(widget, preview);
            }
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
    }
}

export class DashboardChart extends Component {
    static template = "dashboard_suite_core.DashboardChart";
    static props = { widget: Object };

    setup() {
        this.canvasRef = useRef("canvas");
        useEffect(
            () => {
                const element = this.canvasRef.el;
                const widget = this.props.widget;
                const labels = widget.labels || [];
                if (!element || !labels.length || !window.Chart) {
                    return undefined;
                }
                const chart = new window.Chart(element, this.chartConfig(widget));
                return () => chart.destroy();
            },
            () => [this.props.widget]
        );
    }

    chartConfig(widget) {
        const chartType = widget.chart_type === "area" ? "line" : widget.chart_type;
        const isCircular = chartType === "pie" || chartType === "doughnut";
        const values = (widget.datasets && widget.datasets[0] && widget.datasets[0].data) || [];
        const accent = (widget.config && widget.config.color) || PALETTE[0];
        const currency = widget.currency;
        const symbol = currency ? currency.symbol : "";
        const symbolBefore = !currency || currency.position !== "after";
        const formatTooltip = (value) => {
            const text = formatNumber(value);
            return symbolBefore ? `${symbol}${text}` : `${text} ${symbol}`;
        };
        let dataset;
        if (isCircular) {
            dataset = {
                data: values,
                backgroundColor: values.map(
                    (_value, index) => PALETTE[index % PALETTE.length]
                ),
                borderColor: "#ffffff",
                borderWidth: 2,
                hoverOffset: 6,
            };
        } else if (chartType === "line") {
            dataset = {
                data: values,
                borderColor: accent,
                backgroundColor: hexToRgba(accent, 0.16),
                fill: widget.chart_type === "area",
                tension: 0.35,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: accent,
                pointBorderColor: "#ffffff",
            };
        } else {
            dataset = {
                data: values,
                backgroundColor: hexToRgba(accent, 0.85),
                hoverBackgroundColor: accent,
                borderRadius: 6,
                maxBarThickness: 48,
            };
        }
        return {
            type: chartType,
            data: {
                labels: widget.labels || [],
                datasets: [dataset],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 450 },
                plugins: {
                    legend: {
                        display: isCircular,
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                            color: "#64748b",
                        },
                    },
                    tooltip: {
                        backgroundColor: "rgba(15, 23, 42, 0.92)",
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: (context) => {
                                const parsed = context.parsed;
                                const raw =
                                    parsed && typeof parsed === "object"
                                        ? parsed.y
                                        : parsed;
                                const prefix =
                                    chartType === "pie" || chartType === "doughnut"
                                        ? `${context.label}: `
                                        : "";
                                return `${prefix}${formatTooltip(raw ?? 0)}`;
                            },
                        },
                    },
                },
                scales: isCircular
                    ? {}
                    : {
                          x: {
                              grid: { display: false },
                              ticks: {
                                  maxRotation: 0,
                                  autoSkip: true,
                                  color: "#64748b",
                              },
                          },
                          y: {
                              beginAtZero: true,
                              grid: { color: "rgba(148, 163, 184, 0.18)" },
                              ticks: {
                                  color: "#64748b",
                                  callback: (value) => formatNumber(value, 2),
                              },
                          },
                      },
            },
        };
    }
}

export class DashboardTable extends Component {
    static template = "dashboard_suite_core.DashboardTable";
    static props = {
        widget: Object,
        dashboardId: Number,
        filters: Object,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState(this.initialState(this.props.widget));
        onWillUpdateProps((nextProps) => {
            if (nextProps.widget !== this.props.widget) {
                Object.assign(this.state, this.initialState(nextProps.widget));
            }
        });
    }

    initialState(widget) {
        return {
            rows: widget.rows || [],
            columns: widget.columns || [],
            offset: widget.offset || 0,
            total: widget.total || 0,
            hasMore: Boolean(widget.has_more),
            loading: false,
        };
    }

    get pageSize() {
        return this.props.widget.limit || 10;
    }

    get rangeLabel() {
        if (!this.state.total) {
            return "0 / 0";
        }
        const start = this.state.offset + 1;
        const end = this.state.offset + this.state.rows.length;
        return `${start}-${end} / ${this.state.total}`;
    }

    formatCell(value) {
        if (value === null || value === undefined) {
            return "";
        }
        if (typeof value === "boolean") {
            return value ? "✓" : "—";
        }
        if (typeof value === "number") {
            return formatNumber(value);
        }
        return value;
    }

    async loadPage(offset) {
        if (offset < 0 || this.state.loading) {
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "dashboard.suite",
                "get_widget_data",
                [
                    [this.props.dashboardId],
                    this.props.widget.id,
                    offset,
                    this.pageSize,
                    null,
                    this.props.filters,
                ]
            );
            this.state.rows = data.rows || [];
            this.state.columns = data.columns || [];
            this.state.offset = data.offset || 0;
            this.state.total = data.total || 0;
            this.state.hasMore = Boolean(data.has_more);
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) ||
                    error.message ||
                    _t("Could not load the table."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    previous() {
        this.loadPage(Math.max(this.state.offset - this.pageSize, 0));
    }

    next() {
        this.loadPage(this.state.offset + this.pageSize);
    }
}

DashboardWidget.components = { DashboardChart, DashboardTable };
