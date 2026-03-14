interface SkeletonCardProps {
  height?: number
}

export default function SkeletonCard({ height = 180 }: SkeletonCardProps) {
  return (
    <div
      style={{
        height,
        borderRadius: 'var(--r-md)',
        border: '1px solid var(--border)',
        background: 'linear-gradient(90deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.02) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s ease-in-out infinite',
      }}
    />
  )
}
