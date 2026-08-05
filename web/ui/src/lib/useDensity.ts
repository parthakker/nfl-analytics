import { useEffect, useState } from "react";

export type Density = "compact" | "default" | "comfortable";
const KEY = "ui.density";

/** Row density is user state, not a design decision — power users scanning
 *  300 rows want compact; 28px is the floor because in-row targets must
 *  clear 24px (WCAG 2.2). Applied as data-density on <html>; the actual
 *  --row-h/--cell-px values live in styles/base.css. */
export function useDensity(): [Density, (d: Density) => void] {
  const [density, set] = useState<Density>(
    () => (localStorage.getItem(KEY) as Density) || "default");

  useEffect(() => {
    document.documentElement.dataset.density = density;
    localStorage.setItem(KEY, density);
  }, [density]);

  return [density, set];
}
