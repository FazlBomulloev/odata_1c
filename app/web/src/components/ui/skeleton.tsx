import { cn } from '@/lib/utils';

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-sm bg-wash',
        className,
      )}
      {...props}
    />
  );
}

export function TableSkeleton({ rows = 10 }: { rows?: number }) {
  return (
    <div className="border border-rule rounded overflow-hidden bg-card">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={cn(
            'flex items-center gap-4 px-4 py-2.5',
            i > 0 && 'hairline-t',
          )}
        >
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

export function ProgressBar() {
  return (
    <div
      className="h-0.5 w-full bg-rule overflow-hidden rounded-sm"
    >
      <div
        className="h-full w-1/3 bg-[color:var(--accent)] rounded-sm"
        style={{
          animation: 'slide 1.2s ease-in-out infinite',
        }}
      />
      <style>{`
        @keyframes slide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
      `}</style>
    </div>
  );
}
