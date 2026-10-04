import { ArrowLeft, ArrowRight } from "lucide-react";

export const ADMIN_PAGE_SIZE = 5;

type Props = {
  label: string;
  offset: number;
  hasNext: boolean;
  disabled?: boolean;
  onChange: (offset: number) => void;
};

export function ListPagination({ label, offset, hasNext, disabled = false, onChange }: Props) {
  return <nav className="admin-pagination" aria-label={`${label} pagination`}>
    <button type="button" className="icon-button" title={`Previous ${label}`} aria-label={`Previous ${label}`} disabled={offset === 0 || disabled} onClick={() => onChange(Math.max(0, offset - ADMIN_PAGE_SIZE))}><ArrowLeft size={18} /></button>
    <span aria-live="polite">Page {Math.floor(offset / ADMIN_PAGE_SIZE) + 1}</span>
    <button type="button" className="icon-button" title={`Next ${label}`} aria-label={`Next ${label}`} disabled={!hasNext || disabled} onClick={() => onChange(offset + ADMIN_PAGE_SIZE)}><ArrowRight size={18} /></button>
  </nav>;
}