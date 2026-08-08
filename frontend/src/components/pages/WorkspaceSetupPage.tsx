import { Children, ReactNode, useState } from "react";

import { PageHeader } from "../workspace/PageHeader";
import { WorkspaceTabs } from "../workspace/WorkspaceTabs";

type WorkspaceMode = "inputs" | "assets" | "suites" | "catalog";

type WorkspaceSetupPageProps = {
  assets?: ReactNode;
  catalog?: ReactNode;
  children?: ReactNode;
  inputs?: ReactNode;
  suites?: ReactNode;
};

const tabs: Array<{ id: WorkspaceMode; label: string }> = [
  { id: "inputs", label: "Inputs" },
  { id: "assets", label: "Assets" },
  { id: "suites", label: "Suites" },
  { id: "catalog", label: "Catalog" },
];

export function WorkspaceSetupPage({ assets, catalog, children, inputs, suites }: WorkspaceSetupPageProps) {
  const [mode, setMode] = useState<WorkspaceMode>("inputs");
  const panes: Record<WorkspaceMode, ReactNode> = { inputs, assets, suites, catalog };
  const usesLegacySections = children !== undefined;
  const legacySections = Children.toArray(children);
  const visibleLegacySections: Record<WorkspaceMode, number[]> = { inputs: [0], assets: [1], suites: [2], catalog: [3, 4] };

  return (
    <div className={usesLegacySections ? "workspace-page workspace-setup-page workspace-setup-page--legacy" : "workspace-page workspace-setup-page"} data-workspace-mode={mode}>
      <PageHeader description="Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup." eyebrow="Configure" status="4 workbench modes" title="Workspace" />
      <WorkspaceTabs onChange={setMode} tabs={tabs} value={mode} />
      {usesLegacySections ? <div className="workspace-setup-content">{legacySections.map((section, index) => <div hidden={!visibleLegacySections[mode].includes(index)} key={index}>{section}</div>)}</div> : tabs.map((tab) => <section aria-label={`${tab.label} workspace`} className="workspace-tab-panel" hidden={mode !== tab.id} key={tab.id} role="tabpanel">{panes[tab.id]}</section>)}
    </div>
  );
}
