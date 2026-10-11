import { IconLayers,IconTarget,IconUser,IconDoc } from './Icons'
export default function Header({result}) {
  const features=[
    {Icon:IconLayers,title:'一次推理，多模块复用',sub:'Multi-module Analysis'},
    {Icon:IconTarget,title:'直拳技术诊断',sub:'Punch Technique Analysis'},
    {Icon:IconUser,title:'Self Baseline 对照',sub:result?.technique?.reference_available?.self_baseline?'个人基线已启用':'完成分析后显示参考状态'},
    {Icon:IconDoc,title:'结果按需导出',sub:'Export On Demand'},
  ]
  return <header className="workspace-header">
    <div className="brand"><div className="brand-line"><div className="brand-symbol"><IconTarget/></div><div><div className="brand-title"><h1>武术 AI 教练系统</h1><span>V4</span></div><p className="brand-subtitle">MARTIAL ARTS AI COACH</p></div></div>
      <p className="brand-description">上传训练视频，一次姿态推理，串联骨架、运动学与发力链。<br/>从每一帧的真实表现，找到下一轮训练的重点。</p>
    </div>
    <div className="header-orbit" aria-hidden="true"><span/><span/><i/></div>
    <div className="feature-grid">{features.map(({Icon,title,sub})=><div className="feature-item" key={title}><span><Icon/></span><div><strong>{title}</strong><small>{sub}</small></div></div>)}</div>
  </header>
}

