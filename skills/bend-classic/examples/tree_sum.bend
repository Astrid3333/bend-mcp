def build(rem, idx):
  if rem == 0:
    return Tree/Leaf {value: idx}
  else:
    return Tree/Node {left: build(rem - 1, idx * 2), right: build(rem - 1, idx * 2 + 1)}

def tsum(t):
  match t:
    case Tree/Leaf:
      return t.value
    case Tree/Node:
      return tsum(t.left) + tsum(t.right)

def main(depth):
  return tsum(build(depth, 0))
