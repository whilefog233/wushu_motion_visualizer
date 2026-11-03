import { useEffect, useState } from 'react'
import { checkHealth } from '../api/client'

function Row({ k, v, ok }) {
  return (
    <div className="flex items-center justify-between border-t border-white/[.06] py-2.5 text-[12.5px]">
      <span className="text-ink-500">{k}</span>
      <span className={`font-mono ${ok === false ? 'text-warn' : ok === true ? 'text-mint-300' : 'text-ink-200'}`}>
        {v}
      </span>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <section className="glass p-4.5 p-5">
      <h3 className="mb-2 text-[15px] font-semibold text-ink-100">{title}</h3>
      {children}
    </section>
  )
}

export default function SettingsPage() {
  const [h, setH] = useState(null)
  useEffect(() => {
    checkHealth().then(setH)
  }, [])

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-[24px] font-bold text-ink-100">设置与关于</h2>
        <p className="mt-1 text-[12.5px] text-ink-500">系统状态、数据存储方式与能力边界。</p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <Card title="服务状态">
          {h ? (
            <div>
              <Row k="系统版本" v={h.version} ok />
              <Row k="运行状态" v={h.status} ok={h.status === 'ok'} />
              <Row k="最大并发任务" v={h.max_concurrent} />
              <Row k="API 认证" v={h.require_auth ? '已开启（X-API-Key）' : '未开启（同源免认证）'} ok />
              <Row
                k="AI 教练"
                v={h.ai_enabled ? `已开启 · ${h.ai_model || '默认模型'}` : '未开启'}
                ok={h.ai_enabled}
              />
            </div>
          ) : (
            <p className="text-[12.5px] text-ink-500">正在连接服务…</p>
          )}
        </Card>

        <Card title="数据如何保存">
          <ul className="space-y-2 text-[12.5px] leading-relaxed text-ink-300">
            <li>每次上传生成唯一 <span className="font-mono text-mint-300">analysis_id</span>，该视频全部数据存于 <span className="font-mono text-mint-300">data/analyses/{'{id}'}/</span>。</li>
            <li>目录内保留：source.mp4（原视频）、pose.json、metrics.csv、analysis/muscle/power_chain、评分与诊断。</li>
            <li>MediaPipe 对同一视频只推理一次；再次打开或分析同一视频直接复用 pose.json。</li>
            <li>分析只生成数据，骨架/肌肉视频需在导出时按需生成。</li>
          </ul>
        </Card>

        <Card title="能力边界">
          <ul className="space-y-2 text-[12.5px] leading-relaxed text-ink-300">
            <li>不测量真实拳力、真实肌电，不做医学诊断，不替代专业教练。</li>
            <li>速度为像素 / 身体尺度归一化单位，非真实米每秒；无法可靠换算时不伪造物理单位。</li>
            <li>无专家模板时，评分与对照属于基于个人基线和结构规则的实验性估计。</li>
          </ul>
        </Card>

        <Card title="运行方式">
          <ul className="space-y-2 text-[12.5px] leading-relaxed text-ink-300">
            <li>Windows：项目根运行 <span className="font-mono text-mint-300">.\start.ps1</span></li>
            <li>Linux/macOS：<span className="font-mono text-mint-300">./start.sh</span></li>
            <li>仅命令行分析：<span className="font-mono text-mint-300">python worker.py --input 视频.mp4</span></li>
            <li>接口文档：服务启动后访问 <span className="font-mono text-mint-300">/docs</span></li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
