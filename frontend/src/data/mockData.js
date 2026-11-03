// ============================================================
// Mock 数据：后续接入真实后端时，用 API 返回值替换本文件即可
// ============================================================

// 视频信息
export const videoInfo = {
  frame: 28,
  totalFrames: 95,
  fps: 30.0,
  durationSec: 12,
  speed: 1.0,
}

// 当前帧核心指标
export const currentMetrics = [
  { key: 'leftKnee', label: '左膝角度', value: '171.0', unit: '°', status: 'ok', range: '标准范围 165°~180°' },
  { key: 'rightKnee', label: '右膝角度', value: '177.5', unit: '°', status: 'ok', range: '标准范围 165°~180°' },
  { key: 'leftElbow', label: '左肘角度', value: '149.4', unit: '°', status: 'warn', range: '标准范围 150°~170°' },
  { key: 'rightElbow', label: '右肘角度', value: '139.2', unit: '°', status: 'bad', range: '标准范围 150°~170°' },
  { key: 'torso', label: '躯干倾斜', value: '0.8', unit: '°', status: 'ok', range: '标准范围 -5°~5°' },
]

// 关节角度趋势（12s，每 2s 一个采样）
export const jointTrend = {
  x: [0, 2, 4, 6, 8, 10, 12],
  series: [
    { name: '左膝', color: '#22d3ee', data: [168, 172, 170, 175, 171, 174, 172] },
    { name: '右膝', color: '#34d399', data: [172, 176, 174, 178, 175, 177, 176] },
    { name: '左肘', color: '#fbbf24', data: [155, 162, 158, 165, 150, 156, 160] },
    { name: '右肘', color: '#f87171', data: [140, 152, 148, 158, 139, 146, 150] },
    { name: '躯干', color: '#c084fc', data: [2, 3, 1, 4, 0.8, 2, 1] },
  ],
}

// 动作评分
export const motionScore = {
  total: 78,
  bars: [
    { name: '姿态稳定性', value: 85, color: '#3ff0cf' },
    { name: '发力协调性', value: 72, color: '#8b7bff' },
    { name: '动作完成度', value: 80, color: '#3ff0cf' },
    { name: '力量传导', value: 68, color: '#ffb547' },
  ],
}

// 关键帧
export const keyFrames = [1, 12, 28, 45, 60, 78, 95]

// ---- 发力链（髋→肩→肘→腕 时序，单位秒）----
export const powerChain = {
  events: [
    { joint: '髋', start: 0.42, peak: 0.61, color: '#8b7bff' },
    { joint: '肩', start: 0.55, peak: 0.74, color: '#5b8cff' },
    { joint: '肘', start: 0.66, peak: 0.85, color: '#3ff0cf' },
    { joint: '腕', start: 0.74, peak: 0.95, color: '#7ff5e2' },
  ],
  gaps: [
    { from: '髋', to: '肩', ms: 130, ok: true },
    { from: '肩', to: '肘', ms: 110, ok: true },
    { from: '肘', to: '腕', ms: 100, ok: true },
  ],
}

// ---- V3 技术诊断 ----
export const diagnoses = [
  {
    id: 'insufficient_hip',
    title: '髋部参与不足',
    severity: 'medium',
    confidence: 0.72,
    evidence: '髋角速度峰值 215°/s，仅为个人基线均值（370°/s）的 58%；髋峰值帧 #18。',
    meaning: '动力链的第一环没有充分启动，肩臂需要承担更多发力，末端速度会受限。',
    advice: '降速 30% 做空击，每拳先感受髋部转动，再让肩跟出。',
  },
  {
    id: 'slow_recovery',
    title: '回收速度偏慢',
    severity: 'low',
    confidence: 0.64,
    evidence: '回收阶段用时 0.48s，个人最佳 0.31s；回收腕速峰值 -142px/s。',
    meaning: '回收拖沓会暴露空当，连续出拳节奏也会被拖慢。',
    advice: '打靶后主动“弹回”护手位置，按节拍器 1 拍出、1 拍收。',
  },
  {
    id: 'stability_improved',
    title: '身体稳定性较过去提高',
    severity: 'positive',
    confidence: 0.88,
    evidence: '头部最大位移 4.2px（近 10 次均值 9.6px），重心轨迹标准差下降 41%。',
    meaning: '躯干控制在进步，发力时身体没有多余晃动。',
    advice: '保持当前的重心控制，下一阶段把注意力放到髋部启动上。',
  },
]

// ---- AI 教练建议 ----
export const aiAdvice = {
  summary: '本次出拳身体稳定性明显进步，但髋部参与不足，动作仍偏“手臂主导”，末端速度没有被放大。',
  priorityDrill: '扶墙慢速转髋出拳 × 3 组 × 20 次，重点：髋先动、肩再跟。',
  standard: [
    '准备：重心微沉，护手持稳，目视目标',
    '启动：先转髋、送重心，肩自然被带出',
    '加速：肘沿直线伸展，拳面旋转向前',
    '击打：腕部最后弹出，末端速度达到峰值',
    '回收：沿原路线快速弹回护手位',
  ],
  nextSession: [
    '降速空击，专练髋启动（3 组 × 20 次）',
    '节拍器练习出/收各 1 拍，提升回收速度',
    '每组录 1 次视频，对比髋峰值是否接近基线',
  ],
  compare: '相比上次：稳定性 +41%，髋参与 -8%，总分 +3。',
  confidence: 0.78,
}

// ---- 骨架关键点（归一化 0~1000，直拳定格：右手前伸）----
export const skeletonPose = {
  points: {
    head: [500, 165],
    neck: [500, 250],
    leftShoulder: [425, 275],
    rightShoulder: [575, 275],
    leftElbow: [370, 405],
    rightElbow: [660, 320],
    leftWrist: [345, 530],
    rightWrist: [835, 340],
    leftHip: [450, 555],
    rightHip: [550, 555],
    leftKnee: [428, 720],
    rightKnee: [575, 715],
    leftAnkle: [415, 905],
    rightAnkle: [590, 900],
  },
  bones: [
    ['head', 'neck'],
    ['neck', 'leftShoulder'], ['neck', 'rightShoulder'],
    ['leftShoulder', 'leftElbow'], ['leftElbow', 'leftWrist'],
    ['rightShoulder', 'rightElbow'], ['rightElbow', 'rightWrist'],
    ['leftShoulder', 'leftHip'], ['rightShoulder', 'rightHip'],
    ['leftHip', 'rightHip'],
    ['leftHip', 'leftKnee'], ['leftKnee', 'leftAnkle'],
    ['rightHip', 'rightKnee'], ['rightKnee', 'rightAnkle'],
  ],
}

// ---- 技术对比（标准 vs 当前）----
export const techCompare = {
  standard: {
    label: '标准动作',
    ok: true,
    items: [
      { name: '发力顺序', value: '髋→肩→肘→腕', ok: true },
      { name: '髋肩间隔', value: '90~140ms', ok: true },
      { name: '末端放大比', value: '≥ 1.8×', ok: true },
      { name: '回收时间', value: '≤ 0.35s', ok: true },
    ],
  },
  current: {
    label: '当前动作',
    ok: false,
    items: [
      { name: '发力顺序', value: '髋→肩→肘→腕', ok: true },
      { name: '髋肩间隔', value: '130ms', ok: true },
      { name: '末端放大比', value: '1.4×', ok: false },
      { name: '回收时间', value: '0.48s', ok: false },
    ],
  },
}
