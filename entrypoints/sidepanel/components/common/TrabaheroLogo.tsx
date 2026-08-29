import React from 'react';

interface TrabaheroLogoProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  primaryColor?: string;
}

const TrabaheroLogo: React.FC<TrabaheroLogoProps> = ({
  size = 28,
  primaryColor = 'currentColor',
  ...props
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 430 448"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M215 32.5L50 100V210C50 310 120 400 215 425C310 400 380 310 380 210V100L215 32.5Z"
        stroke={primaryColor}
        strokeWidth="20"
        strokeLinejoin="round"
      />
      <rect
        x="120"
        y="170"
        width="190"
        height="130"
        rx="12"
        fill={primaryColor}
      />
      <path
        d="M175 170V145C175 136.716 181.716 130 190 130H240C248.284 130 255 136.716 255 145V170"
        stroke={primaryColor}
        strokeWidth="12"
      />
      <g>
        <circle
          cx="285"
          cy="320"
          r="60"
          fill="var(--color-surface-container-lowest)"
          stroke={primaryColor}
          strokeWidth="15"
        />
        <path
          d="M330 365L390 425"
          stroke={primaryColor}
          strokeWidth="22"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
};

export default TrabaheroLogo;
