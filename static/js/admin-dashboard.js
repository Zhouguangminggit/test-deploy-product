const chartElement = document.getElementById("module-chart");
const summary = JSON.parse(document.getElementById("module-counts").textContent);

if (window.echarts && summary.length) {
  chartElement.style.height = `${Math.max(180, summary.length * 30 + 48)}px`;
  chartElement.hidden = false;
  const chart = window.echarts.init(chartElement, null, { renderer: "svg" });
  chart.setOption({
    animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    aria: { enabled: true },
    grid: { left: 8, right: 40, top: 4, bottom: 24, outerBoundsMode: "same" },
    tooltip: { trigger: "axis", renderMode: "richText" },
    xAxis: { type: "value", minInterval: 1 },
    yAxis: {
      type: "category",
      inverse: true,
      data: summary.map((item) => item.name),
    },
    series: [{
      name: "记录数",
      type: "bar",
      data: summary.map((item) => item.value),
      barMaxWidth: 17,
      itemStyle: { color: "#286652", borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: "right" },
    }],
  });
  new ResizeObserver(() => chart.resize()).observe(chartElement);
}
