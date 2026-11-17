(function (global) {
  'use strict';

  var MAX_HIGHLIGHT_CHARS = 120000;


  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var EXT_LANG = {
    js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'jsx',
    ts: 'typescript', tsx: 'tsx', py: 'python', rb: 'ruby', go: 'go',
    rs: 'rust', java: 'java', kt: 'kotlin', c: 'c', h: 'c', cpp: 'cpp',
    hpp: 'cpp', cs: 'csharp', php: 'php', swift: 'swift',
    json: 'json', jsonc: 'json', yml: 'yaml', yaml: 'yaml', toml: 'toml',
    md: 'markdown', markdown: 'markdown', txt: 'text',
    html: 'html', htm: 'html', vue: 'html', svg: 'xml', xml: 'xml',
    css: 'css', scss: 'css', less: 'css',
    sh: 'bash', bash: 'bash', zsh: 'bash', env: 'bash', ini: 'ini',
    sql: 'sql', csv: 'text', wav: 'text', mp3: 'text', png: 'text', jpg: 'text'
  };

  function langFromName(name) {
    var parts = String(name || '').split('.');
    if (parts.length < 2) return 'text';
    return EXT_LANG[parts.pop().toLowerCase()] || 'text';
  }

  function extOf(name) {
    var parts = String(name || '').split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  var LANG_LABEL = {
    javascript: 'JavaScript', typescript: 'TypeScript', jsx: 'JSX', tsx: 'TSX',
    python: 'Python', json: 'JSON', yaml: 'YAML', markdown: 'Markdown',
    html: 'HTML', xml: 'XML', css: 'CSS', bash: 'Shell', sql: 'SQL',
    go: 'Go', rust: 'Rust', ruby: 'Ruby', java: 'Java', kotlin: 'Kotlin',
    c: 'C', cpp: 'C++', csharp: 'C#', php: 'PHP', swift: 'Swift',
    ini: 'INI', toml: 'TOML', text: 'Text'
  };

  function langLabel(lang) {
    return LANG_LABEL[lang] || (lang ? lang.toUpperCase() : 'TEXT');
  }

  function fmtBytes(value) {
    var n = Number(value) || 0;
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
    return (n / (1024 * 1024)).toFixed(2) + ' MB';
  }

  function byteLength(text) {
    try { return new TextEncoder().encode(text).length; }
    catch (error) { return String(text).length; }
  }

  function icon(name) {
    var ext = extOf(name);
    var palette = {
      js: '#f0d97a', mjs: '#f0d97a', cjs: '#f0d97a', jsx: '#f0d97a',
      ts: '#7fb3ff', tsx: '#7fb3ff',
      py: '#7ec9e8', json: '#ffb000', md: '#c3ccdb', html: '#ff8f6b',
      css: '#9c8cf5', sh: '#8ce8a5', yml: '#e49cf0', yaml: '#e49cf0',
      wav: '#66d48a', mp3: '#66d48a', png: '#f06292', jpg: '#f06292'
    };
    var color = palette[ext] || '#8791a5';
    return '<svg class="rx-file-ico" viewBox="0 0 16 16" aria-hidden="true">'
      + '<path d="M3.5 1.5h6L13 5v9.5H3.5z" fill="none" stroke="' + color + '" stroke-width="1.2" stroke-linejoin="round"/>'
      + '<path d="M9.5 1.5V5H13" fill="none" stroke="' + color + '" stroke-width="1.2" stroke-linejoin="round"/>'
      + '<circle cx="5.6" cy="9" r="1" fill="' + color + '"/>'
      + '<path d="M7.4 9h3" stroke="' + color + '" stroke-width="1.2" stroke-linecap="round"/>'
      + '<path d="M5.6 11.6h4.8" stroke="' + color + '" stroke-width="1.2" stroke-linecap="round"/>'
      + '</svg>';
  }

  /* --------------------------------------------------- syntax highlight */

  var KEYWORDS = {
    javascript: 'break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield async await true false null undefined',
    typescript: 'break case catch class const continue declare default delete do else enum export extends finally for from function if implements import in instanceof interface let namespace new of private protected public readonly return static super switch this throw try type typeof var void while yield async await true false null undefined',
    jsx: 'const let var function return if else import from export default class extends new true false null undefined async await',
    tsx: 'const let var function return if else import from export default class extends interface type true false null undefined async await',
    python: 'and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield self print len range str int float list dict set tuple open',
    go: 'break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var nil true false',
    rust: 'as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while',
    ruby: 'alias and begin break case class def defined do else elsif end ensure false for if in module next nil not or redo rescue retry return self super then true undef unless until when while yield',
    java: 'abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null var',
    kotlin: 'as break class continue do else false for fun if in interface is null object package return super this throw true try typealias val var when while',
    c: 'auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while',
    cpp: 'auto bool break case catch char class const constexpr continue default delete do double else enum explicit extern false float for friend goto if inline int long namespace new nullptr operator private protected public return short signed sizeof static struct switch template this throw true try typedef typename union unsigned using virtual void volatile while',
    csharp: 'abstract as base bool break byte case catch char class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while',
    php: 'abstract and array as break callable case catch class clone const continue declare default do echo else elseif empty enddeclare endfor endforeach endif endswitch endwhile extends final finally fn for foreach function global goto if implements include include_once instanceof insteadof interface isset list match namespace new or print private protected public readonly require require_once return static switch throw trait try unset use var while xor yield true false null',
    swift: 'associatedtype class deinit enum extension fileprivate func import init inout internal let open operator private protocol public rethrows static struct subscript typealias var break case continue default defer do else fallthrough for guard if in repeat return switch where while as catch false is nil super self throw throws true try',
    sql: 'select from where insert into values update set delete create table drop alter add join left right inner outer on group by order having limit offset as and or not null distinct count sum avg min max case when then else end union all primary key foreign references index view',
    bash: 'if then else elif fi for while until do done case esac function return exit export set unset readonly local shift source alias echo cd ls mkdir rm cp mv cat grep sed awk curl wget git npm npx node python pip docker sudo chmod chown', 
    yaml: 'true false null yes no on off',
    ini: 'true false'
  };

  var WORD_SETS = {};
  Object.keys(KEYWORDS).forEach(function (lang) {
    var set = {};
    KEYWORDS[lang].split(/\s+/).forEach(function (word) { if (word) set[word] = true; });
    WORD_SETS[lang] = set;
  });

  var CONSTANTS = {
    true: 1, false: 1, null: 1, undefined: 1, None: 1, True: 1, False: 1, nil: 1,
    NaN: 1, Infinity: 1, this: 1, self: 1, super: 1
  };

  function wordSet(lang) {
    return WORD_SETS[lang] || WORD_SETS.javascript;
  }

  function isCodeish(lang) {
    return ['javascript', 'typescript', 'jsx', 'tsx', 'python', 'go', 'rust', 'ruby',
      'java', 'kotlin', 'c', 'cpp', 'csharp', 'php', 'swift', 'sql', 'bash', 'yaml',
      'ini', 'toml'].indexOf(lang) !== -1;
  }

  function span(cls, text) {
    return '<span class="tok-' + cls + '">' + esc(text) + '</span>';
  }

  /* Single-line tokenizer with carry-over state so block comments and
   * triple-quoted strings keep their colour across lines. */
  function tokenizeLine(line, lang, state) {
    var out = '';
    var i = 0;
    var len = line.length;
    var words = wordSet(lang);
    var hashComment = (lang === 'python' || lang === 'bash' || lang === 'yaml' || lang === 'ini' || lang === 'toml' || lang === 'ruby');

    function flushPlain(text) {
      if (text) out += esc(text);
    }

    if (state.block === '/*') {
      var close = line.indexOf('*/');
      if (close === -1) return span('com', line);
      out += span('com', line.slice(0, close + 2));
      i = close + 2;
      state.block = '';
    } else if (state.block === '"""' || state.block === "'''") {
      var marker = state.block;
      var endIdx = line.indexOf(marker);
      if (endIdx === -1) return span('str', line);
      out += span('str', line.slice(0, endIdx + 3));
      i = endIdx + 3;
      state.block = '';
    } else if (state.block === '<!--') {
      var gt = line.indexOf('-->');
      if (gt === -1) return span('com', line);
      out += span('com', line.slice(0, gt + 3));
      i = gt + 3;
      state.block = '';
    }

    var plain = '';

    while (i < len) {
      var ch = line[i];
      var next = line[i + 1] || '';
      var rest = line.slice(i);

      // block comments
      if (ch === '/' && next === '*' && isCodeish(lang)) {
        var endC = line.indexOf('*/', i + 2);
        flushPlain(plain); plain = '';
        if (endC === -1) { out += span('com', rest); state.block = '/*'; return out; }
        out += span('com', line.slice(i, endC + 2));
        i = endC + 2;
        continue;
      }

      if (lang === 'html' || lang === 'xml') {
        if (rest.indexOf('<!--') === 0) {
          var endH = line.indexOf('-->', i + 4);
          flushPlain(plain); plain = '';
          if (endH === -1) { out += span('com', rest); state.block = '<!--'; return out; }
          out += span('com', line.slice(i, endH + 3));
          i = endH + 3;
          continue;
        }
        var tag = /^<\/?([\w:-]+)/.exec(rest);
        if (tag) {
          flushPlain(plain); plain = '';
          out += esc(tag[0].slice(0, tag[0].length - tag[1].length)) + span('tag', tag[1]);
          i += tag[0].length;
          continue;
        }
        var attr = /^([\w:-]+)(=)/.exec(rest);
        if (attr) {
          flushPlain(plain); plain = '';
          out += span('attr', attr[1]) + esc('=');
          i += attr[0].length;
          continue;
        }
        if (ch === '>' || ch === '/') { plain += ch; i += 1; continue; }
      }

      // line comments
      if (isCodeish(lang) && ch === '/' && next === '/' && lang !== 'sql') {
        flushPlain(plain); plain = '';
        out += span('com', rest);
        return out;
      }
      if (hashComment && ch === '#' && (i === 0 || /\s/.test(line[i - 1]))) {
        flushPlain(plain); plain = '';
        out += span('com', rest);
        return out;
      }
      if (lang === 'sql' && rest.indexOf('--') === 0) {
        flushPlain(plain); plain = '';
        out += span('com', rest);
        return out;
      }

      // strings
      if (ch === '"' || ch === "'" || ch === '`') {
        if (lang === 'python' && line.slice(i, i + 3) === ch + ch + ch) {
          var marker = ch + ch + ch;
          var endT = line.indexOf(marker, i + 3);
          flushPlain(plain); plain = '';
          if (endT === -1) { out += span('str', rest); state.block = marker; return out; }
          out += span('str', line.slice(i, endT + 3));
          i = endT + 3;
          continue;
        }
        var quote = ch;
        var j = i + 1;
        while (j < len) {
          if (line[j] === '\\') { j += 2; continue; }
          if (line[j] === quote) { j += 1; break; }
          j += 1;
        }
        flushPlain(plain); plain = '';
        out += span('str', line.slice(i, j));
        i = j;
        continue;
      }

      // json keys:  "key":
      if (ch === '-' || /[0-9]/.test(ch)) {
        var num = /^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/i.exec(rest);
        if (num && (i === 0 || /[\s([{,:+\-*/=<>!&|?]/.test(line[i - 1]))) {
          flushPlain(plain); plain = '';
          out += span('num', num[0]);
          i += num[0].length;
          continue;
        }
      }

      // identifiers / keywords
      if (/[A-Za-z_$]/.test(ch)) {
        var word = /^[A-Za-z_$][\w$]*/.exec(rest)[0];
        var after = line.slice(i + word.length);
        flushPlain(plain); plain = '';
        if (words[word]) {
          out += span(CONSTANTS[word] ? 'const' : 'kw', word);
        } else if (/^\s*\(/.test(after)) {
          out += span('fn', word);
        } else if (/^\s*:/.test(after) && /^[^"]*"[^"]*"\s*:/.test(line)) {
          out += span('key', word);
        } else if (/^[A-Z]/.test(word) && word.length > 1) {
          out += span('type', word);
        } else {
          out += esc(word);
        }
        i += word.length;
        continue;
      }

      plain += ch;
      i += 1;
    }

    flushPlain(plain);
    return out;
  }

  function highlightLines(code, lang) {
    var source = String(code == null ? '' : code);
    var language = (lang || 'text').toLowerCase();
    var lines = source.replace(/\r\n?/g, '\n').split('\n');

    if (source.length > MAX_HIGHLIGHT_CHARS) {
      return lines.map(esc);
    }

    if (language === 'text' || language === 'markdown' || language === 'json') {
      if (language === 'json') {
        return jsonLines(lines);
      }
      if (language === 'markdown') {
        return lines.map(function (line) {
          if (/^\s*#{1,6}\s/.test(line)) return span('kw', line);
          if (/^\s*```/.test(line)) return span('com', line);
          if (/^\s*[-*+]\s/.test(line)) return span('attr', line.slice(0, line.indexOf(' ') + 1)) + esc(line.slice(line.indexOf(' ') + 1));
          if (/^\s*>/.test(line)) return span('com', line);
          return esc(line);
        });
      }
      return lines.map(esc);
    }

    var state = { block: '' };
    return lines.map(function (line) { return tokenizeLine(line, language, state); });
  }

  /* JSON deserves its own tiny pass: keys, strings, numbers, literals. */
  function jsonLines(lines) {
    var keyRe = /"(?:\\.|[^"\\])*"(?=\s*:)/g;
    return lines.map(function (line) {
      var marks = [];
      line.replace(keyRe, function (match, offset) {
        marks.push({ start: offset, end: offset + match.length });
        return match;
      });

      var out = '';
      var cursor = 0;
      marks.forEach(function (mark) {
        out += jsonRest(line.slice(cursor, mark.start));
        out += span('key', line.slice(mark.start, mark.end));
        cursor = mark.end;
      });
      out += jsonRest(line.slice(cursor));
      return out;
    });

    function jsonRest(chunk) {
      if (!chunk) return '';
      var out = '';
      var pattern = /("(?:\\.|[^"\\])*")|(\btrue\b|\bfalse\b|\bnull\b)|(-?\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b)/gi;
      var last = 0;
      var match;
      while ((match = pattern.exec(chunk)) !== null) {
        out += esc(chunk.slice(last, match.index));
        if (match[1]) out += span('str', match[1]);
        else if (match[2]) out += span('const', match[2]);
        else out += span('num', match[3]);
        last = match.index + match[0].length;
      }
      out += esc(chunk.slice(last));
      return out;
    }
  }

  /* ------------------------------------------------------------ styles */

  var STYLE_ID = 'rex-code-styles';

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    var css = ''
      + ':root{ --rx-code-bg:#0b0e14; --rx-code-line:#11161f; --rx-code-gutter:#3d485c; }'
      + '.rx-file-ico{ width:14px; height:14px; flex:0 0 auto; }'

      /* ---- code card inside chat ---- */
      + '.md pre.rx-code{ position:relative; border-radius:6px; }'
      + '.md pre.rx-code .pre-head{ gap:8px; }'
      + '.md pre.rx-code .pre-file{ display:flex; align-items:center; gap:7px; min-width:0; }'
      + '.md pre.rx-code .pre-name{ font-family:var(--font-mono); font-size:12px; color:var(--text-soft); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }'
      + '.md pre.rx-code .pre-meta{ font-family:var(--font-mono); font-size:11px; color:var(--faint); white-space:nowrap; }'
      + '.md pre.rx-code .pre-saved{'
      + '  font-family:var(--font-mono); font-size:9.5px; letter-spacing:.06em; color:var(--green);'
      + '  border:1px solid rgba(102,212,138,.35); background:rgba(102,212,138,.1); border-radius:3px; padding:2px 5px; white-space:nowrap; }'
      + '.md pre.rx-code .pre-actions{ display:flex; align-items:center; gap:5px; flex:0 0 auto; }'
      + '.md pre.rx-code .pre-btn, .md pre.rx-code .copy{'
      + '  font-family:var(--font-mono); font-size:10px; letter-spacing:.06em; text-transform:uppercase;'
      + '  color:var(--muted); padding:4px 8px; border:1px solid var(--border); border-radius:3px; background:transparent; cursor:pointer; }'
      + '.md pre.rx-code .pre-btn:hover, .md pre.rx-code .copy:hover{ color:var(--brand); border-color:var(--brand-dim); }'
      + '.md pre.rx-code .pre-btn.primary{ color:#141005; background:var(--brand); border-color:var(--brand); }'
      + '.md pre.rx-code .pre-btn.primary:hover{ filter:brightness(1.08); color:#141005; }'
      + '.md pre.rx-code .pre-body{ position:relative; }'
      + '.md pre.rx-code code{ display:block; padding:12px 14px; overflow:auto; max-height:360px; }'
      + '.md pre.rx-code.collapsible code{ max-height:230px; }'
      + '.md pre.rx-code.collapsible .pre-body::after{'
      + '  content:""; position:absolute; left:0; right:0; bottom:0; height:64px; pointer-events:none;'
      + '  background:linear-gradient(to bottom, rgba(11,14,20,0), var(--rx-code-bg)); }'
      + '.md pre.rx-code.collapsible .pre-body::before{'
      + '  content:"OPEN IN VIEWER TO SEE ALL " attr(data-lines) " LINES";'
      + '  position:absolute; left:0; right:0; bottom:10px; text-align:center; pointer-events:none;'
      + '  font-family:var(--font-mono); font-size:10px; letter-spacing:.08em; color:var(--faint); z-index:2; }'

      /* ---- viewer ---- */
      + '.rx-viewer{ position:fixed; inset:0; z-index:120; display:flex; align-items:center; justify-content:center; padding:24px; }'
      + '.rx-viewer-scrim{ position:absolute; inset:0; background:rgba(4,6,10,.72); backdrop-filter:blur(3px); animation:rx-v-fade .16s ease both; }'
      + '.rx-viewer-panel{'
      + '  position:relative; width:min(1080px, 100%); height:auto; min-height:min(46vh, 420px); max-height:min(80vh, 760px); display:flex; flex-direction:column;'
      + '  background:var(--surface); border:1px solid var(--border); border-radius:8px; box-shadow:0 24px 70px rgba(0,0,0,.65);'
      + '  overflow:hidden; animation:rx-v-in .18s cubic-bezier(.2,.9,.3,1) both; }'
      + '@keyframes rx-v-fade{ from{opacity:0} to{opacity:1} }'
      + '@keyframes rx-v-in{ from{ opacity:0; transform:translateY(10px) scale(.99); } to{ opacity:1; transform:none; } }'
      + '.rx-v-head{ display:flex; align-items:center; gap:12px; padding:10px 12px; background:var(--surface-2); border-bottom:1px solid var(--border); }'
      + '.rx-v-file{ display:flex; align-items:center; gap:9px; min-width:0; flex:1; }'
      + '.rx-v-name{ font-family:var(--font-mono); font-size:13px; color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }'
      + '.rx-v-sub{ font-family:var(--font-mono); font-size:10.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); margin-top:2px; }'
      + '.rx-v-actions{ display:flex; align-items:center; gap:6px; flex:0 0 auto; }'
      + '.rx-v-btn{'
      + '  display:inline-flex; align-items:center; gap:6px; font-family:var(--font-mono); font-size:10.5px;'
      + '  letter-spacing:.06em; text-transform:uppercase; color:var(--text-soft); background:transparent;'
      + '  border:1px solid var(--border); border-radius:4px; padding:6px 9px; cursor:pointer; }'
      + '.rx-v-btn:hover{ color:var(--brand); border-color:var(--brand-dim); }'
      + '.rx-v-btn.on{ color:#141005; background:var(--brand); border-color:var(--brand); }'
      + '.rx-v-btn svg{ width:13px; height:13px; }'
      + '.rx-v-close{ width:30px; height:30px; justify-content:center; padding:0; font-size:15px; }'
      + '.rx-v-main{ display:flex; min-height:0; flex:1; }'
      + '.rx-v-rail{ width:200px; flex:0 0 200px; border-right:1px solid var(--border); overflow-y:auto; padding:8px; background:var(--surface); }'
      + '.rx-v-rail-label{ font-family:var(--font-mono); font-size:10px; letter-spacing:.1em; color:var(--faint); padding:6px 8px; }'
      + '.rx-v-rail-item{ display:flex; align-items:center; gap:7px; width:100%; text-align:left; padding:6px 8px; border-radius:4px;'
      + '  font-family:var(--font-mono); font-size:12px; color:var(--text-soft); background:transparent; border:none; cursor:pointer; }'
      + '.rx-v-rail-item span{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }'
      + '.rx-v-rail-item:hover{ background:var(--surface-2); color:var(--text); }'
      + '.rx-v-rail-item.on{ background:var(--surface-3); color:var(--brand); }'
      + '.rx-v-body{ flex:1; min-width:0; overflow:auto; background:var(--rx-code-bg); }'
      + '.rx-v-code{ font-family:var(--font-mono); font-size:12.5px; line-height:1.65; }'
      + '.rx-v-line{ display:flex; align-items:flex-start; }'
      + '.rx-v-line:hover{ background:rgba(255,176,0,.045); }'
      + '.rx-v-ln{'
      + '  flex:0 0 52px; text-align:right; padding:0 12px 0 6px; color:var(--rx-code-gutter);'
      + '  user-select:none; border-right:1px solid rgba(255,255,255,.05); }'
      + '.rx-v-lc{ flex:1; padding:0 16px; white-space:pre; tab-size:2; }'
      + '.rx-v-code.wrap .rx-v-lc{ white-space:pre-wrap; word-break:break-word; }'
      + '.rx-v-blank{ min-height:1.65em; }'
      + '.rx-v-foot{ display:flex; align-items:center; gap:14px; padding:8px 12px; background:var(--surface-2);'
      + '  border-top:1px solid var(--border); font-family:var(--font-mono); font-size:10.5px; letter-spacing:.06em; color:var(--faint); text-transform:uppercase; }'
      + '.rx-v-foot .grow{ flex:1; }'
      + '.rx-v-empty{ padding:40px 20px; text-align:center; font-family:var(--font-mono); color:var(--faint); }'

      /* tokens */
      + '.tok-kw{ color:#ff8f66; font-weight:600; }'
      + '.tok-const{ color:#ffb000; font-weight:600; }'
      + '.tok-str{ color:#a8e6a1; }'
      + '.tok-num{ color:#d9a6ff; }'
      + '.tok-com{ color:#5f6b80; font-style:italic; }'
      + '.tok-fn{ color:#7cc4ff; }'
      + '.tok-key{ color:#4dd0e1; font-weight:500; }'
      + '.tok-type{ color:#ffd479; }'
      + '.tok-tag{ color:#ff8f6b; }'
      + '.tok-attr{ color:#c9a8ff; }'

      + '@media (max-width:720px){'
      + '  .rx-viewer{ padding:0; }'
      + '  .rx-viewer-panel{ width:100%; max-height:100%; height:100%; border-radius:0; }'
      + '  .rx-v-rail{ display:none; }'
      + '  .rx-v-btn span{ display:none; }'
      + '}'
      + '@media (prefers-reduced-motion: reduce){ .rx-viewer-scrim, .rx-viewer-panel{ animation:none !important; } }';

    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ------------------------------------------------------------- viewer */

  var state = {
    open: false,
    files: [],
    activeId: null,
    wrap: false,
    onClose: null
  };

  var ICONS = {
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>',
    save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>',
    wrap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M3 12h13a3 3 0 0 1 0 6h-4"/><path d="M8 15l-3 3 3 3"/><path d="M3 18h2"/></svg>'
  };

  function activeFile() {
    for (var i = 0; i < state.files.length; i += 1) {
      if (state.files[i].id === state.activeId) return state.files[i];
    }
    return state.files[0] || null;
  }

  function mount() {
    injectStyles();

    var existing = document.getElementById('rx-viewer');
    if (existing) existing.remove();

    var wrap = document.createElement('div');
    wrap.id = 'rx-viewer';
    wrap.className = 'rx-viewer';
    wrap.innerHTML = '<div class="rx-viewer-scrim" data-close></div>'
      + '<div class="rx-viewer-panel" role="dialog" aria-modal="true" aria-label="Code viewer">'
      + '  <header class="rx-v-head">'
      + '    <div class="rx-v-file">' + icon('file.txt')
      + '      <div style="min-width:0"><div class="rx-v-name">file</div><div class="rx-v-sub"></div></div>'
      + '    </div>'
      + '    <div class="rx-v-actions">'
      + '      <button type="button" class="rx-v-btn" data-act="save" title="Save this snippet to the workspace">' + ICONS.save + '<span>Save</span></button>'
      + '      <button type="button" class="rx-v-btn" data-act="copy" title="Copy code">' + ICONS.copy + '<span>Copy</span></button>'
      + '      <button type="button" class="rx-v-btn" data-act="download" title="Download file">' + ICONS.download + '<span>Download</span></button>'
      + '      <button type="button" class="rx-v-btn" data-act="wrap" title="Toggle soft wrap">' + ICONS.wrap + '<span>Wrap</span></button>'
      + '      <button type="button" class="rx-v-btn rx-v-close" data-close aria-label="Close viewer">✕</button>'
      + '    </div>'
      + '  </header>'
      + '  <div class="rx-v-main">'
      + '    <aside class="rx-v-rail" data-rail></aside>'
      + '    <div class="rx-v-body" data-body></div>'
      + '  </div>'
      + '  <footer class="rx-v-foot"><span data-foot-lang>text</span><span data-foot-lines>0 lines</span>'
      + '    <span class="grow"></span><span>ESC to close · [ ] switch file</span></footer>'
      + '</div>';

    document.body.appendChild(wrap);
    document.documentElement.classList.add('rx-viewer-open');

    wrap.addEventListener('click', function (event) {
      if (event.target.closest('[data-close]')) { close(); return; }

      var act = event.target.closest('[data-act]');
      if (act) { runAction(act.getAttribute('data-act')); return; }

      var rail = event.target.closest('[data-file-id]');
      if (rail) { state.activeId = rail.getAttribute('data-file-id'); paint(); }
    });

    document.addEventListener('keydown', onKeydown);

    return wrap;
  }

  function onKeydown(event) {
    if (!state.open) return;

    if (event.key === 'Escape') { event.preventDefault(); close(); return; }

    if (event.key === '[' || event.key === ']') {
      var index = -1;
      state.files.forEach(function (file, i) { if (file.id === state.activeId) index = i; });
      if (index === -1) return;
      var next = event.key === ']' ? index + 1 : index - 1;
      if (next < 0) next = state.files.length - 1;
      if (next >= state.files.length) next = 0;
      state.activeId = state.files[next].id;
      paint();
      event.preventDefault();
    }
  }

  function runAction(action) {
    var file = activeFile();
    if (!file) return;

    if (action === 'copy') {
      copyText(file.content);
      return;
    }

    if (action === 'download') {
      downloadFile(file);
      return;
    }

    if (action === 'save') {
      if (typeof global.rexSaveSnippet === 'function') {
        var saved = global.rexSaveSnippet(file.name, file.content, file.language);
        if (saved) {
          file.id = file.id.indexOf('ws:') === 0 ? file.id : 'ws:' + saved;
          paint();
        }
      } else {
        copyText(file.content);
      }
      return;
    }

    if (action === 'wrap') {
      state.wrap = !state.wrap;
      paint();
    }
  }

  function copyText(text) {
    try {
      navigator.clipboard.writeText(text).then(function () {
        if (typeof global.toast === 'function') global.toast('COPIED TO CLIPBOARD');
      });
    } catch (error) {
      if (typeof global.toast === 'function') global.toast('COPY FAILED');
    }
  }

  function downloadFile(file) {
    var blob = new Blob([file.content], { type: 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = String(file.name || 'snippet.txt').split('/').pop();
    link.click();
    URL.revokeObjectURL(url);
    if (typeof global.toast === 'function') global.toast('DOWNLOADED ' + link.download.toUpperCase());
  }

  function paint() {
    var wrap = document.getElementById('rx-viewer');
    if (!wrap) return;

    var file = activeFile();
    if (!file) { close(); return; }

    var content = String(file.content == null ? '' : file.content);
    var language = file.language || langFromName(file.name);
    var lines = content.replace(/\r\n?/g, '\n').split('\n');
    if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop();

    wrap.querySelector('.rx-v-file').innerHTML = icon(file.name)
      + '<div style="min-width:0"><div class="rx-v-name">' + esc(file.name || 'snippet') + '</div>'
      + '<div class="rx-v-sub">' + esc(fmtBytes(byteLength(content))) + ' · ' + lines.length + ' lines'
      + (file.sourceLabel ? ' · ' + esc(file.sourceLabel) : '') + '</div></div>';

    var rail = wrap.querySelector('[data-rail]');
    if (state.files.length > 1) {
      rail.style.display = '';
      rail.innerHTML = '<div class="rx-v-rail-label">FILES</div>'
        + state.files.map(function (item) {
          return '<button type="button" class="rx-v-rail-item' + (item.id === state.activeId ? ' on' : '')
            + '" data-file-id="' + esc(item.id) + '">' + icon(item.name) + '<span>' + esc(item.name) + '</span></button>';
        }).join('');
    } else {
      rail.style.display = 'none';
      rail.innerHTML = '';
    }

    var highlighted = highlightLines(content, language);
    var body = wrap.querySelector('[data-body]');
    body.innerHTML = '<div class="rx-v-code' + (state.wrap ? ' wrap' : '') + '">'
      + highlighted.map(function (html, index) {
        return '<div class="rx-v-line"><span class="rx-v-ln">' + (index + 1) + '</span>'
          + '<span class="rx-v-lc' + (html ? '' : ' rx-v-blank') + '">' + (html || ' ') + '</span></div>';
      }).join('')
      + '</div>';
    body.scrollTop = 0;

    wrap.querySelector('[data-foot-lang]').textContent = langLabel(language);
    wrap.querySelector('[data-foot-lines]').textContent = lines.length + ' lines';
    wrap.querySelector('[data-act="wrap"]').classList.toggle('on', state.wrap);

    var saveBtn = wrap.querySelector('[data-act="save"]');
    saveBtn.style.display = (global.rexSaveSnippet && file.fromChat) ? '' : 'none';

    paint.done = true;
  }

  function open(options) {
    var opts = options || {};
    injectStyles();

    var files = (opts.files || []).map(function (file, index) {
      return {
        id: file.id || ('f' + index),
        name: file.name || ('snippet-' + (index + 1) + '.txt'),
        content: file.content || '',
        language: file.language || langFromName(file.name),
        sourceLabel: file.sourceLabel || '',
        fromChat: file.fromChat !== false && !file.sourceLabel
      };
    });

    if (opts.content != null && !files.length) {
      files = [{
        id: 'current',
        name: opts.name || ('snippet.' + (opts.extension || 'txt')),
        content: String(opts.content),
        language: opts.language || langFromName(opts.name),
        sourceLabel: opts.sourceLabel || '',
        fromChat: opts.fromChat !== false
      }];
    }

    if (!files.length) return;

    state.files = files;
    state.activeId = opts.activeId && files.some(function (f) { return f.id === opts.activeId; })
      ? opts.activeId
      : files[0].id;
    state.wrap = !!opts.wrap;
    state.open = true;

    mount();
    paint();

    if (typeof global.toast === 'function' && opts.silent !== true) {
      // no toast on open: the viewer itself is the feedback
    }
  }

  function close() {
    var wrap = document.getElementById('rx-viewer');
    if (wrap) wrap.remove();
    document.documentElement.classList.remove('rx-viewer-open');
    document.removeEventListener('keydown', onKeydown);
    state.open = false;
    state.files = [];
    state.activeId = null;
  }

  /* -------------------------------------------------------- code cards */

  /* Turns a <pre> produced by renderMarkdown into a code card. Called from
   * the chat renderer; safe to call twice. */
  function decorate(pre, options) {
    if (!pre || pre.classList.contains('rx-code')) return;

    var opts = options || {};
    var codeEl = pre.querySelector('code');
    if (!codeEl) return;

    var content = codeEl.textContent || '';
    var lang = (opts.language || '').toLowerCase();
    var head = pre.querySelector('.pre-head');

    if (!head) {
      head = document.createElement('div');
      head.className = 'pre-head';
      pre.insertBefore(head, pre.firstChild);
    }

    var lineCount = content.replace(/\r\n?/g, '\n').split('\n').length;
    var name = opts.name || '';

    pre.classList.add('rx-code');
    if (lineCount > 14) pre.classList.add('collapsible');

    var savedTag = opts.saved
      ? '<span class="pre-saved" title="Saved to this chat workspace">✓ SAVED</span>'
      : '';

    head.innerHTML = '<span class="pre-file">' + icon(name || 'snippet.txt')
      + '<span class="pre-name">' + esc(name || langLabel(lang)) + '</span>'
      + '<span class="pre-meta">' + lineCount + ' LINES</span>' + savedTag + '</span>'
      + '<span class="pre-actions">'
      + '<button type="button" class="pre-btn primary" data-code-open>OPEN</button>'
      + '<button type="button" class="copy" data-code-copy>COPY</button>'
      + '</span>';

    if (!pre.querySelector('.pre-body')) {
      var body = document.createElement('div');
      body.className = 'pre-body';
      body.setAttribute('data-lines', String(lineCount));
      pre.appendChild(body);
      body.appendChild(codeEl);
    }

    // Same tokenizer as the viewer, so a snippet looks identical in both places.
    if (!codeEl.dataset.highlighted) {
      var highlighted = highlightLines(content, lang || 'text');
      if (highlighted.join('').length < content.length * 12) {
        codeEl.innerHTML = highlighted.join('\n');
        codeEl.dataset.highlighted = '1';
      }
    }

    pre.addEventListener('click', function (event) {
      if (event.target.closest('[data-code-copy]')) {
        copyText(content);
        return;
      }
      var wantsOpen = event.target.closest('[data-code-open]') || event.target.closest('.pre-head');
      if (wantsOpen) {
        open({
          name: name || ('snippet.' + (lang === 'javascript' ? 'js' : lang === 'python' ? 'py' : lang === 'bash' ? 'sh' : lang || 'txt')),
          content: content,
          language: lang,
          fromChat: true
        });
      }
    });
  }

  global.RexCode = {
    highlightLines: highlightLines,
    decorate: decorate,
    open: open,
    close: close,
    icon: icon,
    langFromName: langFromName,
    langLabel: langLabel,
    isOpen: function () { return state.open; }
  };

  injectStyles();

  /* Delegation for the whole app: any [data-code-open] / workspace row. */
  document.addEventListener('click', function (event) {
    var opener = event.target.closest('[data-open-code]');
    if (opener) {
      var name = opener.getAttribute('data-open-code') || 'snippet.txt';
      var payload = opener.getAttribute('data-code-payload');
      if (payload) {
        try {
          var parsed = JSON.parse(payload);
          open({ name: name, content: parsed.content, language: parsed.language, fromChat: true });
        } catch (error) { /* ignore */ }
      }
    }
  });
})(typeof window !== 'undefined' ? window : this);
