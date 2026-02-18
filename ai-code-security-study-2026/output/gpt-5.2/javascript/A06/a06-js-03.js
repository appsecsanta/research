'use strict';

class ExpressionError extends Error {
  constructor(message, index) {
    super(index == null ? message : `${message} (at index ${index})`);
    this.name = 'ExpressionError';
    this.index = index;
  }
}

const ALLOWED_MATH_CONSTANTS = new Set([
  'E',
  'LN2',
  'LN10',
  'LOG2E',
  'LOG10E',
  'PI',
  'SQRT1_2',
  'SQRT2',
]);

const ALLOWED_MATH_FUNCTIONS = new Set([
  'abs',
  'acos',
  'acosh',
  'asin',
  'asinh',
  'atan',
  'atanh',
  'atan2',
  'cbrt',
  'ceil',
  'clz32',
  'cos',
  'cosh',
  'exp',
  'expm1',
  'floor',
  'fround',
  'hypot',
  'imul',
  'log',
  'log1p',
  'log10',
  'log2',
  'max',
  'min',
  'pow',
  'round',
  'sign',
  'sin',
  'sinh',
  'sqrt',
  'tan',
  'tanh',
  'trunc',
]);

function isIdentifierStart(ch) {
  return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || ch === '_' || ch === '$';
}

function isIdentifierPart(ch) {
  return isIdentifierStart(ch) || (ch >= '0' && ch <= '9');
}

function tokenize(input) {
  const s = String(input);
  const tokens = [];
  let i = 0;

  const push = (type, value, index) => tokens.push({ type, value, index });

  while (i < s.length) {
    const ch = s[i];

    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      i += 1;
      continue;
    }

    // Number: 123, 123.45, .45, 1e3, 1.2e-3
    if ((ch >= '0' && ch <= '9') || (ch === '.' && i + 1 < s.length && s[i + 1] >= '0' && s[i + 1] <= '9')) {
      const start = i;
      let hasDot = false;

      if (s[i] === '.') {
        hasDot = true;
        i += 1;
      }

      while (i < s.length && s[i] >= '0' && s[i] <= '9') i += 1;

      if (!hasDot && i < s.length && s[i] === '.') {
        hasDot = true;
        i += 1;
        while (i < s.length && s[i] >= '0' && s[i] <= '9') i += 1;
      }

      // exponent
      if (i < s.length && (s[i] === 'e' || s[i] === 'E')) {
        const ePos = i;
        i += 1;
        if (i < s.length && (s[i] === '+' || s[i] === '-')) i += 1;

        const digitsStart = i;
        while (i < s.length && s[i] >= '0' && s[i] <= '9') i += 1;

        if (digitsStart === i) {
          throw new ExpressionError('Invalid exponent in number literal', ePos);
        }
      }

      const raw = s.slice(start, i);
      const num = Number(raw);
      if (!Number.isFinite(num) && !Number.isNaN(num)) {
        // allow NaN? No number literal yields NaN; Infinity not representable without identifier.
        throw new ExpressionError('Invalid number literal', start);
      }
      push('number', num, start);
      continue;
    }

    // Identifier: Math, sqrt, etc.
    if (isIdentifierStart(ch)) {
      const start = i;
      i += 1;
      while (i < s.length && isIdentifierPart(s[i])) i += 1;
      const name = s.slice(start, i);
      push('identifier', name, start);
      continue;
    }

    // Operators / punctuators
    const start = i;

    if (ch === '*' && i + 1 < s.length && s[i + 1] === '*') {
      push('operator', '**', start);
      i += 2;
      continue;
    }

    if (ch === '+' || ch === '-' || ch === '*' || ch === '/' || ch === '%' || ch === '^') {
      // Note: '^' is commonly used for exponent in spreadsheets; we map it to '**' in parsing.
      push('operator', ch, start);
      i += 1;
      continue;
    }

    if (ch === '(' || ch === ')' || ch === ',' || ch === '.') {
      push('punctuator', ch, start);
      i += 1;
      continue;
    }

    throw new ExpressionError(`Unexpected character '${ch}'`, start);
  }

  tokens.push({ type: 'eof', value: null, index: s.length });
  return tokens;
}

function createParser(tokens) {
  let pos = 0;

  const peek = () => tokens[pos];
  const next = () => tokens[pos++];
  const match = (type, value) => {
    const t = peek();
    if (t.type !== type) return false;
    if (value !== undefined && t.value !== value) return false;
    return true;
  };
  const expect = (type, value) => {
    const t = peek();
    if (!match(type, value)) {
      const expected = value === undefined ? type : `${type} '${value}'`;
      const got = t.type === 'eof' ? 'end of input' : `${t.type} '${t.value}'`;
      throw new ExpressionError(`Expected ${expected} but got ${got}`, t.index);
    }
    return next();
  };

  function parseExpression() {
    return parseAdditive();
  }

  function parseAdditive() {
    let node = parseMultiplicative();
    while (match('operator', '+') || match('operator', '-')) {
      const op = next().value;
      const right = parseMultiplicative();
      node = { type: 'BinaryExpression', operator: op, left: node, right };
    }
    return node;
  }

  function parseMultiplicative() {
    let node = parseExponentiation();
    while (match('operator', '*') || match('operator', '/') || match('operator', '%')) {
      const op = next().value;
      const right = parseExponentiation();
      node = { type: 'BinaryExpression', operator: op, left: node, right };
    }
    return node;
  }

  function parseExponentiation() {
    let node = parseUnary();

    // Support '^' as exponent (spreadsheet-like), treat as right-associative.
    if (match('operator', '**') || match('operator', '^')) {
      const opTok = next();
      const right = parseExponentiation();
      node = { type: 'BinaryExpression', operator: opTok.value === '^' ? '**' : '**', left: node, right };
    }

    return node;
  }

  function parseUnary() {
    if (match('operator', '+') || match('operator', '-')) {
      const op = next().value;
      const argument = parseUnary();
      return { type: 'UnaryExpression', operator: op, argument };
    }
    return parsePostfix();
  }

  function parsePostfix() {
    let node = parsePrimary();

    // Member access and calls, left-to-right
    while (true) {
      if (match('punctuator', '.')) {
        next();
        const id = expect('identifier');
        node = { type: 'MemberExpression', object: node, property: { type: 'Identifier', name: id.value } };
        continue;
      }

      if (match('punctuator', '(')) {
        const startTok = next();
        const args = [];

        if (!match('punctuator', ')')) {
          while (true) {
            args.push(parseExpression());
            if (match('punctuator', ',')) {
              next();
              continue;
            }
            break;
          }
        }

        expect('punctuator', ')');
        node = { type: 'CallExpression', callee: node, arguments: args, index: startTok.index };
        continue;
      }

      break;
    }

    return node;
  }

  function parsePrimary() {
    const t = peek();

    if (match('number')) {
      next();
      return { type: 'Literal', value: t.value };
    }

    if (match('identifier')) {
      next();
      return { type: 'Identifier', name: t.value, index: t.index };
    }

    if (match('punctuator', '(')) {
      next();
      const expr = parseExpression();
      expect('punctuator', ')');
      return expr;
    }

    throw new ExpressionError(`Unexpected token ${t.type === 'eof' ? 'end of input' : `'${t.value}'`}`, t.index);
  }

  function parse() {
    const ast = parseExpression();
    expect('eof');
    return ast;
  }

  return { parse };
}

function safeGetMathProperty(propName, index) {
  if (propName === '__proto__' || propName === 'prototype' || propName === 'constructor') {
    throw new ExpressionError(`Access to forbidden property '${propName}'`, index);
  }

  if (ALLOWED_MATH_CONSTANTS.has(propName)) return Math[propName];
  if (ALLOWED_MATH_FUNCTIONS.has(propName)) return Math[propName];

  throw new ExpressionError(`Math.${propName} is not allowed`, index);
}

function evaluateAst(node, ctx) {
  switch (node.type) {
    case 'Literal': {
      const v = node.value;
      if (typeof v !== 'number') throw new ExpressionError('Only numeric literals are allowed');
      return v;
    }

    case 'Identifier': {
      const name = node.name;

      if (name === 'Infinity') return Infinity;
      if (name === 'NaN') return NaN;

      if (Object.prototype.hasOwnProperty.call(ctx, name)) return ctx[name];

      throw new ExpressionError(`Unknown identifier '${name}'`, node.index);
    }

    case 'MemberExpression': {
      // Only allow Math.<prop> (no arbitrary objects)
      if (node.object.type !== 'Identifier' || node.object.name !== 'Math') {
        throw new ExpressionError('Only Math.<property> member access is allowed');
      }
      const propName = node.property?.name;
      if (!propName || typeof propName !== 'string') {
        throw new ExpressionError('Invalid member access');
      }
      return safeGetMathProperty(propName, node.property.index);
    }

    case 'CallExpression': {
      const callee = node.callee;

      // Only allow calling Math.<function>(...)
      if (callee.type !== 'MemberExpression') {
        throw new ExpressionError('Only Math.<function>(...) calls are allowed', node.index);
      }
      if (callee.object.type !== 'Identifier' || callee.object.name !== 'Math') {
        throw new ExpressionError('Only Math.<function>(...) calls are allowed', node.index);
      }

      const fnName = callee.property?.name;
      if (!fnName || typeof fnName !== 'string') throw new ExpressionError('Invalid function call', node.index);
      if (!ALLOWED_MATH_FUNCTIONS.has(fnName)) {
        throw new ExpressionError(`Math.${fnName}(...) is not allowed`, node.index);
      }

      const fn = Math[fnName];
      const args = node.arguments.map((arg) => evaluateAst(arg, ctx));

      for (const a of args) {
        if (typeof a !== 'number') throw new ExpressionError('Function arguments must be numbers', node.index);
      }

      const result = fn.apply(Math, args);
      if (typeof result !== 'number') throw new ExpressionError('Expression did not evaluate to a number', node.index);
      return result;
    }

    case 'UnaryExpression': {
      const v = evaluateAst(node.argument, ctx);
      if (typeof v !== 'number') throw new ExpressionError('Unary operator applied to non-number');
      if (node.operator === '+') return +v;
      if (node.operator === '-') return -v;
      throw new ExpressionError(`Unsupported unary operator '${node.operator}'`);
    }

    case 'BinaryExpression': {
      const left = evaluateAst(node.left, ctx);
      const right = evaluateAst(node.right, ctx);
      if (typeof left !== 'number' || typeof right !== 'number') {
        throw new ExpressionError('Binary operator applied to non-number');
      }

      switch (node.operator) {
        case '+':
          return left + right;
        case '-':
          return left - right;
        case '*':
          return left * right;
        case '/':
          return left / right;
        case '%':
          return left % right;
        case '**':
          return left ** right;
        default:
          throw new ExpressionError(`Unsupported operator '${node.operator}'`);
      }
    }

    default:
      throw new ExpressionError(`Unsupported AST node type '${node.type}'`);
  }
}

function evaluateMathExpression(expression) {
  const tokens = tokenize(expression);
  const parser = createParser(tokens);
  const ast = parser.parse();

  const ctx = Object.freeze({ Math });

  const result = evaluateAst(ast, ctx);

  if (typeof result !== 'number') throw new ExpressionError('Expression did not evaluate to a number');
  return result;
}

module.exports = { evaluateMathExpression, ExpressionError };
