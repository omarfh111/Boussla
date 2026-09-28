import { useEffect, useState } from "react";
import { BousslaMark } from "./BousslaMark";

const SEEN_KEY = "boussla.boot.v1";
const FULL_MS = 1000;
const REDUCED_MS = 80;
const FADE_MS = 180;

const reducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** True only for the first cold load of this browser session. */
export function shouldShowBoot(): boolean {
  try {
    return !reducedMotion() && window.sessionStorage.getItem(SEEN_KEY) !== "1";
  } catch {
    return false;
  }
}

/** First-load identity cue, bounded independently from network work. */
export function BootSplash({ onDone }: { onDone: () => void }) {
  const reduced = reducedMotion();
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    try {
      window.sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* storage unavailable: the splash simply shows again next load */
    }
    const total = reduced ? REDUCED_MS : FULL_MS;
    const fade = window.setTimeout(
      () => setLeaving(true),
      Math.max(0, total - FADE_MS),
    );
    const done = window.setTimeout(onDone, total);
    return () => {
      window.clearTimeout(fade);
      window.clearTimeout(done);
    };
  }, [onDone, reduced]);
  return (
    <div
      className={`boot-splash ${reduced ? "reduced" : ""} ${leaving ? "leaving" : ""}`}
      role="status"
      aria-live="polite"
      aria-label="Chargement de BOUSSLA"
    >
      <div className="boot-center">
        <BousslaMark size={104} animated={!reduced} title="BOUSSLA" />
        <div className="boot-wordmark">BOUSSLA</div>
        <p className="boot-subtitle">Espace de revue</p>
      </div>
      <button className="boot-skip" type="button" onClick={onDone}>
        Passer l’introduction
      </button>
    </div>
  );
}
