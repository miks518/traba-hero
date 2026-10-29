import React from 'react';
import { FOOTER_LINKS, FOOTER_COPYRIGHT } from '../../data/content';

/**
 * The Privacy link's destination, read per render.
 *
 * There is no domain to host a policy on, so the destination lives in
 * `WXT_PRIVACY_POLICY_URL` and the repository carries no default. An unset or
 * empty value leaves the link exactly as it has always rendered — inert text,
 * which is what AC-05 asks the footer to display — and a pasted URL turns the
 * label into a real link with no other change. A control that vanished while
 * unconfigured would take the promise off the page; one that navigates nowhere
 * would keep lying with its pointer cursor.
 */
export function Footer() {
  const privacyUrl = import.meta.env.WXT_PRIVACY_POLICY_URL as string | undefined;

  return (
    <footer className="bg-surface-container-lowest border-t border-outline-variant/10 w-full flex flex-col items-center gap-2 p-4 shrink-0">
      <div className="flex gap-4">
        {FOOTER_LINKS.map((link) => {
          // The only footer label with a destination. The pointer cursor on
          // the remaining spans was removed with it: a cursor that promises a
          // click and delivers nothing is the same lie as a dead link.
          if (link.id === 'privacy' && privacyUrl) {
            return (
              <a
                key={link.id}
                href={privacyUrl}
                target="_blank"
                rel="noreferrer"
                className="text-label-sm text-on-surface-variant hover:text-secondary transition-colors"
              >
                {link.label}
              </a>
            );
          }
          return (
            <span
              key={link.id}
              className="text-label-sm text-on-surface-variant hover:text-secondary transition-colors"
            >
              {link.label}
            </span>
          );
        })}
      </div>
      <span className="text-label-sm text-on-surface-variant opacity-60">
        {FOOTER_COPYRIGHT}
      </span>
    </footer>
  );
}

export default Footer;
