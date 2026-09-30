/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PALETTE = ["#2E5EAA", "#1F9D8B", "#8E6CC0", "#E0A100", "#D64545", "#3FA7D6", "#F28E2B", "#59A14F", "#B07AA1", "#9AA5B1"];

// canvas ref -> [data key, chart type, extra options]
const CHARTS = {
    stageCanvas: ["placements_by_stage", "bar", { indexAxis: "x" }],
    phaseCanvas: ["placements_by_phase", "doughnut", {}],
    riskCanvas: ["risk", "doughnut", {}],
    applicationsCanvas: ["applications", "bar", { indexAxis: "y" }],
    leadsStageCanvas: ["leads_by_stage", "bar", { indexAxis: "y" }],
    leadsSourceCanvas: ["leads_by_source", "pie", {}],
    attendanceCanvas: ["attendance_trend", "line", {}],
    callsCanvas: ["calls_by_week", "bar", { indexAxis: "x" }],
};

export class InternshipDashboard extends Component {
    static template = "internship_reporting.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, universityId: "" });
        this.canvasRefs = Object.fromEntries(Object.keys(CHARTS).map((name) => [name, useRef(name)]));
        this.charts = [];

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        useEffect(
            () => {
                this.renderCharts();
                return () => this.destroyCharts();
            },
            () => [this.state.data]
        );
        onWillUnmount(() => this.destroyCharts());
    }

    async load() {
        this.state.data = await this.orm.call("internship.dashboard", "get_dashboard_data", [], {
            university_id: this.state.universityId ? parseInt(this.state.universityId) : false,
        });
    }

    async onUniversityChange(ev) {
        this.state.universityId = ev.target.value;
        await this.load();
    }

    destroyCharts() {
        for (const chart of this.charts) {
            chart.destroy();
        }
        this.charts = [];
    }

    renderCharts() {
        this.destroyCharts();
        if (!this.state.data) {
            return;
        }
        for (const [refName, [key, type, extra]] of Object.entries(CHARTS)) {
            const canvas = this.canvasRefs[refName].el;
            const series = this.state.data.charts[key];
            if (!canvas || !series) {
                continue;
            }
            this.charts.push(new Chart(canvas, this.chartConfig(series, type, extra)));
        }
    }

    chartConfig(series, type, extra) {
        const colors = series.labels.map((_, i) => series.colors[i] || PALETTE[i % PALETTE.length]);
        const round = type === "doughnut" || type === "pie";
        const datasets = [
            {
                label: series.label,
                data: series.values,
                backgroundColor: type === "line" ? "rgba(46, 94, 170, 0.15)" : colors,
                borderColor: type === "line" ? "#2E5EAA" : round ? "#ffffff" : colors,
                borderWidth: type === "line" ? 2 : 1,
                fill: type === "line",
                tension: 0.3,
                pointRadius: 4,
                borderRadius: type === "bar" ? 4 : 0,
            },
        ];
        if (type === "line" && series.threshold) {
            datasets.push({
                label: _t("Tripartite threshold"),
                data: series.labels.map(() => series.threshold),
                borderColor: "#D64545",
                borderDash: [6, 4],
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
            });
        }
        return {
            type,
            data: { labels: series.labels, datasets },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                indexAxis: extra.indexAxis || "x",
                plugins: {
                    legend: { display: round || (type === "line" && datasets.length > 1), position: "bottom" },
                    tooltip: { enabled: true },
                },
                scales: round
                    ? {}
                    : {
                          x: { beginAtZero: true, ticks: { precision: 0 } },
                          y: {
                              beginAtZero: true,
                              ticks: { precision: 0 },
                              max: type === "line" ? 100 : undefined,
                          },
                      },
                onClick: (_event, elements) => {
                    if (elements.length && elements[0].datasetIndex === 0) {
                        const index = elements[0].index;
                        this.openRecords(series.model, series.domains[index], `${series.label}: ${series.labels[index]}`);
                    }
                },
            },
        };
    }

    openRecords(model, domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openKpi(kpi) {
        this.openRecords(kpi.model, kpi.domain, kpi.label);
    }

    openPlacement(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "internship.placement", res_id: id, views: [[false, "form"]] });
    }

    openLead(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "crm.lead", res_id: id, views: [[false, "form"]] });
    }
}

registry.category("actions").add("internship_dashboard", InternshipDashboard);
