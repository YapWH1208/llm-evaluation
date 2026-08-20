import { useCallback, useEffect, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { PromptPackagesPage, type PromptPackageCreatePayload } from "../../components/pages/PromptPackagesPage";
import { useTranslation } from "../../i18n/LocaleProvider";
import { benchmarksApi, type PromptPackage } from "./api";

export function PromptsRoute({ activeTab, navigate, reportError, showNotice }: FeatureRouteProps<"prompts">) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [prompts, setPrompts] = useState<PromptPackage[]>([]);
  const refresh = useCallback(async () => setPrompts(await benchmarksApi.listPrompts()), []);

  useEffect(() => { void refresh().catch(reportError); }, [refresh, reportError]);

  async function createPrompt(payload: PromptPackageCreatePayload) {
    setBusy("prompt-package-create");
    try {
      const created = await benchmarksApi.createPrompt({ ...payload });
      showNotice(t("promptPackage.savedNotice"));
      await refresh();
      return created;
    } catch (error) {
      reportError(error);
      throw error;
    } finally { setBusy(null); }
  }

  async function updatePrompt(promptId: string, payload: PromptPackageCreatePayload) {
    setBusy(`prompt-package-update-${promptId}`);
    try {
      const updated = await benchmarksApi.updatePrompt(promptId, { ...payload });
      showNotice(t("promptPackage.updatedNotice"));
      await refresh();
      return updated;
    } catch (error) {
      reportError(error);
      throw error;
    } finally { setBusy(null); }
  }

  async function deletePrompt(promptId: string) {
    setBusy(`prompt-package-delete-${promptId}`);
    try {
      await benchmarksApi.removePrompt(promptId);
      showNotice(t("promptPackage.deletedNotice"));
      await refresh();
    } catch (error) {
      reportError(error);
      throw error;
    } finally { setBusy(null); }
  }

  return <PromptPackagesPage activeTab={activeTab} busy={busy} onCreate={createPrompt} onDelete={deletePrompt} onTabChange={(tab) => navigate("prompts", { tab })} onUpdate={updatePrompt} prompts={prompts} />;
}
