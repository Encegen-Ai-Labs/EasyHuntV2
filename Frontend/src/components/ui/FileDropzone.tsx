"use client";

import { useState } from "react";
import { FileText, Image, X, UploadCloud, FileArchive } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export type UploadItem = {
  id: string;
  name: string;
  type: string;
  size: number;
  progress: number;
  status: "Uploading..." | "Processing OCR..." | "Ready";
};

export function FileDropzone() {
  const [files, setFiles] = useState<UploadItem[]>([
    { id: "1", name: "deed-2026.pdf", type: "PDF", size: 2418920, progress: 96, status: "Ready" },
    { id: "2", name: "valuation.png", type: "PNG", size: 1627024, progress: 62, status: "Processing OCR..." },
  ]);

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Case Documents</p>
            <CardTitle className="mt-1 text-2xl">Upload source files</CardTitle>
          </div>
          <Button variant="outline" size="sm">Add files</Button>
        </div>
      </CardHeader>
      
      <CardContent className="pt-6">
        <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center transition-colors hover:bg-muted/50">
          <span className="flex h-14 w-14 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
            <UploadCloud size={28} />
          </span>
          <div className="mt-4">
            <div className="text-base font-semibold">Drop files to begin intake</div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">PDF · PNG · JPG · TIFF</div>
          </div>
          <Button className="mt-5" size="sm">Browse documents</Button>
        </div>

        <div className="mt-6 flex flex-col gap-3">
          {files.map((file) => (
            <div key={file.id} className="flex items-start gap-4 rounded-xl border border-border bg-card p-4 shadow-sm">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                {file.type === "PDF" ? <FileText size={18} /> : file.type === "PNG" || file.type === "JPG" ? <Image size={18} /> : <FileArchive size={18} />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="truncate text-sm font-semibold">{file.name}</span>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground">
                    <X size={14} />
                  </Button>
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <Progress value={file.progress} className="h-1.5 flex-1" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{file.progress}%</span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{file.type} • {Math.round(file.size / 1024 / 1024 * 10) / 10} MB</span>
                  <Badge variant={file.status === "Ready" ? "default" : "secondary"} className="text-[10px]">
                    {file.status}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
