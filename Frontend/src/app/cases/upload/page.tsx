import { FileDropzone } from "@/components/ui/FileDropzone";

export default function UploadRoute() {
  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Case Intake</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Document Upload</h1>
        </div>
        <FileDropzone />
      </div>
    </div>
  );
}
