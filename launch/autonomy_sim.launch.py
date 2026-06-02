from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription(
        [
            ExecuteProcess(
                cmd=["bash", "-lc", "python3 -m autonomy.run_autonomy --config config/autonomy.yaml"],
                output="screen",
            ),
        ]
    )

