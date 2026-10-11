import { useEffect, useState } from 'react'
import { listAnalyses } from '../api/client'

const STATUS = {
  COMPLETED: { cls: 'bg-mint-500/12 text-mint-300 border-mint-500/30', label: '已完成' },
  FAILED: { cls: 'bg-danger/12 text-danger border-danger/30', label: '失败' },
  RUNNING: { cls: 'bg-violet-glow/15 text-violet-glow border-violet-glow/30', label: '分析中' },
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { hour12: false })
}

function Card({ item, onOpen }) {
  const v = item.video || {}
  const st = STATUS[item.status] || { cls: 'bg-white/8 text-ink-500 border-white/15', label: item.status }
  return (
    <button
      type="button"
      onClick={() => item.status === 'COMPLETED' && onOpen(item.analysis_id)}
      disabled={item.status !== 'COMPLETED'}
      className="glass group flex flex-col gap-2.5 p-4 text-left transition enabled:hover:border-mint-500/40 disabled:opacity-60"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="line-clamp-2 min-w-0 text-[13.5px] font-medium leading-snug text-ink-100">
          {item.source_filename}
        </span>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${st.cls}`}>{st.label}</span>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-ink-500">
        {v.duration != null && (
          <span>时长 <span className="font-mono text-ink-300">{Number(v.duration).toFixed(1)}s</span></span>
        )}
        {v.frame_count != null && (
          <span>帧数 <span className="font-mono text-ink-300">{v.frame_count}</span></span>
        )}
        {v.fps != null && (
          <span>FPS <span className="font-mono text-ink-300">{Number(v.fps).toFixed(1)}</span></span>
        )}
        {v.width != null && v.height != null && (
          <span>分辨率 <span className="font-mono text-ink-300">{v.width}×{v.height}</span></span>
        )}
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-white/[.06] pt-2.5 text-[10.5px] text-ink-700">
        <span className="font-mono">{item.analysis_id}</span>
        <span>{fmtTime(item.created_at)}</span>
      </div>
    </button>
  )
}

export default function HistoryPage({ onOpen }) {
  const [items, setItems] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    listAnalyses()
      .then((d) => setItems(d.analyses))
      .catch((e) => setErr(e.message))
  }, [])

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-[24px] font-bold text-ink-100">历史分析</h2>
        <p className="mt-1 text-[12.5px] text-ink-500">
          所有分析按 analysis_id 保存在 data/analyses/，点击卡片可重新打开完整结果。
        </p>
      </div>

      {err && <p className="text-[13px] text-danger">加载失败：{err}</p>}
      {items == null && !err && <p className="text-[13px] text-ink-500">加载中…</p>}
      {items && items.length === 0 && (
        <div className="glass flex h-48 items-center justify-center text-[13px] text-ink-500">
          还没有分析记录，回到首页上传第一段视频吧。
        </div>
      )}
      {items && items.length > 0 && (
        <div className="grid grid-cols-3 gap-4 xl:grid-cols-4">
          {items.map((it) => (
            <Card key={it.analysis_id} item={it} onOpen={onOpen} />
          ))}
        </div>
      )}
    </div>
  )
}
