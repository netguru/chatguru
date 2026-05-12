/// <reference types="vite/client" />

// biome-ignore lint/correctness/noUnusedVariables: standard Vite env augmentation
interface ImportMetaEnv {
  /** Set to "false" to hide the document-upload button. Defaults to enabled. */
  readonly VITE_DOCUMENT_UPLOAD_ENABLED?: string;
}
