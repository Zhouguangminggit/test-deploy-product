/** Tailwind CSS 配置（v3.x）。
 *  content 指定需要扫描的模板，Tailwind 据此生成用到的样式类。
 *  已预留 apps 目录下各业务模板的扫描路径（供第二步使用）。
 *
 * @type {import('tailwindcss').Config}
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
  ],
  theme: {
    extend: {
      // 可按团队品牌色在此扩展，例如：
      // colors: { brand: { DEFAULT: "#2563eb" } },
    },
  },
  plugins: [
    // 为 Django 默认渲染的表单控件提供基础样式
    require("@tailwindcss/forms"),
  ],
};
