import { ReactNode, useState } from "react";

import { PageHeader } from "../workspace/PageHeader";
import { WorkspaceTabs } from "../workspace/WorkspaceTabs";

type WorkspaceMode = "inputs" | "assets" | "suites" | "catalog";

type WorkspaceSetupPageProps = {
  assets: ReactNode;
  catalog: ReactNode;
  inputs: ReactNode;
  suites: ReactNode;
};

const tabs: Array<{ id: WorkspaceMode; label: string }> = [
  { id: "inputs", label: "Inputs" },
  { id: "assets", label: "Assets" },
  { id: "suites", label: "Suites" },
  { id: "catalog", label: "Catalog" },
];

export function WorkspaceSetupPage({ assets, catalog, inputs, suites }: WorkspaceSetupPageProps) {
  const [mode, setMode] = useState<WorkspaceMode>("inputs");
  const panes: Record<WorkspaceMode, ReactNode> = { inputs, assets, suites, catalog };

  return (
    <div className="workspace-page workspace-setup-page" data-workspace-mode={mode}>
      <PageHeader description="Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup." eyebrow="Configure" status="4 workbench modes" title="Workspace" />
      <WorkspaceTabs onChange={setMode} tabs={tabs} value={mode} />
      {tabs.map((tab) => <section aria-labelledby={`workspace-tab-${tab.id}`} className="workspace-tab-panel" hidden={mode !== tab.id} id={`workspace-tabpanel-${tab.id}`} key={tab.id} role="tabpanel">{panes[tab.id]}</section>)}
    </div>
  );
}
