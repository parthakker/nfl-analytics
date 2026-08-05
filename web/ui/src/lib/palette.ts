/** The palette lives in Shell, but anything can ask for it.
 *
 *  A custom event rather than another provider: the palette has exactly one
 *  instance and one verb, so a context would be more wiring than the problem
 *  is worth, and this keeps callers from importing Shell.
 */
export const PALETTE_OPEN = "palette:open";

export function openPalette() {
  window.dispatchEvent(new CustomEvent(PALETTE_OPEN));
}
