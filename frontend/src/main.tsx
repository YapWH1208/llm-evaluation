import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App, { SharedReportPage } from "./App";
import { LocaleProvider } from "./i18n/LocaleProvider";
import "./styles.css";
import "./workspace-theme.css";

const sharedReport = window.location.pathname.match(/^\/shared-reports\/([^/]+)\/?$/);

createRoot(document.getElementById("root")!).render(
  <StrictMode><LocaleProvider>{sharedReport ? <SharedReportPage token={decodeURIComponent(sharedReport[1])} /> : <App />}</LocaleProvider></StrictMode>,
);
