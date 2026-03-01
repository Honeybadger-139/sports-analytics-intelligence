interface SportsMarkProps {
  size?: number
  className?: string
}

export default function SportsMark({ size = 40, className = '' }: SportsMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 44 44"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Sports Analytics Intelligence"
    >
      {/* ── Outer ring — tennis racket frame ── */}
      <circle cx="22" cy="22" r="19.5" stroke="#FF5C1A" strokeWidth="1.2" opacity="0.45" />

      {/* ── Tennis racket strings — 4 faint grid lines ── */}
      <line x1="22" y1="2.5" x2="22" y2="41.5" stroke="#FF5C1A" strokeWidth="0.4" opacity="0.18" />
      <line x1="2.5" y1="22" x2="41.5" y2="22" stroke="#FF5C1A" strokeWidth="0.4" opacity="0.18" />
      <line x1="7.5" y1="7.5"  x2="36.5" y2="36.5" stroke="#FF5C1A" strokeWidth="0.35" opacity="0.1" />
      <line x1="36.5" y1="7.5" x2="7.5"  y2="36.5" stroke="#FF5C1A" strokeWidth="0.35" opacity="0.1" />

      {/* ── Football — tilted oval, behind basketball ── */}
      <g transform="rotate(-20 22 22)">
        <ellipse cx="22" cy="22" rx="6" ry="9.5" stroke="#06C5F8" strokeWidth="1.1" opacity="0.55" />
        {/* Laces */}
        <line x1="22" y1="17" x2="22" y2="27" stroke="#06C5F8" strokeWidth="0.7" opacity="0.4" />
        <line x1="20" y1="21" x2="24" y2="21" stroke="#06C5F8" strokeWidth="0.6" opacity="0.35" />
        <line x1="20" y1="22.8" x2="24" y2="22.8" stroke="#06C5F8" strokeWidth="0.6" opacity="0.35" />
      </g>

      {/* ── Basketball — center ── */}
      <circle cx="22" cy="22" r="8.5" stroke="#FFFFFF" strokeWidth="1.4" opacity="0.9" />
      {/* Seam arcs */}
      <path d="M13.5 22 Q22 17.5 30.5 22" stroke="#FFFFFF" strokeWidth="0.85" fill="none" opacity="0.75" />
      <path d="M13.5 22 Q22 26.5 30.5 22" stroke="#FFFFFF" strokeWidth="0.85" fill="none" opacity="0.75" />
      <line x1="22" y1="13.5" x2="22" y2="30.5" stroke="#FFFFFF" strokeWidth="0.85" opacity="0.75" />

      {/* ── Hockey stick LEFT — shaft from bottom-left up toward centre ── */}
      {/* Shaft */}
      <line x1="5"  y1="41" x2="15.5" y2="17.5"
            stroke="#FF5C1A" strokeWidth="2.2" strokeLinecap="round" />
      {/* Blade — short curve at the bottom */}
      <path d="M5 41 Q3.5 43 9 43.5"
            stroke="#FF5C1A" strokeWidth="2" strokeLinecap="round" fill="none" />

      {/* ── Hockey stick RIGHT — mirror ── */}
      <line x1="39" y1="41" x2="28.5" y2="17.5"
            stroke="#FF5C1A" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M39 41 Q40.5 43 35 43.5"
            stroke="#FF5C1A" strokeWidth="2" strokeLinecap="round" fill="none" />
    </svg>
  )
}
