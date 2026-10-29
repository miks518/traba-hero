import React from 'react';
import { Icon } from '../common/Icon';

export interface ConsentModalProps {
  open: boolean;
  /** The file the reader picked, named in the notice so they know what they are agreeing to. */
  fileName: string;
  onAccept: () => void;
  onDecline: () => void;
}

/**
 * The privacy notice shown before the first resume upload.
 *
 * Consent under the Data Privacy Act of 2012 (RA 10173) must be informed,
 * specific and voluntary, so the notice names the controller, the data, the
 * recipients, the purpose, the retention, and the way out — each in its own
 * line, because a paragraph that does all five at once informs nobody.
 *
 * Every sentence is enforced somewhere else and the notice is not allowed to
 * outrun it: "no database copy" is held by the backend holding nothing
 * (`docs/decisions/security-boundaries.md`) and by
 * `backend/tests/test_resume_content_not_logged.py` keeping derived content out
 * of the logs. If either changes, this text changes first.
 */
export function ConsentModal({ open, fileName, onAccept, onDecline }: ConsentModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-80 max-h-[90vh] overflow-y-auto rounded-xl bg-surface-container-high border border-outline-variant/30 shadow-xl p-5 flex flex-col gap-3">
        <h3 className="text-headline-xs font-headline text-on-surface">
          Before we process your resume
        </h3>

        <p className="text-body-sm text-on-surface-variant leading-relaxed">
          You chose <span className="font-bold text-on-surface">{fileName}</span>. Nothing has
          been sent yet — uploading is your choice.
        </p>

        <div className="flex flex-col gap-2 text-body-sm text-on-surface-variant leading-relaxed">
          <p>
            <span className="font-bold text-on-surface">What we read.</span> The whole document:
            your name, contact details, address, education and work history — everything the
            file contains.
          </p>
          <p>
            <span className="font-bold text-on-surface">Where it goes.</span> To the Trabahero
            server, which extracts the text and sends it to a third-party AI provider to
            identify your skills and experience for job matching.
          </p>
          <p>
            <span className="font-bold text-on-surface">What is kept.</span> Nothing on a
            server. The file and its text are processed in memory and no database copy is
            written. The extracted profile stays in this browser while the panel is open, and
            you can delete it any time.
          </p>
          <p>
            <span className="font-bold text-on-surface">Your rights.</span> Consent is
            voluntary. You can decline and enter your skills manually instead. Under the Data
            Privacy Act of 2012 (RA 10173) you may withdraw consent at any time and may lodge
            a complaint with the National Privacy Commission (NPC).
          </p>
        </div>

        <div className="flex gap-3 justify-end pt-1">
          <button
            onClick={onDecline}
            className="px-4 py-2 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:text-secondary hover:border-secondary/50 transition-colors text-label-md"
          >
            Don't upload
          </button>
          <button
            onClick={onAccept}
            className="px-4 py-2 rounded-lg text-label-md transition-colors bg-secondary text-on-secondary font-medium hover:bg-secondary/90 flex items-center gap-1.5"
          >
            <Icon name="upload_file" className="text-sm" />
            Agree & upload
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConsentModal;
