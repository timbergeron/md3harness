"""Small, dependency-free vector operations."""
import math

def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))

def dot(a, b):
    return sum(x*y for x, y in zip(a, b))

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def unit(v):
    if len(v) != 3 or not all(math.isfinite(x) for x in v):
        raise ValueError("normal must be a finite three-component vector")
    length = math.hypot(*v)
    if length < 1e-12:
        raise ValueError("zero-length normal")
    return tuple(x/length for x in v)
