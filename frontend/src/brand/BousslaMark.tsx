import { useId } from "react";

/** Frozen BOUSSLA mark (inline SVG, no external asset). Gradient IDs are unique per
 * instance so several marks can share a page. ``animated`` adds part classes that
 * the boot splash animates with CSS only. */
export function BousslaMark({
  size = 32,
  animated = false,
  title = "BOUSSLA",
  className = "",
}: {
  size?: number;
  animated?: boolean;
  title?: string;
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const g = `boussla-g-${uid}`;
  const n = `boussla-n-${uid}`;
  const part = (name: string) => (animated ? `mark-${name}` : undefined);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 256 256"
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={`boussla-mark ${className}`}
    >
      <title>{title}</title>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#126BDB" />
          <stop offset="55%" stopColor="#16C6E3" />
          <stop offset="100%" stopColor="#20D6B5" />
        </linearGradient>
        <linearGradient id={n} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#0B2F63" />
          <stop offset="100%" stopColor="#16C6E3" />
        </linearGradient>
      </defs>
      <circle
        className={part("arc")}
        cx="128"
        cy="128"
        r="94"
        fill="none"
        stroke="#126BDB"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray="420 175"
        transform="rotate(-34 128 128)"
      />
      <circle
        className={part("inner")}
        cx="128"
        cy="128"
        r="72"
        fill="none"
        stroke="#16C6E3"
        strokeWidth="2"
        opacity=".26"
      />
      <path
        className={part("north")}
        d="M128 12 L151 78 L128 65 L105 78 Z"
        fill={`url(#${g})`}
      />
      <path
        className={part("south")}
        d="M128 244 L114 204 L128 212 L142 204 Z"
        fill="#0B2F63"
      />
      <path
        className={part("check")}
        d="M71 133 L113 175 L190 87"
        fill="none"
        stroke={`url(#${n})`}
        strokeWidth="23"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle className={part("node")} cx="113" cy="175" r="8" fill="#20D6B5" />
      <circle className={part("node")} cx="58" cy="96" r="5" fill="#126BDB" />
      <circle className={part("node")} cx="198" cy="163" r="5" fill="#16C6E3" />
    </svg>
  );
}
