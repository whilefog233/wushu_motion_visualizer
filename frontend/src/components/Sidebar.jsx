import { IconHome, IconHistory, IconGear } from './Icons'

const nav = [
  { id: 'home', label: '首页', Icon: IconHome },
  { id: 'history', label: '历史', Icon: IconHistory },
  { id: 'settings', label: '设置', Icon: IconGear },
]

export default function Sidebar({ active = 'home', onChange }) {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-glow/40 to-mint-500/30 shadow-mint-glow">
        <svg viewBox="0 0 24 24" className="h-6 w-6 text-mint-300" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3c-2 3-5 4-5 8a5 5 0 0 0 10 0c0-4-3-5-5-8Z" />
          <path d="M9 15c0 3 1.2 5 3 6 1.8-1 3-3 3-6" />
        </svg>
      </div>

      {nav.map(({ id, label, Icon }) => {
        const on = active === id
        return (
          <button
            key={id}
            onClick={() => onChange?.(id)}
            aria-current={on ? 'page' : undefined}
            className={`group relative flex w-full flex-col items-center gap-1 py-2.5 transition ${
              on ? 'text-mint-300' : 'text-ink-500 hover:text-ink-100'
            }`}
          >
            {on && <span className="absolute left-0 h-7 w-[3px] rounded-r bg-mint-400 shadow-mint-glow" />}
            <Icon className="h-[22px] w-[22px]" />
            <span className="text-[10.5px] tracking-wide">{label}</span>
          </button>
        )
      })}
    </aside>
  )
}
