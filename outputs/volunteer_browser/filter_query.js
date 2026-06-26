(function attachVolunteerQuery(global) {
  const OPERATORS = {
    and: "AND",
    "&&": "AND",
    "且": "AND",
    "与": "AND",
    "和": "AND",
    or: "OR",
    "||": "OR",
    "或": "OR",
    not: "NOT",
    "!": "NOT",
    "-": "NOT",
    "非": "NOT",
    "不含": "NOT",
    "不包含": "NOT",
    contains: "CONTAINS",
    "包含": "CONTAINS",
  };

  function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function tokenize(input) {
    const source = String(input || "");
    const tokens = [];
    let i = 0;

    while (i < source.length) {
      const char = source[i];
      if (/\s/.test(char)) {
        i += 1;
        continue;
      }
      if (char === "(" || char === ")" || char === "!" || char === "-") {
        tokens.push({ type: char === "(" ? "LPAREN" : char === ")" ? "RPAREN" : OPERATORS[char], raw: char });
        i += 1;
        continue;
      }
      if (char === '"' || char === "'") {
        const quote = char;
        let value = "";
        i += 1;
        while (i < source.length) {
          const next = source[i];
          if (next === "\\" && i + 1 < source.length) {
            value += source[i + 1];
            i += 2;
            continue;
          }
          if (next === quote) break;
          value += next;
          i += 1;
        }
        if (i >= source.length || source[i] !== quote) {
          throw new Error("引号未闭合");
        }
        if (!value.trim()) {
          throw new Error("引号内不能是空条件");
        }
        tokens.push({ type: "TERM", value: value.trim(), raw: value.trim() });
        i += 1;
        continue;
      }

      let value = "";
      while (i < source.length && !/\s|\(|\)/.test(source[i])) {
        value += source[i];
        i += 1;
      }
      const normalized = normalizeText(value);
      const operator = OPERATORS[normalized] || OPERATORS[value];
      if (operator) {
        tokens.push({ type: operator, raw: value });
      } else if (value.trim()) {
        tokens.push({ type: "TERM", value: value.trim(), raw: value.trim() });
      }
    }

    return tokens;
  }

  function parse(input) {
    const tokens = tokenize(input);
    let position = 0;

    function peek() {
      return tokens[position];
    }

    function take(type) {
      if (peek()?.type !== type) return null;
      return tokens[position++];
    }

    function startsCondition(token) {
      return token && ["TERM", "LPAREN", "NOT", "CONTAINS"].includes(token.type);
    }

    function parseExpression() {
      const node = parseOr();
      if (position < tokens.length) {
        const token = peek();
        if (token.type === "RPAREN") throw new Error("右括号多余");
        throw new Error(`无法识别 "${token.raw}" 附近的规则`);
      }
      return node;
    }

    function parseOr() {
      let node = parseAnd();
      while (take("OR")) {
        if (!startsCondition(peek())) throw new Error("OR 后面缺少条件");
        node = { type: "or", left: node, right: parseAnd() };
      }
      return node;
    }

    function parseAnd() {
      let node = parseNot();
      while (true) {
        if (take("AND")) {
          if (!startsCondition(peek())) throw new Error("AND 后面缺少条件");
          node = { type: "and", left: node, right: parseNot() };
          continue;
        }
        if (startsCondition(peek())) {
          node = { type: "and", left: node, right: parseNot() };
          continue;
        }
        return node;
      }
    }

    function parseNot() {
      if (take("NOT")) {
        if (!startsCondition(peek())) throw new Error("NOT 后面缺少条件");
        return { type: "not", child: parseNot() };
      }
      return parsePrimary();
    }

    function parsePrimary() {
      if (take("CONTAINS")) {
        if (!startsCondition(peek())) throw new Error("包含 后面缺少关键词");
        return parsePrimary();
      }
      const term = take("TERM");
      if (term) return { type: "term", value: term.value };
      if (take("LPAREN")) {
        if (take("RPAREN")) throw new Error("括号内不能是空条件");
        const node = parseOr();
        if (!take("RPAREN")) throw new Error("缺少右括号");
        return node;
      }
      const token = peek();
      if (!token) throw new Error("缺少条件");
      if (token.type === "AND" || token.type === "OR") throw new Error(`${token.raw} 前面缺少条件`);
      if (token.type === "RPAREN") throw new Error("右括号前面缺少条件");
      throw new Error(`无法识别 "${token.raw}"`);
    }

    if (!tokens.length) return null;
    return parseExpression();
  }

  function matchNode(node, haystack) {
    if (!node) return true;
    if (node.type === "term") return haystack.includes(normalizeText(node.value));
    if (node.type === "not") return !matchNode(node.child, haystack);
    if (node.type === "and") return matchNode(node.left, haystack) && matchNode(node.right, haystack);
    if (node.type === "or") return matchNode(node.left, haystack) || matchNode(node.right, haystack);
    return false;
  }

  function needsQuote(value) {
    const normalized = normalizeText(value);
    return /\s|\(|\)/.test(value) || Boolean(OPERATORS[normalized] || OPERATORS[value]);
  }

  function formatTerm(value) {
    if (!needsQuote(value)) return value;
    return `"${String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"`;
  }

  function precedence(node) {
    if (!node) return 4;
    if (node.type === "or") return 1;
    if (node.type === "and") return 2;
    if (node.type === "not") return 3;
    return 4;
  }

  function formatNode(node, parentPrecedence = 0) {
    if (!node) return "";
    const current = precedence(node);
    let text;
    if (node.type === "term") {
      text = formatTerm(node.value);
    } else if (node.type === "not") {
      text = `NOT ${formatNode(node.child, current)}`;
    } else {
      const op = node.type === "and" ? "AND" : "OR";
      text = `${formatNode(node.left, current)} ${op} ${formatNode(node.right, current)}`;
    }
    return current < parentPrecedence ? `(${text})` : text;
  }

  function compile(input) {
    const ast = parse(input);
    const expression = formatNode(ast);
    return {
      ast,
      expression,
      matchText(text) {
        return matchNode(ast, normalizeText(text));
      },
    };
  }

  const api = { compile, parse, tokenize, formatNode, normalizeText };
  global.VolunteerQuery = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
