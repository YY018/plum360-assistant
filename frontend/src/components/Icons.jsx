// Small line icons drawn for this site (24px grid, 1.5px stroke).
const PATHS = {
  lines: (
    <>
      <path d="M6 3v5.5c0 2.5 2.4 3.6 6 5.5" />
      <path d="M18 3v5.5c0 2.5-2.4 3.6-6 5.5" />
      <path d="M12 14v7" />
      <circle cx="6" cy="3" r="0.6" />
      <circle cx="18" cy="3" r="0.6" />
    </>
  ),
  valve: (
    <>
      <rect x="6" y="3" width="12" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h3" />
    </>
  ),
  air: (
    <>
      <circle cx="9" cy="14.5" r="3.5" />
      <circle cx="16.5" cy="8" r="2.2" />
      <circle cx="16" cy="17.5" r="1.3" />
    </>
  ),
  network: (
    <>
      <path d="M3.5 9a12 12 0 0 1 17 0" />
      <path d="M6.8 12.4a7.5 7.5 0 0 1 10.4 0" />
      <path d="M10 15.8a3 3 0 0 1 4 0" />
      <circle cx="12" cy="19" r="0.9" />
    </>
  ),
  library: (
    <>
      <path d="M5 4h3.5v16H5zM10.25 4h3.5v16h-3.5z" />
      <path d="M15.6 5.2l3.3-.9 3.1 15.4-3.3.9z" />
    </>
  ),
  hardware: (
    <>
      <path d="M12 3l7 3v5.5c0 4.6-3 7.7-7 9.5-4-1.8-7-4.9-7-9.5V6z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  expand: <path d="M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7" />,
  page: (
    <>
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v4h4M9 12h6M9 16h6" />
    </>
  ),
}

export function Icon({ name, size = 20, className = '' }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}
