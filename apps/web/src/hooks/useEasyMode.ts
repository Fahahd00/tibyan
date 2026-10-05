"use client";

import { useCallback, useSyncExternalStore } from "react";
import { EASY_MODE_EVENT, EASY_MODE_KEY } from "@/lib/easyMode";

function subscribe(onChange: () => void) {
  window.addEventListener(EASY_MODE_EVENT, onChange);
  return () => window.removeEventListener(EASY_MODE_EVENT, onChange);
}

const isOn = () => document.documentElement.dataset.easy === "on";

export function useEasyMode() {
  const on = useSyncExternalStore(subscribe, isOn, () => false);
  const toggle = useCallback(() => {
    const next = !isOn();
    if (next) document.documentElement.dataset.easy = "on";
    else delete document.documentElement.dataset.easy;
    try {
      localStorage.setItem(EASY_MODE_KEY, next ? "1" : "0");
    } catch {
      // storage unavailable: the choice lasts for this page only
    }
    window.dispatchEvent(new Event(EASY_MODE_EVENT));
  }, []);
  return { on, toggle };
}
