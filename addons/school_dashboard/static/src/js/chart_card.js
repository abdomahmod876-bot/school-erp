/** @odoo-module **/

import { Component, useEffect, useRef } from "@odoo/owl";

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
    const r = (number >> 16) & 255;
    const g = (number >> 8) & 255;
    const b = number & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export class ChartCard extends Component {
    static template = "school_dashboard.ChartCard";
    static props = { item: Object };

    setup() {
        this.canvasRef = useRef("canvas");
        useEffect(
            () => {
                const element = this.canvasRef.el;
                const item = this.props.item;
                if (!element || item.kind !== "chart" || !(item.labels || []).length) {
                    return undefined;
                }
                if (!window.Chart) {
                    return undefined;
                }
                const chart = new window.Chart(element, this._chartConfig(item));
                return () => chart.destroy();
            },
            () => [this.props.item]
        );
    }

    get formattedValue() {
        const value = this.props.item.value;
        if (value === undefined || value === null) {
            return "0";
        }
        return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
    }

    _chartConfig(item) {
        const accent = item.color || "#6366f1";
        const isCircular = item.item_type === "pie" || item.item_type === "doughnut";
        let dataset;
        if (isCircular) {
            dataset = {
                data: item.values,
                backgroundColor: (item.values || []).map(
                    (_value, index) =>
                        index === 0 ? accent : PALETTE[(index + 1) % PALETTE.length]
                ),
                borderColor: "#ffffff",
                borderWidth: 2,
                hoverOffset: 6,
            };
        } else if (item.item_type === "line") {
            dataset = {
                data: item.values,
                borderColor: accent,
                backgroundColor: hexToRgba(accent, 0.16),
                fill: true,
                tension: 0.35,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: accent,
                pointBorderColor: "#ffffff",
            };
        } else {
            dataset = {
                data: item.values,
                backgroundColor: hexToRgba(accent, 0.85),
                hoverBackgroundColor: accent,
                borderRadius: 6,
                maxBarThickness: 48,
            };
        }
        return {
            type: item.item_type,
            data: {
                labels: item.labels,
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
                            color: "#475569",
                        },
                    },
                    tooltip: {
                        backgroundColor: "rgba(15, 23, 42, 0.92)",
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: true,
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
                              ticks: { color: "#64748b", precision: 0 },
                          },
                      },
            },
        };
    }
}
