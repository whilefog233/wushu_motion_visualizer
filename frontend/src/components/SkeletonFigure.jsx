// 发光骨架渲染：根据归一化点 + 骨骼连线输出 SVG
// 风格：青绿发光圆点 + 平滑连线，动作捕捉分析质感

export default function SkeletonFigure({
  pose,
  width = 400,
  height = 400,
  dotRadius = 7,
  strokeWidth = 3.5,
  color = '#3ff0cf',
  dimColor = null,
  showHead = true,
  className = '',
}) {
  const { points, bones } = pose
  const dim = dimColor || color

  return (
    <svg
      viewBox="0 0 1000 1000"
      width={width}
      height={height}
      className={className}
      style={{ overflow: 'visible' }}
    >
      <defs>
        <radialGradient id="dotGrad" cx="50%" cy="40%" r="65%">
          <stop offset="0%" stopColor="#eafffb" />
          <stop offset="45%" stopColor={color} />
          <stop offset="100%" stopColor={color} stopOpacity="0.85" />
        </radialGradient>
        <filter id="lineGlow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="dotGlow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="9" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* 头部光圈 */}
      {showHead && (
        <circle
          cx={points.head[0]}
          cy={points.head[1]}
          r={dotRadius * 2.6}
          stroke={color}
          strokeWidth={strokeWidth * 0.8}
          fill="none"
          opacity="0.85"
          filter="url(#lineGlow)"
        />
      )}

      {/* 骨骼连线 */}
      <g filter="url(#lineGlow)">
        {bones.map(([a, b], i) => (
          <line
            key={i}
            x1={points[a][0]}
            y1={points[a][1]}
            x2={points[b][0]}
            y2={points[b][1]}
            stroke={dim}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            opacity="0.92"
          />
        ))}
      </g>

      {/* 关节点 */}
      <g filter="url(#dotGlow)">
        {Object.entries(points).map(([name, [x, y]]) => (
          <circle key={name} cx={x} cy={y} r={dotRadius} fill="url(#dotGrad)" />
        ))}
      </g>
    </svg>
  )
}
