import { ReactNode } from "react";

import "./workspace-pages.css";

type PageHeaderProps = {
  actions?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  status?: ReactNode;
  title: ReactNode;
};

export function PageHeader({ actions, description, eyebrow, status, title }: PageHeaderProps) {
  return (
    <header className="workspace-page-header">
      <div className="workspace-page-header-copy">
        {eyebrow && <p className="workspace-page-eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="workspace-page-description">{description}</p>}
      </div>
      {(status || actions) && (
        <div className="workspace-page-header-actions">
          {status && <div className="workspace-page-status">{status}</div>}
          {actions}
        </div>
      )}
    </header>
  );
}
