interface SportsMarkProps {
  size?: number
  className?: string
}

export default function SportsMark({ size = 40, className = '' }: SportsMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 60 60"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Sports Analytics Intelligence"
      style={{ overflow: 'visible' }}
    >
      <style>{`
        .sai-ring {
          animation: saiRing 22s linear infinite;
          transform-origin: 30px 30px;
        }
        .sai-float {
          animation: saiFloat 3.5s ease-in-out infinite;
        }
        .sai-bball {
          animation: saiBball 11s linear infinite;
          transform-box: fill-box;
          transform-origin: center;
        }
        .sai-glow {
          animation: saiGlow 2.8s ease-in-out infinite;
        }
        @keyframes saiRing {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes saiFloat {
          0%,  100% { transform: translateY(0px); }
          50%       { transform: translateY(-2.5px); }
        }
        @keyframes saiBball {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes saiGlow {
          0%,  100% { opacity: 0.18; }
          50%       { opacity: 0.50; }
        }
      `}</style>

      {/* ── Pulsing outer glow ── */}
      <circle
        className="sai-glow"
        cx="30" cy="30" r="28.5"
        stroke="#FF5C1A" strokeWidth="1.2"
      />

      {/* ── Rotating dashed ring ── */}
      <circle
        className="sai-ring"
        cx="30" cy="30" r="27.5"
        stroke="#FF5C1A" strokeWidth="1"
        strokeDasharray="4 3.5"
        opacity="0.45"
      />

      {/* ── All equipment floats together ── */}
      <g className="sai-float">

        {/* ─── Hockey stick + puck (back-left, gold) ─── */}
        {/* Shaft — diagonal from bottom-left up */}
        <line
          x1="5" y1="55" x2="24" y2="11"
          stroke="#FFB300" strokeWidth="2.7" strokeLinecap="round"
        />
        {/* Blade — short horizontal hook at the bottom */}
        <path
          d="M5 55 Q3 58 12 58.5"
          stroke="#FFB300" strokeWidth="2.3" strokeLinecap="round" fill="none"
        />
        {/* Puck — flat cylinder hint under blade */}
        <ellipse
          cx="7.5" cy="57.5" rx="4.5" ry="1.6"
          stroke="#FFB300" strokeWidth="0.9" opacity="0.45"
        />

        {/* ─── Baseball (top-right, light gray + red stitches) ─── */}
        <circle cx="46" cy="14" r="7.5" stroke="#A8B8C8" strokeWidth="1.3" />
        {/* Left stitch arc */}
        <path
          d="M41.5 10.5 Q44 14 41.5 17.5"
          stroke="#FF4C6A" strokeWidth="0.95" fill="none" strokeLinecap="round"
        />
        {/* Right stitch arc */}
        <path
          d="M50.5 10.5 Q48 14 50.5 17.5"
          stroke="#FF4C6A" strokeWidth="0.95" fill="none" strokeLinecap="round"
        />

        {/* ─── Soccer ball (left, behind basketball) ─── */}
        <circle cx="14" cy="33" r="10.5" stroke="#9AAABB" strokeWidth="1.3" />
        {/* Central pentagon */}
        <polygon
          points="14,26.5 17.5,28.8 16.3,32.8 11.7,32.8 10.5,28.8"
          fill="none" stroke="#6A7A8A" strokeWidth="0.8" opacity="0.85"
        />
        {/* Radiating lines from pentagon vertices */}
        <line x1="14"   y1="26.5" x2="14"   y2="22.5" stroke="#6A7A8A" strokeWidth="0.65" opacity="0.7" />
        <line x1="17.5" y1="28.8" x2="20.5" y2="27"   stroke="#6A7A8A" strokeWidth="0.65" opacity="0.7" />
        <line x1="16.3" y1="32.8" x2="18.8" y2="35"   stroke="#6A7A8A" strokeWidth="0.65" opacity="0.7" />
        <line x1="11.7" y1="32.8" x2="9.2"  y2="35"   stroke="#6A7A8A" strokeWidth="0.65" opacity="0.7" />
        <line x1="10.5" y1="28.8" x2="7.5"  y2="27"   stroke="#6A7A8A" strokeWidth="0.65" opacity="0.7" />

        {/* ─── American football (right-side, behind basketball) ─── */}
        <g transform="rotate(-22 44 35)">
          <ellipse
            cx="44" cy="35" rx="10" ry="6"
            stroke="#C47A2B" strokeWidth="1.4"
          />
          {/* Seam line */}
          <line x1="44" y1="30" x2="44" y2="40" stroke="#C47A2B" strokeWidth="0.8" />
          {/* Lace stitches */}
          <line x1="40" y1="33"   x2="48" y2="33"   stroke="#C47A2B" strokeWidth="0.75" />
          <line x1="40" y1="35"   x2="48" y2="35"   stroke="#C47A2B" strokeWidth="0.7"  />
          <line x1="40.5" y1="37" x2="47.5" y2="37" stroke="#C47A2B" strokeWidth="0.65" />
        </g>

        {/* ─── Tennis ball (bottom-right, cyan accent) ─── */}
        <circle cx="48" cy="48" r="6.5" stroke="#06C5F8" strokeWidth="1.15" opacity="0.75" />
        {/* Characteristic curved seams */}
        <path
          d="M42.5 44.5 Q48 48 42.5 51.5"
          stroke="#06C5F8" strokeWidth="0.9" fill="none" opacity="0.65" strokeLinecap="round"
        />
        <path
          d="M53.5 44.5 Q48 48 53.5 51.5"
          stroke="#06C5F8" strokeWidth="0.9" fill="none" opacity="0.65" strokeLinecap="round"
        />

        {/* ─── Basketball (center foreground — the HERO) ─── */}
        {/* Outer circle is stable; seams spin independently */}
        <circle cx="29" cy="27" r="13.5" stroke="#FF5C1A" strokeWidth="1.9" />
        <g className="sai-bball">
          {/* Top seam arc */}
          <path
            d="M15.5 27 Q29 20 42.5 27"
            stroke="#FF5C1A" strokeWidth="1.2" fill="none"
          />
          {/* Bottom seam arc */}
          <path
            d="M15.5 27 Q29 34 42.5 27"
            stroke="#FF5C1A" strokeWidth="1.2" fill="none"
          />
          {/* Vertical seam */}
          <line x1="29" y1="13.5" x2="29" y2="40.5" stroke="#FF5C1A" strokeWidth="1.2" />
        </g>

      </g>
    </svg>
  )
}
