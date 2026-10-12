// 线性图标集合（stroke 风格，继承 currentColor）

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

export const IconHome = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M9.5 21v-6h5v6" /></svg>
)
export const IconHistory = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></svg>
)
export const IconFolder = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" /></svg>
)
export const IconGear = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="3.2" /><path d="M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1 5.3 5.3" /></svg>
)
export const IconUploadCloud = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 16v-9" /><path d="m8 10 4-4 4 4" /><path d="M4.5 15.5v2A2.5 2.5 0 0 0 7 20h10a2.5 2.5 0 0 0 2.5-2.5v-2" /></svg>
)
export const IconPlay = (p) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...p}><path d="M8 5.5v13l11-6.5Z" /></svg>
)
export const IconVolume = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5Z" /><path d="M16.5 9a4 4 0 0 1 0 6" /></svg>
)
export const IconFullscreen = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
)
export const IconCheck = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="m5 12.5 4.5 4.5L19 7" /></svg>
)
export const IconChevronLeft = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="m14 6-6 6 6 6" /></svg>
)
export const IconChevronRight = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="m10 6 6 6-6 6" /></svg>
)
export const IconArrowRight = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 12h16" /><path d="m13 6 6 6-6 6" /></svg>
)
export const IconBolt = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M13 2 4.5 13.5H11l-1 8.5 8.5-11.5H12Z" /></svg>
)
export const IconTarget = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.4" fill="currentColor" /></svg>
)
export const IconLayers = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="m12 3 9 5-9 5-9-5Z" /><path d="m3 13 9 5 9-5" /></svg>
)
export const IconRefresh = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M20 12a8 8 0 1 1-2.3-5.6" /><path d="M20 3.5V8h-4.5" /></svg>
)
export const IconDoc = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M6 2.5h8L20 8.5V20a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 6 20Z" /><path d="M14 2.5V8.5h6" /></svg>
)
export const IconSpark = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></svg>
)
export const IconUser = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><circle cx="12" cy="7.5" r="3.5" /><path d="M5 20.5c.8-3.5 3.6-5 7-5s6.2 1.5 7 5" /></svg>
)
export const IconAlert = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 3.5 21.5 20h-19Z" /><path d="M12 10v4.5" /><circle cx="12" cy="17.6" r="0.6" fill="currentColor" /></svg>
)
