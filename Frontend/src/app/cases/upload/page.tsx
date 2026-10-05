import { redirect } from "next/navigation";

// This route used to render a fully static mock (FileDropzone.tsx —
// hardcoded files, no real <input>, no working buttons), then later just
// redirected to a standalone /upload route (also removed — it defaulted to
// a hardcoded demo case rather than a real one). The only sanctioned upload
// path now is a case's own workspace (CaseWorkspacePage.tsx, /cases/[id]),
// which requires and passes a real caseId. Redirect old bookmarks to the
// case list so they land somewhere real instead of a dead route.
export default function UploadRoute() {
  redirect("/cases");
}
