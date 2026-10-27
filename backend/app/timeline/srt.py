"""SRT timestamps use exactly the same absolute frames as the renderer."""
from .schema import Timeline


def timestamp(frame: int, fps: int) -> str:
    milliseconds = round(frame * 1000 / fps)
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def render_srt(timeline: Timeline) -> str:
    cues = []
    for scene in timeline.scenes:
        for beat in scene.beats:
            for caption in beat.captions:
                cues.append(f"{len(cues) + 1}\n{timestamp(caption.start_frame, timeline.fps)} --> "
                            f"{timestamp(caption.end_frame, timeline.fps)}\n{caption.text}\n")
    return "\n".join(cues)
