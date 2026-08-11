import { Download } from "lucide-react";

export function PdfDownloadButton({ label = "Download PDF" }: { label?: string }) {
  return (
    <button className="button button-primary">
      <Download size={14} />
      {label}
    </button>
  );
}
