interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const label = status || "unknown";
  return <span className={`badge badge-${label}`}>{label}</span>;
}
