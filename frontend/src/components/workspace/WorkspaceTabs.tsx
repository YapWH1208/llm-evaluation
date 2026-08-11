import { type KeyboardEvent, useRef } from "react";

type WorkspaceTab<T extends string> = {
  description?: string;
  id: T;
  label: string;
};

type WorkspaceTabsProps<T extends string> = {
  ariaLabel?: string;
  idPrefix?: string;
  onChange: (value: T) => void;
  tabs: readonly WorkspaceTab<T>[];
  value: T;
};

export function workspaceTabId(prefix: string, id: string) {
  return `${prefix}-tab-${id}`;
}

export function workspaceTabPanelId(prefix: string, id: string) {
  return `${prefix}-tabpanel-${id}`;
}

export function WorkspaceTabs<T extends string>({
  ariaLabel = "Workspace sections",
  idPrefix = "workspace",
  onChange,
  tabs,
  value,
}: WorkspaceTabsProps<T>) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function activateTab(index: number) {
    const tab = tabs[index];
    if (!tab) return;
    tabRefs.current[index]?.focus();
    onChange(tab.id);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    activateTab(nextIndex);
  }

  return (
    <div aria-label={ariaLabel} className="workspace-tabs" role="tablist">
      {tabs.map((tab, index) => (
        <button
          aria-label={tab.label}
          aria-selected={tab.id === value}
          className={tab.id === value ? "workspace-tab is-active" : "workspace-tab"}
          id={workspaceTabId(idPrefix, tab.id)}
          key={tab.id}
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => handleKeyDown(event, index)}
          ref={(node) => { tabRefs.current[index] = node; }}
          role="tab"
          tabIndex={tab.id === value ? 0 : -1}
          type="button"
          {...(tab.id === value ? { "aria-controls": workspaceTabPanelId(idPrefix, tab.id) } : {})}
        >
          <span className="workspace-tab-label">{tab.label}</span>
          {tab.description && <small className="workspace-tab-description">{tab.description}</small>}
        </button>
      ))}
    </div>
  );
}
