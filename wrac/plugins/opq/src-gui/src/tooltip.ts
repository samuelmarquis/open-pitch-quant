/**
 * One shared tooltip: a mono-type card that follows hover targets.
 * Content is plain text (mechanism copy lives in controls.ts).
 */

let node: HTMLDivElement | undefined;
let showTimer = 0;

function ensure(): HTMLDivElement {
  if (!node) {
    node = document.createElement("div");
    node.id = "tooltip";
    node.hidden = true;
    document.body.appendChild(node);
  }
  return node;
}

export function attachTooltip(target: HTMLElement, text: string): void {
  target.addEventListener("pointerenter", () => {
    window.clearTimeout(showTimer);
    showTimer = window.setTimeout(() => {
      const tip = ensure();
      tip.textContent = text;
      tip.hidden = false;
      const rect = target.getBoundingClientRect();
      tip.style.left = "0px";
      tip.style.top = "0px";
      const tw = tip.offsetWidth;
      const th = tip.offsetHeight;
      let x = rect.left + rect.width / 2 - tw / 2;
      x = Math.min(Math.max(4, x), window.innerWidth - tw - 4);
      let y = rect.top - th - 8;
      if (y < 4) y = rect.bottom + 8;
      tip.style.left = `${Math.round(x)}px`;
      tip.style.top = `${Math.round(y)}px`;
    }, 350);
  });
  target.addEventListener("pointerleave", () => {
    window.clearTimeout(showTimer);
    if (node) node.hidden = true;
  });
  target.addEventListener("pointerdown", () => {
    window.clearTimeout(showTimer);
    if (node) node.hidden = true;
  });
}
