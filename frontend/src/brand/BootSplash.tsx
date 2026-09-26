import { useEffect, useState } from "react";
import { BousslaMark } from "./BousslaMark";

const SEEN_KEY = "boussla.boot.v1";
const FULL_MS = 2900;
const REDUCED_MS = 250;

const reducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** True only for the first cold load of this browser session. */
export function shouldShowBoot(): boolean {
  try {
    return window.sessionStorage.getItem(SEEN_KEY) !== "1";
  } catch {
    return false;
  }
}

/** ~3 s CSS/SVG boot sequence, shown once per session and time-bounded: it never waits
 * on the network, so loading continues to the skeleton and errors stay visible.
 * The status lines are visual labels only; they do not report provider calls. */
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
      Math.max(0, total - 300),
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
      onClick={onDone}
    >
      <div className="boot-center">
        <BousslaMark size={132} animated={!reduced} title="BOUSSLA" />
        <div className="boot-wordmark">BOUSSLA</div>
        <ul className="boot-lines" aria-hidden="true">
          <li>Structuration des faits</li>
          <li>Contrôles documentaires</li>
          <li>Préparation de l'espace de revue</li>
        </ul>
      </div>
    </div>
  );
}
