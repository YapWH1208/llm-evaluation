import type { WorkspaceNavigate, WorkspaceTabFor } from "../dashboard/routing";
import type { WorkspaceView } from "../i18n/catalog";

export type ShowNotice = (template: string, values?: Record<string, string | number>) => void;

export type FeatureRouteProps<V extends WorkspaceView> = {
  activeTab: WorkspaceTabFor<V>;
  navigate: WorkspaceNavigate;
  reportError: (error: unknown) => void;
  showNotice: ShowNotice;
};
