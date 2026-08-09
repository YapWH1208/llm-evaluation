import { ReactNode, useId } from "react";

type WorkspacePanelProps = {
  children?: ReactNode;
  className?: string;
  description?: ReactNode;
  title?: ReactNode;
  toolbar?: ReactNode;
  variant?: "default" | "muted" | "inset";
};

export function WorkspacePanel({ children, className, description, title, toolbar, variant = "default" }: WorkspacePanelProps) {
  const headingId = useId();
  const inferredTitle = title ?? (typeof children === "string" ? children : undefined);
  const content = title === undefined && typeof children === "string" ? null : children;
  const classes = ["workspace-panel", `workspace-panel--${variant}`, className].filter(Boolean).join(" ");

  return (
    <section aria-labelledby={inferredTitle ? headingId : undefined} className={classes}>
      {(inferredTitle || description || toolbar) && (
        <div className="workspace-panel-heading">
          <div>
            {inferredTitle && <h2 id={headingId}>{inferredTitle}</h2>}
            {description && <p>{description}</p>}
          </div>
          {toolbar && <div className="workspace-panel-toolbar">{toolbar}</div>}
        </div>
      )}
      {content}
    </section>
  );
}
