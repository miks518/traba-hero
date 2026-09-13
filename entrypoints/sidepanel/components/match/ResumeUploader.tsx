import React, { useRef, useCallback } from 'react';
import { Icon } from '../common/Icon';

export interface ResumeUploaderProps {
  onFileSelected: (base64: string, fileType: string, fileName: string) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = '.pdf,.png,.jpg,.jpeg,.doc,.docx,.txt';

export function ResumeUploader({ onFileSelected, disabled }: ResumeUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(',') ? result.split(',')[1] : result;
      onFileSelected(base64, ext, file.name);
    };
    reader.readAsDataURL(file);
  }, [onFileSelected]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
    e.target.value = '';
  }, [handleFile]);

  return (
    <div
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
      onClick={() => inputRef.current?.click()}
      className="border-2 border-dashed border-outline-variant/30 rounded-xl p-6 flex flex-col items-center gap-3 cursor-pointer hover:border-secondary/50 transition-colors bg-surface-container-low/50"
    >
      <Icon name="upload_file" className="text-3xl text-on-surface-variant" />
      <span className="text-body-md text-on-surface-variant text-center">
        Upload your resume
      </span>
      <span className="text-label-sm text-on-surface-variant/60 text-center">
        PDF, DOC, TXT, or Image
      </span>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={handleChange}
        disabled={disabled}
        className="hidden"
      />
    </div>
  );
}

export default ResumeUploader;
