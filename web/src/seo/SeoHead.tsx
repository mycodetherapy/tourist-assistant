import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { canonicalUrl, resolvePageSeo, SITE_ORIGIN } from "./site";

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  const selector = `meta[${attr}="${key}"]`;
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function upsertLink(rel: string, href: string) {
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/** Title / description / canonical / robots по маршруту — для отрисовки Googlebot. */
export function SeoHead() {
  const { pathname } = useLocation();

  useEffect(() => {
    const page = resolvePageSeo(pathname);
    const url = canonicalUrl(page.canonicalPath);
    document.title = page.title;
    upsertMeta("name", "description", page.description);
    upsertMeta("name", "robots", page.robots);
    upsertLink("canonical", url);
    upsertMeta("property", "og:title", page.title);
    upsertMeta("property", "og:description", page.description);
    upsertMeta("property", "og:url", url);
    upsertMeta("property", "og:type", page.canonicalPath === "/" ? "website" : "article");
    upsertMeta("property", "og:locale", "ru_RU");
    upsertMeta("property", "og:site_name", "Прогуляй");
    upsertMeta("property", "og:image", `${SITE_ORIGIN}/icons/icon-512.png`);
  }, [pathname]);

  return null;
}
