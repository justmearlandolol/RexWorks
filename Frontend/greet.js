(function () {
  'use strict';

  var GREETINGS = [
    'Back at it, {name}',
    'Hey again, {name}. Where do we start?',
    'Welcome back, {name}.',
    'Yo, {name}! Ready to build something today?',
    'Missed you, {name}. What can I help with?',
    'What are you in the mood to work on, {name}?',
    'Keep the momentum going, {name}. Shall we?',
    'Hi {name}, what idea are we shipping today?',
    'Good to have you back, {name}.',
    'Ready when you are, {name}. Where do we begin?',
    'Welcome back, {name}. Your desk is all tidy.',
    '{name}, got something on your mind? Just type it.',
    'Hi {name}, productive day or a chill one?',
    'Good to see you again, {name}.',
    '{name}! Coding, writing, or researching first?',
    'No rush, {name}. We will take it step by step.',
    'How have you been, {name}? Tell me a little.',
    'What phase are you in right now, {name}?',
    'All set, {name}? So am I.',
    'Hi {name}, I am right here whenever you need me.',
    'Alright {name}, let us start with what matters most.',
    '{name}, what should we knock out today?',
    'Back to work, {name}? I will keep you company.',
    'Hey {name}, how heavy is today looking?',
    'Welcome, {name}. No stiff formalities here, promise.',
    '{name}, if you get stuck, we will break it down together.',
    'Nice, {name} is back. Pick up where we left off?',
    'Hey again {name}, coffee ready? Let us begin.',
    '{name}, whatever you bring today, we will give it a go.',
    'Welcome, {name}. Fast or thorough? Both work for me.',
    'Hey {name}, want a draft first or straight to execution?',
    'Thinking hard, {name}? Let me think with you.',
    '{name}, got a file to analyze or shall we just talk first?',
    'Hi {name}, take a breath, then we start.',
    'Keep going, {name}. Small progress is still progress.',
    'Ready whenever you are ready, {name}.',
    '{name}, everything we discuss is saved. Relax.',
    'Hi {name}, continue the old project or start something new?',
    '{name}, no need to hurry. Let us plan it out first.',
    'Hi {name}, I have been ready this whole time.',
    '{name}, a small step now beats a perfect plan later.',
    'Morning, noon, night. Just say hi, {name}.',
    '{name}, want the short version or the full detail?',
    'Hey {name}, any wild idea you want to try?',
    'Hi {name}. There are no silly questions here.',
    '{name}, let us set the context first so the result fits.',
    'Let us work together, {name}. My focus is on you.',
    '{name}, want me to write, summarize, or code it?',
    'Welcome, {name}. Whatever your pace, I will match it.',
    'Hi {name}, this is your workspace. Free, easy, and polite.'
  ];

  var LAST_KEY = 'rexwork_greet_last';
  var CURRENT_KEY = 'rexwork_greet_current';

  function storedName() {
    var keys = ['rexwork_auth', 'rexwork_profile'];
    for (var i = 0; i < keys.length; i++) {
      try {
        var raw = localStorage.getItem(keys[i]);
        if (!raw) continue;
        var data = JSON.parse(raw) || {};
        var meta = data.user_metadata || data.userMetadata || {};
        var candidates = [
          data.name, data.displayName, data.display_name, data.full_name, data.username,
          meta.full_name, meta.name, meta.user_name, meta.preferred_username
        ];
        for (var j = 0; j < candidates.length; j++) {
          if (typeof candidates[j] === 'string' && candidates[j].trim()) return candidates[j].trim();
        }
        if (typeof data.email === 'string' && data.email.indexOf('@') > 0) {
          return data.email.split('@')[0].trim();
        }
      } catch (error) {}
    }
    return '';
  }

  function resolveName(node) {
    var name = node ? (node.getAttribute('data-name') || '') : '';
    if (!name) name = window.REXWORK_USER_NAME || '';
    if (!name) name = storedName();
    if (!name) name = 'there';
    name = String(name).replace(/\s+/g, ' ').trim();
    return name.length > 28 ? name.slice(0, 28).trim() : name;
  }

  function pick(force) {
    if (!force) {
      try {
        var current = sessionStorage.getItem(CURRENT_KEY);
        if (current !== null && GREETINGS[current] !== undefined) return GREETINGS[current];
      } catch (error) {}
    }
    var index = Math.floor(Math.random() * GREETINGS.length);
    try {
      var last = parseInt(sessionStorage.getItem(LAST_KEY), 10);
      if (!isNaN(last) && GREETINGS.length > 1 && index === last) {
        index = (index + 1 + Math.floor(Math.random() * (GREETINGS.length - 1))) % GREETINGS.length;
      }
      sessionStorage.setItem(LAST_KEY, String(index));
      sessionStorage.setItem(CURRENT_KEY, String(index));
    } catch (error) {}
    return GREETINGS[index];
  }

  function logoSrc() {
    if (window.REXWORK_LOGO_SRC) return window.REXWORK_LOGO_SRC;
    try {
      var value = getComputedStyle(document.documentElement).getPropertyValue('--rw-logo') || '';
      var match = value.match(/url\(["']?(.*?)["']?\)/);
      if (match && match[1]) return match[1];
    } catch (error) {}
    return 'rexworks-logo.png';
  }

  function injectStyle() {
    if (document.getElementById('rwg-style')) return;
    var style = document.createElement('style');
    style.id = 'rwg-style';
    style.textContent = [
      '.rwg{ display:flex; align-items:center; justify-content:center; gap:14px; flex-wrap:nowrap; width:100%; }',
      '.rwg-logo{ width:clamp(32px,4.6vw,46px); height:auto; flex:0 0 auto; filter:drop-shadow(0 8px 20px rgba(0,0,0,.5)); }',
      '.rwg-text{ font-family:var(--font-mono,"IBM Plex Mono",ui-monospace,monospace); font-size:clamp(19px,2.9vw,29px); line-height:1.35; letter-spacing:-.2px; color:var(--text,#e9edf5); text-align:left; text-wrap:balance; }',
      '.rwg-text b{ font-weight:600; color:var(--text,#e9edf5); }',
      '@media (max-width:520px){ .rwg{ gap:10px; } .rwg-text{ font-size:19px; } }'
    ].join('\n');
    document.head.appendChild(style);
  }

  function render(node, options) {
    if (!node) return '';
    var name = resolveName(node);
    var text = (options && options.text) || node.getAttribute('data-text') || pick();
    var rendered = String(text).split('{name}').join(name);
    var escaped = rendered.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    var safeName = name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    if (escaped.indexOf(safeName) !== -1) {
      escaped = escaped.split(safeName).join('<b>' + safeName + '</b>');
    }
    injectStyle();
    node.classList.add('rwg');
    node.innerHTML = '<img class="rwg-logo" src="' + logoSrc() + '" alt="RexWork" />' +
      '<span class="rwg-text">' + escaped + '</span>';
    return rendered;
  }

  function mount(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll('[data-rexwork-greet]');
    for (var i = 0; i < nodes.length; i++) render(nodes[i]);
    return nodes.length;
  }

  window.RexWorkGreet = {
    greetings: GREETINGS,
    pick: pick,
    render: render,
    mount: mount,
    resolveName: resolveName
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { mount(); });
  } else {
    mount();
  }
})();
