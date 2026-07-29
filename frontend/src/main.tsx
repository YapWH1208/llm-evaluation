import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App, { SharedReportPage } from "./App";
import "./styles.css";

const sharedReport = window.location.pathname.match(/^\/shared-reports\/([^/]+)\/?$/);

createRoot(document.getElementById("root")!).render(
  <StrictMode>{sharedReport ? <SharedReportPage token={decodeURIComponent(sharedReport[1])} /> : <App />}</StrictMode>,
);
