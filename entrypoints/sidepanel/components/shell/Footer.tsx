import React from 'react';
import { FOOTER_LINKS, FOOTER_COPYRIGHT } from '../../data/content';

export function Footer() {
  return (
    <footer className="bg-surface-container-lowest border-t border-outline-variant/10 w-full flex flex-col items-center gap-2 p-4 shrink-0">
      <div className="flex gap-4">
        {FOOTER_LINKS.map((link) => (
          <span
            key={link.id}
            className="text-label-sm text-on-surface-variant hover:text-secondary cursor-pointer transition-colors"
          >
            {link.label}
          </span>
        ))}
      </div>
      <span className="text-label-sm text-on-surface-variant opacity-60">
        {FOOTER_COPYRIGHT}
      </span>
    </footer>
  );
}

export default Footer;
