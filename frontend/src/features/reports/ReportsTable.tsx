import { useState } from "react";

import { reportCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { reportsApi, type Report } from "./api";

export function ReportsTable({ reports, onDelete }: { reports: Report[]; onDelete: (report: Report) => void }) {
  const { formatDate, locale } = useTranslation();
  const copy = reportCopy[locale];
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function downloadReport(report: Report) {
    setDownloadError(null);
    try {
      const objectUrl = await reportsApi.download(report.id);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `evaluation-report.${report.format === "markdown" ? "md" : report.format}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : copy.downloadFailed);
    }
  }

  if (reports.length === 0) return <p className="empty">{copy.noArtifacts}</p>;
  return <>
    {downloadError && <p className="error" role="alert">{downloadError}</p>}
    <div className="table-wrap"><table><thead><tr><th>{copy.format}</th><th>{copy.generated}</th><th>{copy.version}</th><th /></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.format}</td><td>{formatDate(report.generated_at)}</td><td>{report.generator_version}</td><td><div className="actions"><button className="secondary" onClick={() => void downloadReport(report)}>{copy.download}</button><button className="danger" onClick={() => onDelete(report)}>{copy.delete}</button></div></td></tr>)}</tbody></table></div>
  </>;
}
