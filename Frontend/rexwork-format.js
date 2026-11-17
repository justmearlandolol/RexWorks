(function (global) {
  'use strict';

  /* ---------------------------------------------------------------- utils */

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var FENCE = /^(\s*)(`{3,}|~{3,})\s*([\w+.#\/-]*)\s*$/;
  var FENCE_ANY = /^(\s*)(`{3,}|~{3,})\s*([\w+.#\/-]*)\s*(.*)$/;
  var HEADING = /^(\s*)(#{1,6})\s*(.*?)\s*#*\s*$/;
  var HASHTAG_GLUED = /^(\s*)(#{1,6})([^\s#].*)$/;
  var SETEXT_H1 = /^(\s*)=+\s*$/;
  var SETEXT_H2 = /^(\s*)-{2,}\s*$/;
  var LIST_ITEM = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
  var LIST_TIGHT = /^(\s*)(\d{1,9})\)([^\s\d].*)$/;
  var TASK_ITEM = /^\[([ xX])\]\s+(.*)$/;
  var HR = /^\s*([-*_])(?:\s*\1){2,}\s*$/;
  var QUOTE = /^(\s*)>\s?(.*)$/;
  var TABLE_ROW = /^\s*\|.*\|\s*$/;
  var TABLE_LOOSE = /^\s*[^|\n]+\|[^|\n]+\|[^|\n]*$/;
  var BOLD_LEAD = /^(\*\*[^*\n]{1,48}\*\*)(?=[A-Za-z0-9("'\u201c])/;
  var CELL_BULLET = /(^|[\s.;:,)])([-*+])\s+/;
  var INLINE_CODE = /(`+)([^`\n]+?)\1/g;
  var BULLET = '\u2022';
  var PH_OPEN = '\uE000';
  var PH_CLOSE = '\uE001';
  var PH_RE = new RegExp(PH_OPEN + '(\\d+)' + PH_CLOSE, 'g');

  var LANG = {
    js: 'javascript', javascript: 'javascript', ts: 'typescript', tsx: 'tsx',
    py: 'python', python: 'python', python3: 'python', sh: 'bash', shell: 'bash',
    bash: 'bash', zsh: 'bash', console: 'bash', terminal: 'bash', yml: 'yaml',
    yaml: 'yaml', md: 'markdown', markdown: 'markdown', html: 'html', htm: 'html',
    txt: 'text', plain: 'text', plaintext: 'text', '': 'text'
  };

  function langLabel(raw) {
    var key = String(raw || '').trim().toLowerCase().replace(/^\./, '');
    return LANG[key] || key || 'text';
  }

  /* ------------------------------------------------------- table helpers */

  function splitRow(line) {
    var body = String(line).trim();
    if (body.charAt(0) === '|') body = body.slice(1);
    if (body.slice(-1) === '|' && body.slice(-2) !== '\\|') body = body.slice(0, -1);

    var cells = [];
    var buffer = '';
    var inCode = false;
    var escaped = false;

    for (var i = 0; i < body.length; i += 1) {
      var ch = body.charAt(i);
      if (escaped) { buffer += ch; escaped = false; }
      else if (ch === '\\') { buffer += ch; escaped = true; }
      else if (ch === '`') { inCode = !inCode; buffer += ch; }
      else if (ch === '|' && !inCode) { cells.push(buffer.trim()); buffer = ''; }
      else { buffer += ch; }
    }

    cells.push(buffer.trim());
    return cells;
  }

  function isSeparator(line) {
    var stripped = String(line || '').trim();
    if (stripped.indexOf('-') === -1) return false;
    return /^[\s:|-]+$/.test(stripped) && stripped.indexOf('|') !== -1;
  }

  function alignmentOf(cell) {
    var text = String(cell || '').trim();
    var left = text.charAt(0) === ':';
    var right = text.slice(-1) === ':';
    if (left && right) return 'center';
    if (right) return 'right';
    if (left) return 'left';
    return 'default';
  }

  function normalizeCell(cell) {
    var text = String(cell || '').replace(/\\\|/g, '|').replace(/\s*\n\s*/g, ' ');
    text = text.replace(/^\s*[-*+]\s+/, '');
    if (text.trim().length > 1) text = text.replace(/\s+[-*+]\s*$/, '');
    text = text.replace(CELL_BULLET, function (m, before) { return before + BULLET + ' '; });
    return text.replace(/\s{2,}/g, ' ').trim();
  }

  function padTable(rows, align) {
    if (!rows.length) return [];
    var cols = Math.min(Math.max.apply(null, rows.map(function (r) { return r.length; })), 24);
    if (!cols) return [];

    var grid = rows.map(function (row) {
      var out = [];
      for (var c = 0; c < cols; c += 1) out.push(row[c] == null ? '' : row[c]);
      return out;
    });

    var widths = [];
    for (var c = 0; c < cols; c += 1) {
      widths.push(3);
      grid.forEach(function (row) {
        widths[c] = Math.max(widths[c], row[c].length);
      });
    }

    function render(row) {
      var cells = [];
      for (var i = 0; i < cols; i += 1) {
        cells.push(row[i] + new Array(Math.max(0, widths[i] - row[i].length) + 1).join(' '));
      }
      return '| ' + cells.join(' | ') + ' |';
    }

    var rules = align || [];
    var separator = [];
    for (var i = 0; i < cols; i += 1) {
      var rule = rules[i] || 'default';
      var width = widths[i];
      if (rule === 'center') separator.push(':' + new Array(Math.max(1, width - 2) + 1).join('-') + ':');
      else if (rule === 'right') separator.push(new Array(Math.max(1, width - 1) + 1).join('-') + ':');
      else if (rule === 'left') separator.push(':' + new Array(Math.max(1, width - 1) + 1).join('-'));
      else separator.push(new Array(width + 1).join('-'));
    }

    var out = [render(grid[0]), '| ' + separator.join(' | ') + ' |'];
    for (var r = 1; r < grid.length; r += 1) out.push(render(grid[r]));
    return out;
  }

  function gluedTableCut(line, wanted) {
    var fallback = -1;
    var limit = Math.min(line.length, 600);
    var breaks = ' :;!?)\u2014,.';

    for (var i = 1; i < limit; i += 1) {
      var prose = line.slice(0, i).trim();
      var segment = line.slice(i).trim();
      if (!prose || !segment) continue;
      if (splitRow(segment).length !== wanted) continue;
      if (segment.charAt(0) === '|') return i;
      if (breaks.indexOf(line.charAt(i - 1)) !== -1) fallback = i;
    }
    return fallback;
  }

  function splitGluedTables(lines) {
    var out = [];
    var inFence = false;

    for (var i = 0; i < lines.length; i += 1) {
      var line = lines[i];

      if (FENCE.test(line)) { inFence = !inFence; out.push(line); continue; }
      if (inFence || !line.trim() || line.replace(/^\s+/, '').charAt(0) === '|') {
        out.push(line);
        continue;
      }

      var next = i + 1 < lines.length ? lines[i + 1] : '';
      if (line.indexOf('|') !== -1 && isSeparator(next)) {
        var cut = gluedTableCut(line, splitRow(next).length);
        if (cut > 0) {
          var prose = line.slice(0, cut).trim();
          var row = line.slice(cut).trim();
          if (prose && row.indexOf('|') !== -1) {
            out.push(prose, '', row);
            continue;
          }
        }
      }
      out.push(line);
    }
    return out;
  }

  function promoteTables(lines) {
    var out = [];
    var inFence = false;
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      if (FENCE.test(line)) { inFence = !inFence; out.push(line); i += 1; continue; }

      var nextIsSeparator = i + 1 < lines.length && isSeparator(lines[i + 1]);
      var pipey = TABLE_ROW.test(line) || TABLE_LOOSE.test(line) || (nextIsSeparator && line.indexOf('|') !== -1);

      if (inFence || !pipey || ((line.split('|').length - 1) < 2 && !nextIsSeparator)) {
        out.push(line);
        i += 1;
        continue;
      }

      var block = [];
      var sawSeparator = false;

      while (i < lines.length) {
        var candidate = lines[i];
        if (FENCE.test(candidate) || !candidate.trim()) break;

        var upcoming = i + 1 < lines.length && isSeparator(lines[i + 1]);
        var accept = TABLE_ROW.test(candidate) || TABLE_LOOSE.test(candidate) || isSeparator(candidate);
        if (!accept) accept = (sawSeparator || upcoming) && (candidate.split('|').length - 1) >= 1;
        if (!accept) break;

        if (isSeparator(candidate)) sawSeparator = true;
        block.push(candidate);
        i += 1;
      }

      var rows = [];
      var align = [];

      block.forEach(function (row) {
        if (isSeparator(row)) {
          align = splitRow(row).map(alignmentOf);
          return;
        }
        var cells = splitRow(row).map(function (cell) { return normalizeCell(cell); });
        if (cells.join('').trim()) rows.push(cells);
      });

      if (!rows.length) { out.push.apply(out, block); continue; }
      out.push.apply(out, padTable(rows, align));
    }

    return out;
  }

  /* ------------------------------------------------------- block repair */

  var FENCE_HEAD = /^(\s*)(`{3,}|~{3,})(.*)$/;
  var FENCE_LANG = /^([A-Za-z][\w+.#-]{0,19})/;
  var COMMENT_START = /^(?:\/\/|#|--|;|<!--)/;
  var CODE_CHARS = /[{;=()\[\]]|::|->|=>/;
  var CODE_HINT_JS = /^\s*(?:def \w+\(|class \w+|import \w|from \w+ import |#include|public (?:class|void|static)|function \w+\(|const \w+\s*=|let \w+\s*=|var \w+\s*=|using \w|namespace \w|SELECT .+ FROM|\$ |sudo |npm |pnpm |yarn |pip |git |docker |curl |echo |cd |mkdir |ls )/;
  var PROSE_HEADING = /^\s*#{2,6}\s+\S/;
  var PROSE_BOLD = /^\s*\*\*[^*]+\*\*/;

  function parseFenceLine(line) {
    var match = FENCE_HEAD.exec(line);
    if (!match) return null;

    var tail = (match[3] || '').trim();
    var lang = '';
    var rest = '';

    if (tail) {
      var token = FENCE_LANG.exec(tail);
      if (token) {
        lang = token[1];
        rest = tail.slice(token[0].length).trim();
      } else {
        rest = tail;
      }
    }

    return { indent: match[1], markup: match[2], lang: lang, rest: rest };
  }

  function looksLikeCode(lines) {
    return lines.some(function (line) {
      return CODE_CHARS.test(line) || CODE_HINT_JS.test(line);
    });
  }

  function proseBoundary(lines, body, index) {
    if (!body.some(function (line) { return line.trim(); })) return false;
    if (index > 0 && lines[index - 1].trim()) return false;

    var line = lines[index];
    if (!(PROSE_HEADING.test(line) || PROSE_BOLD.test(line))) return false;

    return !looksLikeCode([line]);
  }

  function normalizeFences(lines) {
    var out = [];
    var index = 0;

    while (index < lines.length) {
      var parsed = parseFenceLine(lines[index]);

      if (!parsed) { out.push(lines[index]); index += 1; continue; }

      var markup = parsed.markup;
      var body = [];
      var cursor = index + 1;
      var closedHere = false;

      while (cursor < lines.length) {
        var candidate = parseFenceLine(lines[cursor]);

        if (candidate && candidate.markup.charAt(0) === markup.charAt(0) &&
            candidate.markup.length >= markup.length) {
          // A marker with an info string starts a new fence, it does not close this one.
          closedHere = !(candidate.lang === '' && candidate.rest === '');
          break;
        }

        if (proseBoundary(lines, body, cursor)) { closedHere = true; break; }

        body.push(lines[cursor]);
        cursor += 1;
      }

      var trailing = parsed.rest;

      if (trailing && (COMMENT_START.test(trailing) || CODE_CHARS.test(trailing) || CODE_HINT_JS.test(trailing))) {
        body.unshift(trailing);
      }

      var pureMarker = parsed.lang === '' && parsed.rest === '';
      if (pureMarker && !looksLikeCode(body)) {
        var hasBlank = body.some(function (line) { return !line.trim(); });
        if (hasBlank || !body.length) {
          Array.prototype.push.apply(out, body);
          index = cursor;
          continue;
        }
      }

      while (body.length && !body[body.length - 1].trim()) body.pop();

      out.push(markup + langLabel(parsed.lang));
      Array.prototype.push.apply(out, body);
      out.push(markup);

      index = closedHere ? cursor : (cursor > index ? cursor : index + 1);
    }

    return out;
  }

  function normalizeHeadings(lines) {
    var stage = [];
    var inFence = false;

    lines.forEach(function (line) {
      if (FENCE.test(line)) { inFence = !inFence; stage.push(line); return; }
      if (inFence) { stage.push(line); return; }

      var glued = HASHTAG_GLUED.exec(line);
      if (glued) { stage.push(glued[1] + glued[2] + ' ' + glued[3].trim()); return; }

      var heading = HEADING.exec(line);
      if (heading && heading[3].trim()) { stage.push(heading[2] + ' ' + heading[3].trim()); return; }

      stage.push(line);
    });

    var out = [];
    inFence = false;

    for (var i = 0; i < stage.length; i += 1) {
      var line = stage[i];
      if (FENCE.test(line)) inFence = !inFence;

      if (!inFence && i + 1 < stage.length && line.trim()) {
        var text = line.trim();
        var isList = LIST_ITEM.test(line) || text.charAt(0) === '|';
        if (!isList) {
          if (SETEXT_H1.test(stage[i + 1])) { out.push('# ' + text); i += 1; continue; }
          if (SETEXT_H2.test(stage[i + 1]) && text.length < 90) { out.push('## ' + text); i += 1; continue; }
        }
      }

      out.push(line);
    }

    return out;
  }

  function looksLikeLead(plain, rest) {
    if (!plain) return false;
    if (/[:;.,]$/.test(plain) && plain.length <= 60) return false;
    var letters = plain.replace(/[^A-Za-z\u00C0-\u024F]/g, '');
    if (!letters.length) return false;
    var upper = letters.replace(/[^A-Z\u00C0-\u00DE]/g, '').length;
    if (plain.length > 24 || upper / letters.length >= 0.7) return rest.length >= 20;
    return false;
  }

  function splitGluedLeads(lines) {
    var out = [];
    var inFence = false;

    lines.forEach(function (line) {
      if (FENCE.test(line)) { inFence = !inFence; out.push(line); return; }
      if (inFence || !line.trim()) { out.push(line); return; }

      var match = BOLD_LEAD.exec(line);
      if (!match) { out.push(line); return; }

      var lead = match[1];
      var rest = line.slice(lead.length).trim();
      var plain = lead.replace(/\*/g, '').trim();

      if (!rest || !looksLikeLead(plain, rest)) { out.push(lead + (rest ? ' ' + rest : '')); return; }

      out.push(lead, '', rest);
    });

    return out;
  }

  function normalizeLists(lines) {
    var out = [];
    var stack = [];
    var inFence = false;
    var blank = false;

    lines.forEach(function (line) {
      if (FENCE.test(line)) { inFence = !inFence; out.push(line); return; }
      if (inFence) { out.push(line); return; }

      var match = LIST_ITEM.exec(line);
      var marker;
      var content;
      var width;

      if (!match) {
        var tight = LIST_TIGHT.exec(line);
        if (!tight) {
          if (line.trim()) { stack = []; blank = false; } else { blank = true; }
          out.push(line);
          return;
        }
        width = tight[1].replace(/\t/g, '    ').length;
        marker = tight[2] + '.';
        content = tight[3].trim();
      } else {
        width = match[1].replace(/\t/g, '    ').length;
        marker = match[2];
        content = match[3];
        marker = (marker === '-' || marker === '*' || marker === '+') ? '-' : marker.slice(0, -1) + '.';
      }

      if (blank) stack = [];
      blank = false;

      if (width === 0) stack = [0];
      else {
        while (stack.length && width < stack[stack.length - 1]) stack.pop();
        if (!stack.length || width > stack[stack.length - 1]) stack.push(width);
      }

      var indent = new Array(Math.max(0, stack.length - 1) + 1).join('  ');
      var task = TASK_ITEM.exec(content);
      if (task) {
        out.push(indent + '- [' + (task[1].toLowerCase() === 'x' ? 'x' : ' ') + '] ' + task[2].trim());
      } else {
        out.push(indent + marker + ' ' + content.trim());
      }
    });

    return out;
  }

  function blockKind(line) {
    if (FENCE.test(line)) return 'fence';
    if (TABLE_ROW.test(line)) return 'table';
    if (HEADING.test(line)) return 'heading';
    if (HR.test(line)) return 'hr';
    if (QUOTE.test(line)) return 'quote';
    if (LIST_ITEM.test(line)) return 'list';
    if (!line.trim()) return 'blank';
    return 'prose';
  }

  var GAP = {
    heading: ['prose', 'list', 'table', 'quote', 'fence', 'hr'],
    hr: ['prose', 'list', 'table', 'quote', 'fence'],
    quote: ['prose', 'list', 'heading', 'table'],
    list: ['prose', 'heading', 'table', 'quote', 'fence'],
    table: ['prose', 'heading', 'list', 'quote', 'fence'],
    fence: ['prose', 'list', 'table', 'heading', 'quote'],
    prose: ['table', 'fence']
  };

  function splitGluedBlocks(lines) {
    var out = [];
    var inFence = false;

    lines.forEach(function (line) {
      var kind = blockKind(line);

      if (inFence) {
        out.push(line);
        if (kind === 'fence') inFence = false;
        return;
      }

      if (kind === 'fence') {
        inFence = true;
        if (out.length && GAP.fence.indexOf(blockKind(out[out.length - 1])) !== -1) out.push('');
        out.push(line);
        return;
      }

      if (kind !== 'blank' && out.length && out[out.length - 1].trim()) {
        var previous = blockKind(out[out.length - 1]);
        var wants = (GAP[kind] || []).indexOf(previous) !== -1 || (previous === 'table' && kind === 'prose');
        if (wants && previous !== kind) out.push('');
      }

      out.push(line);
    });

    return out;
  }

  function collapseBlanks(lines) {
    var out = [];
    var inFence = false;
    var blanks = 0;

    lines.forEach(function (line) {
      if (FENCE.test(line)) inFence = !inFence;

      if (!line.trim() && !inFence) {
        blanks += 1;
        if (blanks > 1) return;
        out.push('');
        return;
      }

      blanks = 0;
      out.push(line.replace(/[ \t]+$/, ''));
    });

    while (out.length && !out[out.length - 1].trim()) out.pop();
    while (out.length && !out[0].trim()) out.shift();

    return out;
  }

  /* ------------------------------------------------------- inline repair */

  function protectCode(text) {
    var spans = [];
    var stashed = text.replace(INLINE_CODE, function (match) {
      spans.push(match);
      return PH_OPEN + (spans.length - 1) + PH_CLOSE;
    });
    return { text: stashed, spans: spans };
  }

  function restoreCode(text, spans) {
    return text.replace(PH_RE, function (match, index) {
      var span = spans[Number(index)];
      return span == null ? match : span;
    });
  }

  function balanceBold(text) {
    var count = (text.match(/\*\*/g) || []).length;
    if (count % 2 === 0) return text;

    var open = -1;
    var i = 0;
    while (i < text.length) {
      if (text.slice(i, i + 2) === '**') { open = open === -1 ? i : -1; i += 2; continue; }
      i += 1;
    }

    if (open === -1) return text;

    var tail = text.slice(open + 2).replace(/\*/g, '').trim();
    if (!tail) return text.slice(0, open).replace(/\s+$/, '');
    return text.slice(0, open) + '**' + tail + '**';
  }

  function fixInline(text) {
    if (!text) return text;

    var stashed = protectCode(text);
    var working = balanceBold(stashed.text);

    working = working.replace(/\*\*[ \t]+([^\n*]+?)[ \t]+\*\*/g, '**$1**');
    working = working.replace(/(^|[^\w*])\*[ \t]+([^\n*]+?)[ \t]+\*(?![\w*])/g, '$1*$2*');
    working = working.replace(/(^|[^\w_])_[ \t]+([^\n_]+?)[ \t]+_(?![\w_])/g, '$1_$2_');
    working = working.replace(/\*\*\*\*/g, '');
    // `Hey Justin!Here's ...` -> insert the missing space after the sentence.
    working = working.replace(/([a-z0-9!)\]\u201d])([A-Z][a-z])/g, '$1 $2');
    working = working.replace(/[ \t]{2,}/g, ' ').replace(/^\s+|\s+$/g, '');

    return restoreCode(working, stashed.spans);
  }

  function repairInlineLines(lines) {
    var out = [];
    var inFence = false;

    lines.forEach(function (line) {
      if (FENCE.test(line)) { out.push(line); inFence = !inFence; return; }
      if (inFence || !line.trim() || line.replace(/^\s+/, '').charAt(0) === '|') { out.push(line); return; }
      if (HR.test(line)) { out.push(line); return; }

      var prefix = '';
      var body = line;
      var quote = QUOTE.exec(line);
      if (quote) { prefix = quote[1] + '> '; body = quote[2]; }

      var item = LIST_ITEM.exec(body);
      if (item) { prefix = prefix + item[1] + item[2] + ' '; body = item[3]; }

      var fixed = fixInline(body);
      out.push(fixed ? prefix + fixed : prefix.replace(/\s+$/, ''));
    });

    return out;
  }

  /* ------------------------------------------------------------- public */

  function markdown(src) {
    if (src == null || !String(src).trim()) return '';

    var source = String(src).slice(0, 200000);
    source = source.replace(/\r\n?/g, '\n').replace(/\u00a0/g, ' ').replace(/\u202f/g, ' ').replace(/\t/g, '    ');

    var lines = source.split('\n').map(function (line) { return line.replace(/[ \t]+$/, ''); });

    lines = normalizeFences(lines);
    lines = splitGluedTables(lines);
    lines = promoteTables(lines);
    lines = normalizeHeadings(lines);
    lines = splitGluedLeads(lines);
    lines = normalizeLists(lines);
    lines = splitGluedBlocks(lines);
    lines = collapseBlanks(lines);
    lines = repairInlineLines(lines);

    return lines.join('\n').replace(/[ \t]+$/gm, '').trim() + '\n';
  }

  function render(src) {
    var fixed = markdown(src);
    if (typeof global.renderMarkdown === 'function') return global.renderMarkdown(fixed);
    return '<p>' + esc(fixed) + '</p>';
  }

  function plain(src) {
    /* Speech-friendly text: tables lose their pipes, code is skipped. */
    var out = [];

    markdown(src).split('\n').forEach(function (line) {
      if (FENCE.test(line)) return;
      if (isSeparator(line)) return;
      if (TABLE_ROW.test(line)) {
        var cells = splitRow(line).filter(function (cell) { return cell.trim(); });
        if (cells.length) out.push(cells.join(', ') + '.');
        return;
      }
      out.push(line);
    });

    return out.join(' ')
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/[#*`>_~]+/g, ' ')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }

  /* Split Markdown into reveal "blocks": a table stays one block (so it can
   * never be painted half-built), a fence stays one block, prose is per line. */
  function blocks(src) {
    var out = [];
    var inFence = false;
    var table = [];

    function flushTable() {
      if (table.length) { out.push(table.join('\n')); table = []; }
    }

    markdown(src).split('\n').forEach(function (raw) {
      var line = raw.trim();

      if (FENCE.test(line)) {
        if (!inFence) { flushTable(); out.push(line); inFence = true; }
        else { out[out.length - 1] += '\n' + line; inFence = false; }
        return;
      }

      if (inFence) { out[out.length - 1] += '\n' + raw; return; }

      if (TABLE_ROW.test(line)) { table.push(line); return; }

      flushTable();
      if (line) out.push(line);
    });

    flushTable();
    return out;
  }

  global.RexFormat = {
    markdown: markdown,
    render: render,
    plain: plain,
    blocks: blocks,
    fixInline: fixInline,
    esc: esc
  };

  /* ------------------------------------------------------------- reveal */

  var SETTINGS_KEY = 'rexwork_reveal';

  var DEFAULT_SETTINGS = {
    enabled: true,
    pace: 'slow',   // 'slow' | 'normal' | 'instant'
    sound: true     // soft tick while text lands (0.012 volume, no assets)
  };

  var PACES = {
    slow:    { word: 46,  block: 210, char: 2.3 },
    normal:  { word: 26,  block: 130, char: 1.6 },
    instant: { word: 0,   block: 0,   char: 0 }
  };

  function prefersReducedMotion() {
    return typeof global.matchMedia === 'function' &&
      global.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  var toned = null; // tiny WebAudio tick so reveal feels "alive"
  var audioUnlocked = false;

  function unlockAudio() {
    audioUnlocked = true;
    try {
      var Ctx = global.AudioContext || global.webkitAudioContext;
      if (!Ctx) return;
      toned = toned || new Ctx();
      if (toned.state === 'suspended') toned.resume();
    } catch (error) { /* ignored */ }
  }

  if (typeof global.addEventListener === 'function') {
    global.addEventListener('pointerdown', unlockAudio, { once: true, passive: true });
    global.addEventListener('keydown', unlockAudio, { once: true });
  }

  function tick(volume) {
    if (!RexReveal.settings.sound || volume <= 0 || !audioUnlocked) return;
    try {
      var Ctx = global.AudioContext || global.webkitAudioContext;
      if (!Ctx) return;
      toned = toned || new Ctx();
      if (!toned || toned.state !== 'running') return;
      var osc = toned.createOscillator();
      var gain = toned.createGain();
      osc.type = 'square';
      osc.frequency.value = 620 + Math.random() * 120;
      gain.gain.setValueAtTime(volume, toned.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, toned.currentTime + 0.05);
      osc.connect(gain); gain.connect(toned.destination);
      osc.start(); osc.stop(toned.currentTime + 0.055);
    } catch (error) { /* audio is a nice-to-have */ }
  }

  var RexReveal = {
    settings: Object.assign({}, DEFAULT_SETTINGS),
    reducedMotion: false,

    loadSettings: function () {
      try {
        var raw = global.localStorage.getItem(SETTINGS_KEY);
        if (raw) Object.assign(RexReveal.settings, JSON.parse(raw) || {});
      } catch (error) { /* ignored */ }
      RexReveal.reducedMotion = prefersReducedMotion();
      return RexReveal.settings;
    },

    saveSettings: function () {
      try { global.localStorage.setItem(SETTINGS_KEY, JSON.stringify(RexReveal.settings)); } catch (error) { /* ignored */ }
    },

    /* Start revealing `text` inside `host`. Returns a controller:
     *   controller.finish()  -> show everything now
     *   controller.pause()   -> hold
     *   controller.resume()  -> continue
     *   controller.stop()    -> abort (no onDone)
     *   controller.done      -> boolean
     */
    start: function (options) {
      var opts = options || {};
      var host = opts.host;
      if (!host) throw new Error('RexReveal.start requires { host }');

      var onTick = typeof opts.onTick === 'function' ? opts.onTick : function () {};
      var onDone = typeof opts.onDone === 'function' ? opts.onDone : function () {};
      var fullText = String(opts.text || '');
      var pace = PACES[RexReveal.settings.pace] || PACES.slow;
      var animated = RexReveal.settings.enabled && opts.animate !== false &&
        !prefersReducedMotion() && pace.word > 0;

      var queue = blocks(fullText);
      var state = { finished: false, cancelled: false, paused: false, timer: null };
      var index = 0;
      var shown = [];
      var animatedUpto = -1;   // block index that already played its entrance

      function caretNode() {
        return host.querySelector('.rx-caret');
      }

      function ensureCaret() {
        var caret = caretNode();
        if (!caret) {
          caret = document.createElement('span');
          caret.className = 'rx-caret';
          caret.setAttribute('aria-hidden', 'true');
        }
        return caret;
      }

      /* Count the top-level elements a block renders into, so the entrance
       * animation is applied to that block only - never replayed on the blocks
       * that are already on screen (that used to make the whole answer blink). */
      function elementCount(blockText) {
        var probe = document.createElement('div');
        probe.innerHTML = RexFormat.render(blockText);
        return Math.max(1, probe.childElementCount || 1);
      }

      function paint(partial, freshBlocks) {
        host.innerHTML = RexFormat.render(partial);

        var kids = host.children;
        var fresh = freshBlocks == null ? 0 : freshBlocks;

        for (var k = 0; k < kids.length; k += 1) {
          if (k < kids.length - fresh) kids[k].style.animation = 'none';
        }

        var last = kids[kids.length - 1];
        if (last) last.appendChild(ensureCaret());
      }

      if (!animated) {
        host.innerHTML = RexFormat.render(fullText);
        host.classList.add('rx-reveal-done');
        state.finished = true;
        onTick(fullText, { done: true });
        setTimeout(onDone, 0);
        return {
          finish: function () {}, pause: function () {}, resume: function () {}, stop: function () {},
          get done() { return true; }
        };
      }

      host.classList.add('rx-reveal');
      host.classList.remove('rx-reveal-done');
      paint('', 0);

      function finishNow() {
        if (state.finished || state.cancelled) return;
        state.finished = true;
        if (state.timer) clearTimeout(state.timer);
        host.innerHTML = RexFormat.render(fullText);
        host.classList.add('rx-reveal-done');
        var caret = caretNode();
        if (caret) caret.remove();
        onTick(fullText, { done: true });
        onDone();
      }

      function step() {
        if (state.cancelled) return;
        if (state.paused) { state.timer = setTimeout(step, 120); return; }
        if (index >= queue.length) { finishNow(); return; }

        var block = queue[index];
        var words = block.split(/\s+/);
        var target = words.length;
        var cursor = 0;
        var isCode = FENCE.test(block);
        var lineCount = block.split('\n').length;
        var isDense = isCode || TABLE_ROW.test(block) || lineCount > 1;
        var fresh = elementCount(block);

        shown.push(block);
        var blockIndex = index;
        var firstPaint = true;

        function typeWord() {
          if (state.cancelled) return;
          if (state.paused) { state.timer = setTimeout(typeWord, 120); return; }

          cursor += 1;
          var partialBlock = words.slice(0, cursor).join(' ');
          var preview = shown.slice(0, -1).concat([partialBlock]).join('\n');

          var animate = firstPaint && blockIndex > animatedUpto ? fresh : 0;
          if (animate) animatedUpto = blockIndex;
          firstPaint = false;

          paint(preview, animate);
          onTick(preview, { typing: true });

          if (cursor < target) {
            var speed = isDense ? pace.char : pace.word;
            var jitter = speed * (0.75 + Math.random() * 0.6);
            tick(0.008 + Math.random() * 0.006);
            state.timer = setTimeout(typeWord, jitter);
            return;
          }

          index += 1;
          state.timer = setTimeout(step, pace.block * (isDense ? 0.4 : 1));
        }

        typeWord();
      }

      step();

      return {
        finish: finishNow,
        pause: function () { state.paused = true; },
        resume: function () { state.paused = false; },
        stop: function () {
          state.cancelled = true;
          if (state.timer) clearTimeout(state.timer);
        },
        get done() { return state.finished; }
      };
    }
  };

  RexReveal.loadSettings();
  global.RexReveal = RexReveal;
})(typeof window !== 'undefined' ? window : this);
