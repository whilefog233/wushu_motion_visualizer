import { IconArrowRight, IconGear } from './Icons'

export default function StartButton({ onClick, busy, disabled, onSettings }) {
  return (
    <section className="glass start-panel flex flex-col items-center justify-center gap-3 p-4">
      <button
        onClick={onClick}
        disabled={disabled || busy}
        className="relative w-full overflow-hidden rounded-xl bg-gradient-to-r from-mint-600 to-mint-400 py-3.5 text-[15px] font-bold text-space-950 shadow-mint-glow transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className="relative z-10 flex items-center justify-center gap-2">
          {busy ? '分析中...' : '开始分析'}
          {!busy && <IconArrowRight className="h-4 w-4" />}
        </span>
        {!busy && !disabled && (
          <span className="absolute inset-y-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-white/40 to-transparent" />
        )}
      </button>
      <button onClick={onSettings} className="flex items-center gap-1.5 text-[12px] text-ink-500 transition hover:text-ink-300">
        <IconGear className="h-4 w-4" />
        分析设置
      </button>
    </section>
  )
}
