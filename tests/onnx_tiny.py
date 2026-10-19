"""Hand-encoded minimal ONNX models for tests (no `onnx` package needed).

Writes the protobuf wire format directly: one graph, one or two nodes,
float32 NCHW input. Enough to drive cv2.dnn.readNetFromONNX through the
imagemodels loaders without shipping real weights.
"""
import struct


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _key(field, wire):
    return _varint((field << 3) | wire)


def _bytes(field, payload):
    if isinstance(payload, str):
        payload = payload.encode()
    return _key(field, 2) + _varint(len(payload)) + payload


def _int(field, v):
    return _key(field, 0) + _varint(v)


def _value_info(name, dims):
    shape = b"".join(_bytes(1, _int(1, d)) for d in dims)        # Dimension.dim_value
    tensor = _int(1, 1) + _bytes(2, shape)                          # FLOAT, shape
    return _bytes(1, name) + _bytes(2, _bytes(1, tensor))            # name, TypeProto.tensor_type


def _node(op, inputs, outputs, attrs=b""):
    return (b"".join(_bytes(1, i) for i in inputs)
            + b"".join(_bytes(2, o) for o in outputs)
            + _bytes(4, op) + attrs)


def _tensor_float(name, dims, values):
    return (b"".join(_int(1, d) for d in dims) + _int(2, 1)
            + _bytes(8, name) + _bytes(9, struct.pack(f"<{len(values)}f", *values)))


def write_model(path, kind, size=32):
    """kind: "mean1" — (1,3,H,W) -> (1,1,H,W) channel mean (a matting /
    line-art / depth stand-in); "identity3" — (1,3,H,W) -> (1,3,H,W)
    (a 3-class parsing stand-in: argmax = the brightest channel)."""
    nodes, inits = [], []
    if kind == "mean1":
        # 1x1 conv with weights 1/3: channel mean, opset-independent
        inits.append(_tensor_float("w", [1, 3, 1, 1], [1 / 3] * 3))
        nodes.append(_node("Conv", ["x", "w"], ["y"]))
        out_dims = [1, 1, size, size]
    elif kind == "identity3":
        nodes.append(_node("Identity", ["x"], ["y"]))
        out_dims = [1, 3, size, size]
    else:
        raise ValueError(kind)
    graph = (b"".join(_bytes(1, n) for n in nodes) + _bytes(2, "g")
             + b"".join(_bytes(5, t) for t in inits)
             + _bytes(11, _value_info("x", [1, 3, size, size]))
             + _bytes(12, _value_info("y", out_dims)))
    model = (_int(1, 7) + _bytes(2, "tests")
             + _bytes(7, graph) + _bytes(8, _bytes(1, "") + _int(2, 13)))
    with open(path, "wb") as fh:
        fh.write(model)
    return path
