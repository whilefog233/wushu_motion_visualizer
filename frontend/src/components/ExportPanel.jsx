import { fileUrl } from '../api/client'
export default function ExportPanel({result}) {
  const files=Object.entries(result?.files || {}).filter(([,name])=>typeof name==='string')
  return <section className="glass export-panel"><div><h2>分析资料与导出</h2><p>下载本次分析实际生成的文件</p></div>
    {files.length?<div className="export-links">{files.map(([key,name])=><a key={key} href={fileUrl(result.analysis_id,name)} download>{({metrics:'运动指标 CSV',pose:'骨架数据 JSON',summary:'训练摘要',power_chain:'发力链数据',muscle:'肌肉分析',metadata:'视频信息',analysis:'分析结果',coach_input:'教练输入',performance:'运行统计'})[key] || name}<span>↗</span></a>)}</div>:<p>完成分析后可导出结果</p>}
  </section>
}

