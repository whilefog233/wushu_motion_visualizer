import CoreMetrics from './CoreMetrics'
import KineticMetrics from './KineticMetrics'
import PoseBody from './PoseBody'
import JointTrendChart from './JointTrendChart'

export default function PoseAnalysisTab({ metrics, pose, frameIndex, onSeek }) {
  return (
    <div className="space-y-3.5">
      <CoreMetrics metrics={metrics} frameIndex={frameIndex} />
      <KineticMetrics metrics={metrics} frameIndex={frameIndex} />
      <div className="pose-detail-grid">
        <PoseBody pose={pose} frameIndex={frameIndex} />
        <JointTrendChart metrics={metrics} frameIndex={frameIndex} onSeek={onSeek} />
      </div>
    </div>
  )
}
