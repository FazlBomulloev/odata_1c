import { cn } from '@/lib/utils';

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-surface-2',
        className,
      )}
      {...props}
    />
  );
}

export function TableSkeleton({ rows = 10 }: { rows?: number }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden bg-surface">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={cn(
            'flex items-center gap-4 px-4 py-3',
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
      className="h-0.5 w-full bg-border overflow-hidden rounded-sm"
    >
      <div
        className="h-full w-1/3 bg-accent rounded-sm"
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
