import { KeyboardEvent, useRef } from "react";

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
  const tabListRef = useRef<HTMLDivElement>(null);

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) {
    const lastIndex = tabs.length - 1;
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1;
    if (event.key === "ArrowLeft") nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = lastIndex;
    if (nextIndex === null) return;

    event.preventDefault();
    onChange(tabs[nextIndex].id);
    tabListRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[nextIndex]?.focus();
  }

  return (
    <div aria-label="Workspace sections" className="workspace-tabs" ref={tabListRef} role="tablist">
      {tabs.map((tab, index) => (
        <button
          aria-selected={tab.id === value}
          className={tab.id === value ? "workspace-tab is-active" : "workspace-tab"}
          key={tab.id}
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => moveFocus(event, index)}
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
