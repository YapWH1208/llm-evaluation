export type View =
  | "dashboard"
  | "models"
  | "capabilities"
  | "workspace"
  | "benchmarks"
  | "datasets"
  | "suites"
  | "runs"
  | "queue"
  | "workers"
  | "analysis"
  | "compare"
  | "reports"
  | "reviews"
  | "users"
  | "settings";

export type Locale = "en" | "zh-CN";

type LocalizedText = Record<Locale, string>;

export type NavigationItem = {
  view: View;
  glyph: string;
  label: LocalizedText;
  description: LocalizedText;
};

export type NavigationGroup = {
  id: "overview" | "configure" | "operations" | "insights" | "system";
  label: LocalizedText;
  items: NavigationItem[];
};

export const navigationGroups: NavigationGroup[] = [
  {
    id: "overview",
    label: { en: "Overview", "zh-CN": "概览" },
    items: [
      {
        view: "dashboard",
        glyph: "⌂",
        label: { en: "Dashboard", "zh-CN": "仪表盘" },
        description: { en: "Operational status and recent work", "zh-CN": "运行状态和最近工作" },
      },
    ],
  },
  {
    id: "configure",
    label: { en: "Configure", "zh-CN": "配置" },
    items: [
      {
        view: "models",
        glyph: "◌",
        label: { en: "Models", "zh-CN": "模型" },
        description: { en: "Endpoints and run defaults", "zh-CN": "端点和运行默认值" },
      },
      {
        view: "capabilities",
        glyph: "✦",
        label: { en: "Capabilities", "zh-CN": "能力" },
        description: { en: "Detection and declarations", "zh-CN": "检测和声明" },
      },
      {
        view: "workspace",
        glyph: "◫",
        label: { en: "Workspace", "zh-CN": "工作区" },
        description: { en: "Prompts, assets, and setup", "zh-CN": "提示词、资产和设置" },
      },
      {
        view: "benchmarks",
        glyph: "▤",
        label: { en: "Benchmarks", "zh-CN": "评测基准" },
        description: { en: "Benchmark registry", "zh-CN": "评测基准注册表" },
      },
      {
        view: "datasets",
        glyph: "▥",
        label: { en: "Datasets", "zh-CN": "数据集" },
        description: { en: "Versioned data sources", "zh-CN": "版本化数据源" },
      },
      {
        view: "suites",
        glyph: "◷",
        label: { en: "Suites", "zh-CN": "评测套件" },
        description: { en: "Reusable evaluation suites", "zh-CN": "可复用评测套件" },
      },
    ],
  },
  {
    id: "operations",
    label: { en: "Operations", "zh-CN": "运行" },
    items: [
      {
        view: "runs",
        glyph: "▶",
        label: { en: "Runs", "zh-CN": "运行任务" },
        description: { en: "Execution, results, and evidence", "zh-CN": "执行、结果和证据" },
      },
      {
        view: "queue",
        glyph: "≋",
        label: { en: "Task queue", "zh-CN": "任务队列" },
        description: { en: "Priorities and pending work", "zh-CN": "优先级和待处理工作" },
      },
      {
        view: "workers",
        glyph: "◉",
        label: { en: "Workers", "zh-CN": "工作节点" },
        description: { en: "Leases and active workers", "zh-CN": "租约和活动节点" },
      },
    ],
  },
  {
    id: "insights",
    label: { en: "Insights", "zh-CN": "洞察" },
    items: [
      {
        view: "analysis",
        glyph: "◒",
        label: { en: "Analysis", "zh-CN": "分析" },
        description: { en: "Capability and trend evidence", "zh-CN": "能力和趋势证据" },
      },
      {
        view: "compare",
        glyph: "⇄",
        label: { en: "Compare", "zh-CN": "对比" },
        description: { en: "Run-to-run comparisons", "zh-CN": "运行之间的对比" },
      },
      {
        view: "reports",
        glyph: "▱",
        label: { en: "Reports", "zh-CN": "报告" },
        description: { en: "Exports and shared artifacts", "zh-CN": "导出和共享产物" },
      },
      {
        view: "reviews",
        glyph: "✓",
        label: { en: "Human review", "zh-CN": "人工评审" },
        description: { en: "Review and adjudication", "zh-CN": "评审和裁决" },
      },
    ],
  },
  {
    id: "system",
    label: { en: "System", "zh-CN": "系统" },
    items: [
      {
        view: "users",
        glyph: "◍",
        label: { en: "Users", "zh-CN": "用户" },
        description: { en: "Users and audit activity", "zh-CN": "用户和审计活动" },
      },
      {
        view: "settings",
        glyph: "⚙",
        label: { en: "Settings", "zh-CN": "设置" },
        description: { en: "Health, access, and preferences", "zh-CN": "健康、访问和偏好" },
      },
    ],
  },
];

export const navigationItems = navigationGroups.flatMap((group) => group.items);

export function navigationItem(view: View) {
  const item = navigationItems.find((candidate) => candidate.view === view);
  if (!item) throw new Error(`Unknown workspace view: ${view}`);
  return item;
}

export function navigationGroupFor(view: View) {
  const group = navigationGroups.find((candidate) => candidate.items.some((item) => item.view === view));
  if (!group) throw new Error(`Unknown workspace view: ${view}`);
  return group;
}
