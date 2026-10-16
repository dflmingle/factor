"""Typed prefix expression grammar, generated on demand rather than a formula bank.

Types distinguish numeric expressions from positive trailing-window parameters.
Depth/node caps are resource guards; they do not enumerate admissible formulas.
Only causal operators are admitted. No eval(), imports or target-data terminals.
"""
from dataclasses import dataclass
import json
import math
import numpy as np

FIELDS = ('close', 'open', 'high', 'low', 'amount', 'volume', 'turnover', 'cap', 'bm', 'ep', 'cfp', 'sp', 'roe', 'roic', 'gm', 'assets_growth', 'current_ratio', 'leverage')
UNARY = ('neg', 'abs', 'logabs', 'sqrtabs', 'rank', 'zscore')
BINARY = ('add', 'sub', 'mul', 'div', 'mean2', 'max2', 'min2', 'ts_corr', 'less2')
TERNARY = ('where',)
TRAILING = ('delay', 'ts_mean', 'ts_std', 'ts_max', 'ts_min', 'ema', 'sma', 'ts_rank', 'ts_skew', 'ts_kurt', 'ts_sum', 'ts_corr', 'decaylinear')
WINDOWS = tuple(range(1, 121)) + (180, 252, 504, 756)
CONSTANTS = (-100., -10., -4., -1., -.15, -.1, 0., 1e-6, .1, .15, .2, .3, .5, .7, .8, .85, 1., 2., 4., 5., 10., 100.)

def arity(name):return 3 if name in TERNARY else 2 if name in BINARY else 1


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple = ()
    value: object = None

    @property
    def nodes(self):
        return 1 + sum(x.nodes for x in self.args)

    @property
    def depth(self):
        return 1 + max((x.depth for x in self.args), default=0)

    @property
    def fields(self):
        if self.op == 'field':
            return frozenset([self.value])
        return frozenset().union(*(x.fields for x in self.args))

    def json(self):
        d = dict(op=self.op)
        if self.args:
            d['args'] = [x.json() for x in self.args]
        if self.value is not None:
            d['value'] = self.value
        return d

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict) or set(data) - {'op', 'args', 'value'}:
            raise ValueError('Invalid AST schema')
        return cls(data['op'], tuple(cls.from_json(x) for x in data.get('args', [])), data.get('value'))

    def key(self):
        return json.dumps(self.json(), sort_keys=True, separators=(',', ':'))


def field(name): return Expr('field', value=name)
def const(x): return Expr('const', value=float(x))
def op(name, *args, window=None): return Expr(name, tuple(args), window)


def validate(expr, max_depth=10, max_nodes=100):
    if expr.depth > max_depth or expr.nodes > max_nodes:
        raise ValueError('Expression exceeds configured resource limits')
    if expr.op == 'field':
        if expr.value not in FIELDS or expr.args: raise ValueError('Unknown field')
    elif expr.op == 'const':
        if expr.args or not isinstance(expr.value, (int, float)) or not math.isfinite(expr.value):
            raise ValueError('Invalid constant')
        if not -100 <= expr.value <= 100: raise ValueError('Constant outside parameter bounds')
    elif expr.op in UNARY + BINARY + TERNARY + TRAILING:
        if len(expr.args) != arity(expr.op): raise ValueError('Arity mismatch')
        if expr.op in TRAILING:
            if type(expr.value) is not int or expr.value not in WINDOWS: raise ValueError('Noncausal/invalid window')
        elif expr.value is not None: raise ValueError('Unexpected operator parameter')
        for child in expr.args: validate(child, max_depth, max_nodes)
    else:
        raise ValueError('Unsupported operator: ' + str(expr.op))
    return expr


def paths(expr, prefix=()):
    result = [(prefix, expr)]
    for i, child in enumerate(expr.args): result += paths(child, prefix + (i,))
    return result


def replace(expr, path, replacement):
    if not path: return replacement
    children = list(expr.args)
    children[path[0]] = replace(children[path[0]], path[1:], replacement)
    return Expr(expr.op, tuple(children), expr.value)


def tokens(expr):
    if expr.op == 'field': return ['F:' + expr.value]
    if expr.op == 'const': return ['C:' + format(expr.value, '.12g')]
    out = [expr.op]
    if expr.op in TRAILING: out += ['W:' + str(expr.value)]
    for x in expr.args: out += tokens(x)
    return out


def decode(sequence):
    seq = iter(sequence)
    def read():
        token = next(seq)
        if token.startswith('F:'): return field(token[2:])
        if token.startswith('C:'): return const(float(token[2:]))
        n = int(next(seq)[2:]) if token in TRAILING else None
        if token not in UNARY + BINARY + TERNARY + TRAILING: raise ValueError('Unknown prefix token')
        return Expr(token, tuple(read() for _ in range(arity(token))), n)
    try: result = read()
    except StopIteration as exc: raise ValueError('Incomplete expression') from exc
    if next(seq, None) is not None: raise ValueError('Trailing tokens')
    return validate(result)


def formula(e):
    if e.op == 'field': return {'cap':'MARKET_CAP','bm':'BOOK_TO_MARKET_RATIO_LF','ep':'RATIO_EP_TTM','cfp':'RATIO_CFP_TTM','sp':'RATIO_SP_TTM'}.get(e.value, e.value.upper())
    if e.op == 'const': return format(e.value, '.12g')
    a = [formula(x) for x in e.args]
    if e.op == 'neg': return '(-' + a[0] + ')'
    if e.op == 'less2':return '('+a[0]+'<'+a[1]+')'
    if e.op == 'where':return 'IF('+','.join(a)+')'
    if e.op in ('add', 'sub', 'mul', 'div'):
        return '(' + a[0] + {'add': '+', 'sub': '-', 'mul': '*', 'div': '/'}[e.op] + a[1] + ')'
    if e.op == 'logabs': return 'LOG(MAX(ABS(' + a[0] + '),1e-12))'
    if e.op == 'sqrtabs': return '(ABS(' + a[0] + ')**0.5)'
    name = {'mean2': 'MEAN', 'max2': 'MAX', 'min2': 'MIN', 'ts_std': 'STDDEV'}.get(e.op, e.op.upper())
    if e.op in TRAILING: a += [str(e.value)]
    if e.op == 'sma': a += ['1']
    return name + '(' + ','.join(a) + ')'


class Grammar:
    def __init__(self, max_depth=7, max_nodes=47):
        self.max_depth, self.max_nodes = max_depth, max_nodes
        self.vocab = list(dict.fromkeys(UNARY + BINARY + TERNARY + TRAILING)) + ['F:' + x for x in FIELDS]
        self.vocab += ['C:' + format(x, '.12g') for x in CONSTANTS]
        self.vocab += ['W:' + str(x) for x in WINDOWS]
        self.ids = {t: i for i, t in enumerate(self.vocab)}

    def state(self, prefix):
        """Pending typed slots, depth, and expression node budget."""
        stack, used = [('expr', 1)], 0
        for token in prefix:
            if not stack: raise ValueError('Prefix already terminal')
            kind, depth = stack.pop()
            if kind == 'window':
                if token not in ['W:' + str(n) for n in WINDOWS]: raise ValueError('Expected positive window')
                continue
            used += 1
            if token.startswith(('F:', 'C:')): continue
            if token not in UNARY + BINARY + TERNARY + TRAILING: raise ValueError('Expected expression token')
            stack += [('expr', depth + 1)] * arity(token)
            if token in TRAILING: stack.append(('window', depth))
        return stack, used

    def legal(self, prefix):
        stack, used = self.state(prefix)
        if not stack: return []
        kind, depth = stack[-1]
        if kind == 'window': return [self.ids['W:' + str(n)] for n in WINDOWS]
        remaining_expr = sum(k == 'expr' for k, _ in stack) - 1
        leaves = [self.ids[t] for t in self.vocab if t.startswith(('F:', 'C:'))]
        if depth >= self.max_depth: return leaves
        out = leaves.copy()
        for token in dict.fromkeys(UNARY + BINARY + TERNARY + TRAILING):
            if used + 1 + arity(token) + remaining_expr <= self.max_nodes: out.append(self.ids[token])
        return out

    def prior(self, prefix, legal):
        # This is a generative structural prior, with known proposal probability.
        weights = []
        stack, _ = self.state(prefix)
        for i in legal:
            t = self.vocab[i]
            if t.startswith('W:'):
                n = int(t[2:]); weight = math.exp(-n / 120) * (3 if n in (1, 3, 5, 10, 14, 20, 60) else 1)
            elif t.startswith('F:'): weight = 4.
            elif t.startswith('C:'): weight = 1.
            else: weight = 1.2 / max(1, stack[-1][1] - 1)
            weights.append(weight)
        p = np.array(weights, float); return p / p.sum()

    def sample(self, rng, prefix=()):
        prefix = list(prefix)
        while self.legal(prefix):
            legal = self.legal(prefix)
            i = int(rng.choice(legal, p=self.prior(prefix, legal)))
            prefix.append(self.vocab[i])
        return decode(prefix)

    def log_prob(self, expression):
        prefix = []; result = 0.
        for token in tokens(expression):
            legal = self.legal(prefix)
            if token not in self.ids or self.ids[token] not in legal: return -math.inf
            result += math.log(self.prior(prefix, legal)[legal.index(self.ids[token])])
            prefix.append(token)
        return result

    def mutate(self, expression, rng):
        """Real subtree insertion/deletion/replacement; parameters also mutate."""
        for _ in range(40):
            choices = paths(expression); path, node = choices[int(rng.integers(len(choices)))]
            mode = int(rng.integers(5))
            if mode == 0 and node.args: new = node.args[int(rng.integers(len(node.args)))]
            elif mode == 1: new = op(str(rng.choice(UNARY)), node)
            elif mode == 2: new = op(str(rng.choice(BINARY)), node, self.sample(rng))
            elif mode == 3 and node.op in TRAILING: new = Expr(node.op, node.args, int(rng.choice(WINDOWS)))
            elif mode == 3 and node.op == 'const': new = const(float(rng.choice(CONSTANTS)))
            else: new = self.sample(rng)
            candidate = replace(expression, path, new)
            try: validate(candidate, self.max_depth, self.max_nodes)
            except ValueError: continue
            if candidate.fields: return candidate
        return expression


def seed_pool():
    c, a, t, cap = [field(n) for n in ('close', 'amount', 'turnover', 'cap')]
    ret = op('sub', op('div', c, op('delay', c, window=1)), const(1))
    delta = op('sub', c, op('delay', c, window=1))
    up = op('sma', op('max2', delta, const(0)), window=14)
    down = op('sma', op('max2', op('neg', delta), const(0)), window=14)
    rsi = op('div', op('mul', const(-100), up), op('add', up, down))
    return (op('rank', op('neg', op('ts_mean', a, window=5))),
            op('neg', op('ts_mean', t, window=3)),
            op('neg', op('ts_std', ret, window=20)), rsi, op('neg', cap))
