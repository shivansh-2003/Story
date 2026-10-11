import type { TextSelection } from "./rewritingApi";

export function wholeParagraph(text: string): TextSelection {
  return { start: 0, end: Array.from(text).length, original_text: text };
}

/** Browser offsets count UTF-16 units; the API counts Unicode code points. */
export function fromUtf16(text: string, start: number, end: number): TextSelection | null {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > text.length || end <= start) return null;
  const splitSurrogate = (offset: number) => offset > 0 && offset < text.length &&
    /[\uD800-\uDBFF]/.test(text[offset - 1]) && /[\uDC00-\uDFFF]/.test(text[offset]);
  if (splitSurrogate(start) || splitSurrogate(end)) return null;
  return { start: Array.from(text.slice(0, start)).length, end: Array.from(text.slice(0, end)).length, original_text: text.slice(start, end) };
}

export function paragraphSelection(element: HTMLElement, text: string): TextSelection | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1) return null;
  const range = selection.getRangeAt(0);
  if (!element.contains(range.startContainer) || !element.contains(range.endContainer)) return null;
  const prefix = range.cloneRange();
  prefix.selectNodeContents(element);
  prefix.setEnd(range.startContainer, range.startOffset);
  const start = prefix.toString().length;
  const result = fromUtf16(text, start, start + range.toString().length);
  return result?.original_text === range.toString() ? result : null;
}
