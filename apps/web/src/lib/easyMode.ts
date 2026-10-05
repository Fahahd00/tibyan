/** Easy mode (larger text, a big voice button, answers read aloud): a per-viewer choice kept in this browser. */
export const EASY_MODE_KEY = "tibyan-easy";
export const EASY_MODE_EVENT = "tibyan:easy";

/** Runs before the page paints, so a returning viewer never sees the small text first. */
export const EASY_MODE_SCRIPT = `try{if(localStorage.getItem("${EASY_MODE_KEY}")==="1")document.documentElement.dataset.easy="on"}catch(e){}`;
