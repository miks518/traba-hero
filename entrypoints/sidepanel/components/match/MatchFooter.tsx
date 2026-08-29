import React from 'react';
import { FOOTER_LINKS, FOOTER_COPYRIGHT } from '../../data/content';

export function MatchFooter() {
  return (
    <footer className="w-full border-t border-outline-variant/10 flex flex-col items-center gap-2 p-4 mt-auto">
      <div className="flex gap-4">
        {FOOTER_LINKS.map((link) => (
          <a
            key={link.id}
            href="#"
            className="font-label-sm text-on-surface-variant hover:text-secondary transition-colors"
          >
            {link.label}
          </a>
        ))}
      </div>
      <span className="font-label-sm text-on-surface-variant opacity-60">
        {FOOTER_COPYRIGHT}
      </span>
    </footer>
  );
}

export default MatchFooter;
