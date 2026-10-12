import { useRef,useState } from 'react'
import { IconUploadCloud } from './Icons'
export default function UploadPanel({file,onFile,disabled}) {
  const inputRef=useRef(null)
  const [error,setError]=useState(''),[drag,setDrag]=useState(false)
  const choose=(f)=>{
    if(disabled||!f)return
    if(!/\.mp4$/i.test(f.name)){setError('请选择 MP4 视频，其他格式暂不支持。');return}
    setError('');onFile(f)
  }
  return <section className="glass upload-panel">
    <div className="section-heading"><span className="heading-icon"><IconUploadCloud/></span><h2>1. 上传视频</h2><span className="upload-format">MP4 · 横屏 / 竖屏</span></div>
    <button type="button" disabled={disabled} className={'upload-zone '+(drag?'dragging':'')} onClick={()=>inputRef.current?.click()}
      onDragOver={e=>{e.preventDefault();if(!disabled)setDrag(true)}} onDragLeave={()=>setDrag(false)}
      onDrop={e=>{e.preventDefault();setDrag(false);choose(e.dataTransfer.files?.[0])}}>
      <IconUploadCloud/><span className="upload-copy"><strong>{file?file.name:'点击上传视频或拖拽文件到此处'}</strong><small>{file?(file.size/1024/1024).toFixed(1)+' MB · 已选择':'保留原始比例，文件大小以服务端限制为准'}</small></span><span className="select-file">选择文件</span>
    </button>
    {error&&<p className="upload-error" role="alert">{error}</p>}
    <input ref={inputRef} type="file" accept=".mp4,video/mp4" className="hidden" onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
  </section>
}

