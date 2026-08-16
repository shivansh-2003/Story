import { createTimeline, utils } from "animejs";

// The one action that changes the database gets the one long animation in
// the app: the blue drains out of the paragraph left to right, it settles
// 2px onto the sheet, and a tick appears in the margin. 620ms, once.
export function inkSettle(el: HTMLElement, onDone: () => void) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.dataset.state = "ink";
    onDone();
    return;
  }

  utils.set(el, { "--sweep": "0%" });

  createTimeline({ defaults: { ease: "cubicBezier(.16,.84,.3,1)" } })
    .add(el, { "--sweep": "100%", duration: 620 })
    .add(el, { y: [-2, 0], duration: 320 }, "-=380")
    .add(
      el.querySelector("[data-gutter-tick]")!,
      { opacity: [0, 1], scaleY: [0.4, 1], duration: 240 },
      "-=200",
    )
    .then(() => {
      el.dataset.state = "ink";
      onDone();
    });
}
