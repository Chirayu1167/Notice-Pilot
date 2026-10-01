import { createContext, useContext } from "react";

type UploadContextValue = {
  openUpload: () => void;
};

const UploadContext = createContext<UploadContextValue>({ openUpload: () => {} });

export function useUploadModal() {
  return useContext(UploadContext);
}

export const UploadContextProvider = UploadContext.Provider;
