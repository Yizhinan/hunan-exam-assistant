import { useRef, useState, type DragEvent } from "react";
import { UploadCloud, FileSpreadsheet, X, AlertCircle } from "lucide-react";

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  disabled?: boolean;
  hint?: string;
}

export default function FileUploadZone({
  onFileSelect,
  accept = ".xlsx,.xlsm",
  disabled = false,
  hint = "拖拽 .xlsx 文件到此处，或点击选择",
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  const validateAndSet = (file: File) => {
    setError("");
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["xlsx", "xlsm"].includes(ext)) {
      setError(`仅支持 .xlsx 格式，收到: .${ext}`);
      return;
    }
    const maxSize = 20 * 1024 * 1024; // 20MB
    if (file.size > maxSize) {
      setError(`文件过大（最大 20MB），当前: ${(file.size / 1024 / 1024).toFixed(1)}MB`);
      return;
    }
    setSelectedFile(file);
    onFileSelect(file);
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) validateAndSet(file);
  };

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleInputChange = () => {
    const file = inputRef.current?.files?.[0];
    if (file) validateAndSet(file);
  };

  const handleRemove = () => {
    setSelectedFile(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div>
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
          disabled
            ? "bg-warm-50 border-warm-200 cursor-not-allowed opacity-60"
            : dragOver
            ? "border-brand-400 bg-brand-50/50"
            : selectedFile
            ? "border-emerald-300 bg-emerald-50/30"
            : "border-warm-200 bg-warm-50/30 hover:border-brand-300 hover:bg-brand-50/20"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />

        {selectedFile ? (
          <div className="flex flex-col items-center gap-2">
            <FileSpreadsheet className="h-10 w-10 text-emerald-500" />
            <span className="text-sm font-medium text-warm-800">{selectedFile.name}</span>
            <span className="text-xs text-warm-400">
              {(selectedFile.size / 1024).toFixed(0)} KB
            </span>
            {!disabled && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove();
                }}
                className="mt-1 inline-flex items-center gap-1 text-xs text-warm-400 hover:text-red-500 transition-colors"
              >
                <X className="h-3 w-3" /> 移除
              </button>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <UploadCloud className={`h-10 w-10 ${dragOver ? "text-brand-500" : "text-warm-300"}`} />
            <div>
              <p className="text-sm text-warm-600">{hint}</p>
              <p className="text-xs text-warm-400 mt-1">支持 .xlsx 格式，最大 20MB</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-center gap-2 text-xs text-red-600">
          <AlertCircle className="h-3 w-3" />
          {error}
        </div>
      )}
    </div>
  );
}
