import { useNavigate } from "react-router";

interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface Props {
  items: BreadcrumbItem[];
}

export default function Breadcrumb({ items }: Props) {
  const navigate = useNavigate();

  return (
    <nav className="flex items-center gap-1.5 text-[12px] text-[#94A3B8]">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            )}
            {isLast || !item.to ? (
              <span className={isLast ? "text-[#64748B] font-medium" : ""}>{item.label}</span>
            ) : (
              <button
                onClick={() => navigate(item.to!)}
                className="hover:text-[#2563EB] transition-colors"
              >
                {item.label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
