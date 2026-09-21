import { redirect } from "next/navigation";

// This route used to render a fully static mock (FileDropzone.tsx — hardcoded
// files, no real <input>, no working buttons). The real, functional batch
// upload (BatchUploadPanel) lives at /upload, so this now just redirects there
// instead of being a dead end for anyone with the old link bookmarked.
export default function UploadRoute() {
  redirect("/upload");
}
