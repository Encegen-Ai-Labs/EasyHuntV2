"use client";

import React from "react";
import { Plus, Trash2 } from "lucide-react";
import type { DraftBlock, DraftField, DraftLoop, DraftSection, ReportDraft } from "@/services/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const TEXTAREA_CLASS =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm leading-relaxed outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

function rowsFor(text: string): number {
  const lines = text.split("\n").reduce((n, line) => n + Math.max(1, Math.ceil(line.length / 90)), 0);
  return Math.min(14, Math.max(2, lines));
}

function GrowingTextarea({
  value,
  onChange,
  className,
  placeholder,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <textarea
      aria-label={ariaLabel}
      value={value}
      placeholder={placeholder}
      rows={rowsFor(value)}
      onChange={(e) => onChange(e.target.value)}
      className={cn(TEXTAREA_CLASS, className)}
    />
  );
}

/** A section the lawyer can fold away. The summary carries a short status so a closed section still says something. */
function Fold({
  title,
  status,
  defaultOpen,
  children,
}: {
  title: React.ReactNode;
  status?: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-heading text-lg font-medium">{title}</span>
        <span className="flex items-center gap-3 text-xs text-muted-foreground">
          {status}
          <span aria-hidden className="transition-transform group-open:rotate-90">›</span>
        </span>
      </summary>
      <div className="border-t border-border px-4 py-4">{children}</div>
    </details>
  );
}

/** A table whose cells can be edited and whose rows can be added or removed. */
function TableEditor({
  columns,
  rows,
  onChange,
}: {
  columns: string[];
  rows: string[][];
  onChange: (rows: string[][]) => void;
}) {
  function setCell(r: number, c: number, value: string) {
    onChange(rows.map((row, i) => (i === r ? row.map((cell, j) => (j === c ? value : cell)) : row)));
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((column, i) => (
                <th key={i} className="border-b border-border px-2 py-1.5 text-left font-semibold">{column}</th>
              ))}
              <th className="w-9 border-b border-border" aria-label="Remove row" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className="border-t border-border">
                {columns.map((column, c) => (
                  <td key={c} className="p-1 align-top">
                    <GrowingTextarea
                      ariaLabel={`${column}, row ${r + 1}`}
                      value={row[c] ?? ""}
                      onChange={(value) => setCell(r, c, value)}
                      className="min-w-[7rem] px-1.5 py-1"
                    />
                  </td>
                ))}
                <td className="p-1 align-top">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    title="Remove row"
                    aria-label={`Remove row ${r + 1}`}
                    onClick={() => onChange(rows.filter((_, i) => i !== r))}
                  >
                    <Trash2 size={13} />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-fit"
        onClick={() => onChange([...rows, columns.map(() => "")])}
      >
        <Plus size={13} data-icon="inline-start" />
        Add row
      </Button>
    </div>
  );
}

function BlockEditor({ block, onChange }: { block: DraftBlock; onChange: (block: DraftBlock) => void }) {
  if (block.type === "table") {
    return <TableEditor columns={block.columns} rows={block.rows} onChange={(rows) => onChange({ ...block, rows })} />;
  }
  return <GrowingTextarea ariaLabel="Paragraph" value={block.text} onChange={(text) => onChange({ ...block, text })} />;
}

/** Title search report: ordered sections of paragraphs and tables. */
export function TitleSearchEditor({
  draft,
  onChange,
}: {
  draft: ReportDraft;
  onChange: (draft: ReportDraft) => void;
}) {
  function setBlock(section: DraftSection, blockIndex: number, block: DraftBlock) {
    onChange({
      ...draft,
      sections: draft.sections.map((s) =>
        s.id === section.id ? { ...s, blocks: s.blocks.map((b, i) => (i === blockIndex ? block : b)) } : s
      ),
    });
  }
  function setHeading(section: DraftSection, heading: string) {
    onChange({ ...draft, sections: draft.sections.map((s) => (s.id === section.id ? { ...s, heading } : s)) });
  }

  return (
    <div className="flex flex-col gap-6">
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Report title</span>
        <Input value={draft.title} onChange={(e) => onChange({ ...draft, title: e.target.value })} className="h-9 text-base font-semibold" />
      </label>
      {draft.sections.map((section) => (
        <Fold
          key={section.id}
          title={section.heading}
          defaultOpen={!["documents", "extracts", "signature"].includes(section.id)}
        >
          <Input
            aria-label="Section heading"
            value={section.heading}
            onChange={(e) => setHeading(section, e.target.value)}
            className="mb-3 h-9 text-sm font-medium"
          />
          <div className="flex flex-col gap-3">
            {section.blocks.map((block, index) => (
              <BlockEditor key={index} block={block} onChange={(next) => setBlock(section, index, next)} />
            ))}
          </div>
        </Fold>
      ))}
    </div>
  );
}

function FieldInput({ field, onChange }: { field: DraftField; onChange: (value: string) => void }) {
  const empty = field.required && !field.value.trim();
  const common = cn(empty && "border-amber-500/70");
  if (field.type === "choice" && field.options.length > 0) {
    return (
      <select
        aria-label={field.label}
        value={field.value}
        onChange={(e) => onChange(e.target.value)}
        className={cn("h-9 w-full rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30", common)}
      >
        <option value="">Choose…</option>
        {field.options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    );
  }
  if (field.source === "drafted" || field.value.length > 80) {
    return <GrowingTextarea ariaLabel={field.label} value={field.value} onChange={onChange} className={common} />;
  }
  return (
    <Input
      aria-label={field.label}
      value={field.value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.type === "date" ? "DD/MM/YYYY" : undefined}
      inputMode={field.type === "number" ? "decimal" : undefined}
      className={cn("h-9", common)}
    />
  );
}

function LoopEditor({ loop, onChange }: { loop: DraftLoop; onChange: (loop: DraftLoop) => void }) {
  const nested = Object.keys(loop.nested_lists);
  const columns = [...loop.item_fields, ...nested];
  const asText = (value: string | string[] | undefined) => (Array.isArray(value) ? value.join("\n") : value ?? "");

  return (
    <TableEditor
      columns={columns.map((c) => c.replace(/_/g, " "))}
      rows={loop.rows.map((row) => columns.map((c) => asText(row[c])))}
      onChange={(rows) =>
        onChange({
          ...loop,
          rows: rows.map((cells) => Object.fromEntries(columns.map((c, i) => [c, cells[i] ?? ""]))),
        })
      }
    />
  );
}

/** A bank's template: its fields grouped by where the answer comes from, then its repeating tables. */
export function BankFormEditor({
  draft,
  onChange,
}: {
  draft: ReportDraft;
  onChange: (draft: ReportDraft) => void;
}) {
  const groups = [...new Set(draft.fields.map((f) => f.group))];
  const setValue = (name: string, value: string) =>
    onChange({ ...draft, fields: draft.fields.map((f) => (f.name === name ? { ...f, value } : f)) });

  return (
    <div className="flex flex-col gap-6">
      {groups.map((group, groupIndex) => {
        const inGroup = draft.fields.filter((f) => f.group === group);
        const filled = inGroup.filter((f) => f.value.trim()).length;
        const hasSuggested = inGroup.some((f) => f.suggested && f.value);
        return (
        <Fold
          key={group}
          title={group}
          status={`${filled} of ${inGroup.length} filled`}
          defaultOpen={hasSuggested || groupIndex === 0}
        >
          <div className="grid gap-4 md:grid-cols-2">
            {draft.fields
              .filter((f) => f.group === group)
              .map((field) => (
                <div key={field.name} className={cn("flex flex-col gap-1.5", (field.source === "drafted" || field.value.length > 80) && "md:col-span-2")}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{field.label}</span>
                    {field.suggested && field.value && (
                      <Badge variant="secondary" className="text-[10px] font-medium">
                        from documents · check
                      </Badge>
                    )}
                    {field.review_level === "must_confirm" && (
                      <Badge variant="outline" className="text-[10px] font-medium">
                        your call
                      </Badge>
                    )}
                  </div>
                  <FieldInput field={field} onChange={(value) => setValue(field.name, value)} />
                </div>
              ))}
          </div>
        </Fold>
        );
      })}

      {draft.loops.map((loop) => (
        <Fold
          key={loop.name}
          title={loop.label}
          status={loop.suggested ? "filled from documents" : `${loop.rows.length} row${loop.rows.length === 1 ? "" : "s"}`}
          defaultOpen={Boolean(loop.suggested)}
        >
          {Object.keys(loop.nested_lists).length > 0 && (
            <p className="mb-3 text-xs text-muted-foreground">One entry per line in list cells.</p>
          )}
          <LoopEditor
            loop={loop}
            onChange={(next) => onChange({ ...draft, loops: draft.loops.map((l) => (l.name === loop.name ? next : l)) })}
          />
        </Fold>
      ))}
    </div>
  );
}
