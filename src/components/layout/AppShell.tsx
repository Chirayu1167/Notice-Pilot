import { useState, type ReactNode } from "react";
import { TopNav } from "../navigation/TopNav";
import { UploadModal } from "../upload/UploadModal";
import { UploadContextProvider } from "../upload/uploadContext";

export function AppShell({ children }: { children: ReactNode }) {
  const [uploadOpen, setUploadOpen] = useState(false);

  return (
    <UploadContextProvider value={{ openUpload: () => setUploadOpen(true) }}>
      <TopNav onUpload={() => setUploadOpen(true)} />
      <main>{children}</main>
      <footer>
        <span>NoticePilot · GST notice review workspace</span>
        <span>Rule pack: not connected · Review required before submission</span>
      </footer>
      {uploadOpen ? <UploadModal onClose={() => setUploadOpen(false)} /> : null}
    </UploadContextProvider>
  );
}
