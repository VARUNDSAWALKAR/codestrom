"""Small deterministic constructions, not an expression evaluator or physics engine."""
import math


def linear_points(slope: float, intercept: float, x_min: float, x_max: float,
                  y_min: float, y_max: float) -> list[dict[str, float]]:
    """Five samples of y=m*x+b, in a .1-.9 plot inset. Reject clipping."""
    if (not all(math.isfinite(v) and abs(v) <= 100 for v in
                (slope, intercept, x_min, x_max, y_min, y_max))
            or x_min >= x_max or y_min >= y_max):
        raise ValueError('Invalid linear plot limits')
    points = []
    for i in range(5):
        x = x_min+(x_max-x_min)*i/4
        y = slope*x+intercept
        if not y_min <= y <= y_max:
            raise ValueError('Linear plot exceeds declared range')
        points.append(dict(x=.1+.8*i/4, y=.9-.8*(y-y_min)/(y_max-y_min)))
    return points
