// Roteamento por hash: o site é estático e pode ser servido de qualquer lugar.
import { useEffect, useState } from "react";

export type Route =
  | { name: "login" }
  | { name: "home" }
  | { name: "profiles" }
  | { name: "settings" }
  | { name: "batch"; id: string }
  | { name: "review"; id: string }
  | { name: "sequence"; id: string; doc?: string }
  | { name: "metadata"; id: string; doc?: string }
  | { name: "reports"; id: string };

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  const [head, id, sub, extra] = parts;
  if (head === "login") return { name: "login" };
  if (head === "profiles") return { name: "profiles" };
  if (head === "settings") return { name: "settings" };
  if (head === "batches" && id) {
    if (sub === "review") return { name: "review", id };
    if (sub === "sequence") return { name: "sequence", id, doc: extra };
    if (sub === "metadata") return { name: "metadata", id, doc: extra };
    if (sub === "reports") return { name: "reports", id };
    return { name: "batch", id };
  }
  return { name: "home" };
}

export function href(route: Route): string {
  switch (route.name) {
    case "login":
      return "#/login";
    case "home":
      return "#/";
    case "profiles":
      return "#/profiles";
    case "settings":
      return "#/settings";
    case "batch":
      return `#/batches/${route.id}`;
    case "review":
      return `#/batches/${route.id}/review`;
    case "reports":
      return `#/batches/${route.id}/reports`;
    case "sequence":
    case "metadata":
      return `#/batches/${route.id}/${route.name}${route.doc ? `/${route.doc}` : ""}`;
  }
}

export function navigate(route: Route): void {
  window.location.hash = href(route);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
