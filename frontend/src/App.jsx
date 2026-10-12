import { useCallback, useEffect, useRef, useState } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import UploadPanel from './components/UploadPanel'
import PipelineSteps from './components/PipelineSteps'
import StartButton from './components/StartButton'
import VideoStage from './components/VideoStage'
import ExportPanel from './components/ExportPanel'
import AnalysisTabs from './components/AnalysisTabs'
import ScorePanel from './components/ScorePanel'
import HistoryPage from './components/HistoryPage'
import SettingsPage from './components/SettingsPage'
import { uploadVideo, getStatus, getResult, getMetrics, getPose } from './api/client'

export default function App() {
  const [nav, setNav] = useState('home')
  const [file, setFile] = useState(null)
  const [task, setTask] = useState(null) // { id, status, stage, error, uploadPct }
  const [result, setResult] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [pose, setPose] = useState(null)
  const [frameIndex, setFrameIndex] = useState(0)
  const [seekFrame, setSeekFrame] = useState(null) // { frame, nonce }
  const [fatal, setFatal] = useState(null)
  const pollRef = useRef(null)
  const requestRef = useRef(0)

  const onFrame = useCallback((idx) => setFrameIndex(idx), [])
  const onSeek = useCallback((frame) => setSeekFrame({ frame, nonce: Date.now() }), [])

  // 拉取并保存一个已完成任务的全部结果（result/metrics/pose）
  const fetchResults = useCallback(async (id) => {
    const version = requestRef.current
    const [res, met, poseData] = await Promise.all([
      getResult(id),
      getMetrics(id).catch(() => null),
      getPose(id).catch(() => null),
    ])
    if (version !== requestRef.current) return null
    setResult(res)
    setMetrics(met)
    setPose(poseData)
    return res
  }, [])

  // 按 id 加载一个任务（URL 直达 / 历史打开复用）
  const loadTaskById = useCallback(
    async (id) => {
      const version = ++requestRef.current
      clearTimeout(pollRef.current)
      setTask(null); setFile(null); setResult(null); setMetrics(null); setPose(null); setFrameIndex(0); setSeekFrame(null)
      try {
        const s = await getStatus(id)
        if (version !== requestRef.current) return
        if (s.status === 'COMPLETED') {
          const loaded = await fetchResults(id)
          if (!loaded || version !== requestRef.current) return
          setTask({ id, status: 'COMPLETED', stage: 'COMPLETED' })
        } else if (s.status === 'FAILED') {
          setTask({ id, status: 'FAILED', stage: s.stage, error: s.error })
          setFatal(s.error || '该任务此前分析失败')
        } else {
          setTask({ id, status: 'RUNNING', stage: s.stage })
        }
      } catch {
        setFatal('任务不存在或已被删除')
      }
    },
    [fetchResults],
  )

  // URL ?id={analysis_id} 直达
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('id')
    if (id) loadTaskById(id)
  }, [loadTaskById])

  // 从历史页打开
  const openFromHistory = useCallback(
    (id) => {
      setFatal(null)
      setNav('home')
      loadTaskById(id)
    },
    [loadTaskById],
  )

  const startAnalysis = useCallback(async () => {
    if (!file) return
    ++requestRef.current
    setSeekFrame(null)
    setFatal(null); setResult(null); setMetrics(null); setPose(null); setFrameIndex(0)
    try {
      setTask({ status: 'UPLOADING', stage: 'UPLOADING', uploadPct: 0 })
      const created = await uploadVideo(file, (p) =>
        setTask((t) => ({ ...t, uploadPct: p })),
      )
      setTask({ id: created.analysis_id, status: 'RUNNING', stage: created.stage })
    } catch (e) {
      setTask({ status: 'FAILED', stage: 'UPLOADING', error: e.message })
      setFatal(e.message)
    }
  }, [file])

  // 轮询任务状态
  useEffect(() => {
    if (!task?.id || task.status !== 'RUNNING') return
    let stopped = false
    const tick = async () => {
      try {
        const version = requestRef.current
        const s = await getStatus(task.id)
        if (stopped || version !== requestRef.current) return
        if (s.status === 'COMPLETED') {
          await fetchResults(task.id) // 先拉结果再标记完成
          if (stopped || version !== requestRef.current) return
          setTask((t) => ({ ...t, status: 'COMPLETED', stage: 'COMPLETED', error: null }))
          return
        }
        setTask((t) => ({ ...t, status: s.status, stage: s.stage, error: s.error }))
        if (s.status === 'FAILED') {
          setFatal(s.error || '分析失败')
          return
        }
        pollRef.current = setTimeout(tick, 1500)
      } catch {
        if (!stopped) pollRef.current = setTimeout(tick, 2500)
      }
    }
    pollRef.current = setTimeout(tick, 1200)
    return () => {
      stopped = true
      clearTimeout(pollRef.current)
    }
  }, [task?.id, task?.status, fetchResults])

  const busy = task?.status === 'UPLOADING' || task?.status === 'RUNNING'

  return (
    <div className="app-shell">
      <Sidebar active={nav} onChange={setNav} />

      <main className="workspace-main">
        {nav === 'history' ? (
          <div className="p-6">
            <HistoryPage onOpen={openFromHistory} />
          </div>
        ) : nav === 'settings' ? (
          <div className="p-6">
            <SettingsPage />
          </div>
        ) : (
          <div className="workspace-content">
            <Header result={result} />

            {fatal && (
              <div className="rounded-xl border border-danger/35 bg-danger/10 px-4 py-2.5 text-[12.5px] text-danger">
                分析失败：{fatal}。可重新选择视频后再次点击“开始分析”。
              </div>
            )}

            <div className="setup-grid">
              <UploadPanel file={file} onFile={(selected) => { ++requestRef.current; setFile(selected); setTask(null); setResult(null); setMetrics(null); setPose(null); setFrameIndex(0); setSeekFrame(null); setFatal(null) }} disabled={busy} />
              <PipelineSteps task={task} />
              <StartButton onSettings={() => setNav('settings')} onClick={startAnalysis} busy={busy} disabled={!file} />
            </div>

            <div className="analysis-grid">
              <VideoStage file={file} task={task} result={result} pose={pose} metrics={metrics} onFrame={onFrame} seekFrame={seekFrame} frameIndex={frameIndex} onSeek={onSeek} />
              <AnalysisTabs result={result} metrics={metrics} pose={pose} frameIndex={frameIndex} onSeek={onSeek} />
            </div>
            <div className="score-section"><ScorePanel result={result} /></div>
            <ExportPanel result={result} />
          </div>
        )}
      </main>
    </div>
  )
}
