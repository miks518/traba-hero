import React, { useEffect, useState } from 'react';

const EXIT_DURATION_MS = 100;

export interface FadeSlideProps {
  show: boolean;
  className?: string;
  children: React.ReactNode;
}

export function FadeSlide({ show, className = '', children }: FadeSlideProps) {
  const [isMounted, setIsMounted] = useState(show);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    if (show) {
      setIsMounted(true);
      setIsExiting(false);
      return;
    }

    if (!isMounted) return;

    setIsExiting(true);
    const timer = setTimeout(() => setIsMounted(false), EXIT_DURATION_MS);
    return () => clearTimeout(timer);
  }, [isMounted, show]);

  if (!isMounted) return null;

  return (
    <div
      aria-hidden={!show}
      className={`${className} ${
        isExiting
          ? 'opacity-0 -translate-y-1 pointer-events-none transition-[opacity,transform] duration-100 ease-in motion-reduce:transition-none'
          : 'opacity-100 translate-y-0 pointer-events-auto animate-fade-slide-in motion-reduce:animate-none'
      }`}
    >
      {children}
    </div>
  );
}
