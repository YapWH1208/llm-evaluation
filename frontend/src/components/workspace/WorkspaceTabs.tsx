type WorkspaceTab<T extends string> = {
  id: T;
  label: string;
};

type WorkspaceTabsProps<T extends string> = {
  onChange: (value: T) => void;
  tabs: readonly WorkspaceTab<T>[];
  value: T;
};

export function WorkspaceTabs<T extends string>({ onChange, tabs, value }: WorkspaceTabsProps<T>) {
  return (
    <div aria-label="Workspace sections" className="workspace-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          aria-controls={`workspace-tabpanel-${tab.id}`}
          aria-selected={tab.id === value}
          className={tab.id === value ? "workspace-tab is-active" : "workspace-tab"}
          id={`workspace-tab-${tab.id}`}
          key={tab.id}
          onClick={() => onChange(tab.id)}
          role="tab"
          tabIndex={tab.id === value ? 0 : -1}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
