from src.analysis.metrics import infer_kinetic_chain_stage


BASE_PEAKS = {
    "ankle_speed_peak": 100.0,
    "hip_speed_peak": 100.0,
    "torso_angular_velocity_peak": 100.0,
    "wrist_speed_peak": 100.0,
}


def test_infer_kinetic_chain_stage_detects_lower_limb_drive():
    metrics = {
        **BASE_PEAKS,
        "left_ankle_speed": 90.0,
        "right_ankle_speed": 20.0,
        "hip_center_speed": 10.0,
        "torso_angular_velocity": 10.0,
        "left_wrist_speed": 5.0,
        "right_wrist_speed": 5.0,
    }

    assert infer_kinetic_chain_stage(metrics) == "Lower-limb drive"


def test_infer_kinetic_chain_stage_detects_upper_limb_release():
    metrics = {
        **BASE_PEAKS,
        "left_ankle_speed": 10.0,
        "right_ankle_speed": 10.0,
        "hip_center_speed": 10.0,
        "torso_angular_velocity": 10.0,
        "left_wrist_speed": 95.0,
        "right_wrist_speed": 40.0,
    }

    assert infer_kinetic_chain_stage(metrics) == "Upper-limb release"


def test_infer_kinetic_chain_stage_returns_transition_for_low_activity():
    metrics = {
        **BASE_PEAKS,
        "left_ankle_speed": 5.0,
        "right_ankle_speed": 5.0,
        "hip_center_speed": 5.0,
        "torso_angular_velocity": 5.0,
        "left_wrist_speed": 5.0,
        "right_wrist_speed": 5.0,
    }

    assert infer_kinetic_chain_stage(metrics) == "Transition / Hold"
