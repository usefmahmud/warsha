/** Inline SVG icon set — no icon dependency, consistent 24px stroke grid. */

export type IconName =
  | 'select'
  | 'pen'
  | 'eraser'
  | 'rect'
  | 'circle'
  | 'triangle'
  | 'arrow'
  | 'text'
  | 'sticky'
  | 'image'
  | 'hand'
  | 'undo'
  | 'redo'
  | 'trash'
  | 'copy'
  | 'download'
  | 'share'
  | 'grid'
  | 'plus'
  | 'zoomIn'
  | 'zoomOut'
  | 'fit'
  | 'close'
  | 'check'
  | 'help'
  | 'back'
  | 'link'
  | 'sparkle'
  | 'save'
  | 'spinner';

const PATHS: Record<IconName, string> = {
  select: 'M5 3l14 8-6 1.6L10 20 5 3z',
  pen: 'M4 20l4-1 10-10a2.1 2.1 0 0 0-3-3L5 16l-1 4z M14 6l4 4',
  eraser: 'M8 19l-4-4 8-8 4 4-8 8zM10 21h10M7 12l4 4',
  rect: 'M4 5h16v14H4z',
  circle: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  triangle: 'M12 4L21 20H3L12 4z',
  arrow: 'M4 20L20 4M20 4h-7M20 4v7',
  text: 'M5 6V4h14v2M12 4v16M8 20h8',
  sticky: 'M4 4h16v10l-6 6H4V4zM20 14h-6v6',
  image: 'M4 5h16v14H4zM4 15l4-4 4 4 3-3 5 5M9 9.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  hand: 'M8 13V5.5a1.5 1.5 0 0 1 3 0V12m0-1.5V4.5a1.5 1.5 0 0 1 3 0V12m0-1V6a1.5 1.5 0 0 1 3 0v7.5c0 4-2.5 7-6 7-2.5 0-4-1-5.5-3L4 14c-.7-1 .3-2.4 1.5-1.9L8 13',
  undo: 'M4 9h9a4.5 4.5 0 0 1 0 9H7M4 9l4-4M4 9l4 4',
  redo: 'M20 9h-9a4.5 4.5 0 0 0 0 9h6M20 9l-4-4M20 9l-4 4',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
  copy: 'M9 9h10v10H9zM15 9V5H5v10h4',
  download: 'M12 4v11M8 11l4 4 4-4M5 20h14',
  share: 'M15 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM6 15a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM15 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM8.2 10.6l5-2.6M8.2 13.4l5 2.6',
  grid: 'M4 4h16v16H4zM4 9.3h16M4 14.6h16M9.3 4v16M14.6 4v16',
  plus: 'M12 5v14M5 12h14',
  zoomIn: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4M11 8v6M8 11h6',
  zoomOut: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4M8 11h6',
  fit: 'M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 13l4 4L19 7',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.2a2.6 2.6 0 1 1 3.6 2.4c-.7.4-1.1 1-1.1 1.8M12 17h.01',
  back: 'M14 6l-6 6 6 6',
  link: 'M10 13a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11.5 6M14 11a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 19.7L12.5 18',
  sparkle: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3zM18 16l.9 2.1L21 19l-2.1.9L18 22l-.9-2.1L15 19l2.1-.9L18 16z',
  save: 'M5 4h11l4 4v12H5zM8 4v6h7V4M8 20v-6h8v6',
  spinner: 'M12 3a9 9 0 1 0 9 9',
};

export function Icon({
  name,
  size = 20,
  className = '',
  strokeWidth = 1.7,
}: {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
