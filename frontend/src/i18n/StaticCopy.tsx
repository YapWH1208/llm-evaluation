import { ReactNode, useLayoutEffect, useRef } from "react";
import { translateStaticText } from "./operationalCopy";
import { useTranslation } from "./LocaleProvider";

const protectedSelector = "pre, code, textarea, input, [data-i18n-preserve], .evidence, .review, .badge";
const protectedAttributeSelector = "pre, code, [data-i18n-preserve], .evidence, .review, .badge";
const attributeNames = ["placeholder", "aria-label", "title"] as const;
const serverStatusValues = new Set(["available", "unavailable", "pending", "queued", "running", "paused", "completed", "completed_with_errors", "cancelled", "failed", "ready", "downloading", "waiting", "disabled", "enabled", "registered", "deprecated", "broken", "supported", "unsupported", "unknown", "succeeded", "unreviewed", "reviewed", "adjudicated"]);

function isProtected(node: Text) {
  const parent = node.parentElement;
  if (parent?.closest(protectedSelector)) return true;
  return parent?.tagName !== "OPTION" && serverStatusValues.has(node.nodeValue?.trim().toLowerCase() ?? "");
}

/**
 * Translates static UI nodes from the catalog while leaving API responses,
 * status badges, raw evidence, and user-authored values untouched.
 */
export function StaticCopy({ children }: { children: ReactNode }) {
  const { locale } = useTranslation();
  const root = useRef<HTMLDivElement>(null);
  const textState = useRef(new WeakMap<Text, { source: string; last: string }>());
  const attributeState = useRef(new WeakMap<HTMLElement, Record<string, { source: string; last: string }>>());

  useLayoutEffect(() => {
    const translate = () => {
      const element = root.current;
      if (!element) return;
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const nodes: Text[] = [];
      while (walker.nextNode()) nodes.push(walker.currentNode as Text);
      nodes.forEach((node) => {
        if (isProtected(node) || !node.nodeValue?.trim()) return;
        const current = node.nodeValue;
        const previous = textState.current.get(node);
        const source = previous && current === previous.last ? previous.source : current;
        const translated = locale === "en" ? source : translateStaticText(locale, source);
        if (translated !== node.nodeValue) node.nodeValue = translated;
        textState.current.set(node, { source, last: translated });
      });
      element.querySelectorAll<HTMLElement>("[placeholder], [aria-label], [title]").forEach((node) => {
        if (node.closest(protectedAttributeSelector)) return;
        const state = attributeState.current.get(node) ?? {};
        attributeNames.forEach((name) => {
          const current = node.getAttribute(name);
          if (!current) return;
          const previous = state[name];
          const source = previous && current === previous.last ? previous.source : current;
          const translated = locale === "en" ? source : translateStaticText(locale, source);
          if (translated !== current) node.setAttribute(name, translated);
          state[name] = { source, last: translated };
        });
        attributeState.current.set(node, state);
      });
    };
    translate();
    const observer = new MutationObserver(translate);
    if (root.current) observer.observe(root.current, { attributes: true, attributeFilter: [...attributeNames], characterData: true, childList: true, subtree: true });
    return () => observer.disconnect();
  }, [locale]);

  return <div className="localized-static-copy" ref={root}>{children}</div>;
}
