// sortable tables init (NFL & Teams)
$(function () {
  $(".sortable-table").each(function () {
    const $table = $(this);

    // --- per-table header config ---
    // # column unsortable; cols >=4 default to DESC on first click
    const headersCfg = { 0: { sorter: false } };
    $table.find("thead th").each(function (i) {
      if (i >= 4) headersCfg[i] = Object.assign(headersCfg[i] || {}, { sortInitialOrder: "desc" });
    });
    if (window.buildHeadersCfg) Object.assign(headersCfg, window.buildHeadersCfg($table));

    // --- default sort col: detect Fantasy header OR override via data attribute ---
    const $fantasyTh = $table.find("thead th.fantasy-col-header");
    const detectedIdx = $table.find("thead th").index($fantasyTh); // 0-based
    const attrIdx = parseInt($table.attr("data-default-sort-col"), 10);
    const defaultIdx = Number.isFinite(attrIdx) ? attrIdx : (detectedIdx >= 0 ? detectedIdx : 4);

    // --- helpers ---
    function updateRowIndices() {
      $table.find("tbody tr").each(function (i) {
        $(this).children("td").eq(0).text(i + 1);
      });
    }
    function markSortedColumn() {
      $table.find("td.sorted-column").removeClass("sorted-column");
      $table.find("th.sorted-header").removeClass("sorted-header");

      const cfg = $table[0].config;
      if (!cfg || !cfg.sortList || !cfg.sortList.length) return;
      const colIdx = cfg.sortList[0][0];

      $table.find("thead th").eq(colIdx).addClass("sorted-header");
      $table.find("tbody tr").each(function () {
        $(this).children("td").eq(colIdx).addClass("sorted-column");
      });
    }

    // --- init tablesorter (bind events BEFORE we need them) ---
    $table
      .on("sortEnd updateComplete pagerComplete filterEnd", function () {
        updateRowIndices();
        markSortedColumn();
      })
      .tablesorter({
        theme: "bootstrap",
        headerTemplate: "{content}",
        sortRestart: true,
        sortList: [[defaultIdx, 1]],   // DESC by default
        headers: headersCfg,
        textExtraction: function (cell) {
          const ds = cell.getAttribute("data-sort");
          return ds != null ? ds : cell.textContent.trim();
        },
        // ensure first render gets numbered & highlighted
        initialized: function (table) {
          // defer to allow DOM reorder to finish
          setTimeout(function () {
            updateRowIndices();
            markSortedColumn();
          }, 0);
        }
      });
  });
});


document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.clickable-row').forEach(row => {
    const href = row.dataset.href;
    if (!href) return;

    // Make row focusable & accessible
    row.setAttribute('tabindex', '0');
    row.setAttribute('role', 'link');

    // Primary click
    row.addEventListener('click', (e) => {
      if (e.defaultPrevented) return;
      if (e.target.closest('a,button,input,textarea,select,[role="button"]')) return;

      if (e.ctrlKey || e.metaKey || e.shiftKey) {
        // Ctrl/Cmd/Shift + click -> new tab/window
        window.open(href, '_blank', 'noopener');
      } else {
        window.location.href = href;
      }
    });

    // Middle-click (auxclick = button 1)
    row.addEventListener('auxclick', (e) => {
      if (e.button !== 1) return;
      if (e.target.closest('a,button,input,textarea,select,[role="button"]')) return;
      window.open(href, '_blank', 'noopener');
    });

    // Keyboard: Enter or Space to activate (Ctrl/Cmd+Enter -> new tab)
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        if (e.ctrlKey || e.metaKey || e.shiftKey) {
          window.open(href, '_blank', 'noopener');
        } else {
          window.location.href = href;
        }
        e.preventDefault();
      }
    });
  });
});

(function () {
  const BUTTONS = document.querySelectorAll('.scoring-btn');
  const HEADER = document.querySelector('.fantasy-col-header');
  const CELLS = document.querySelectorAll('td.fantasy-col');
  const LABEL = { espn_ppr: 'Fantasy (PPR)', espn_half: 'Fantasy (Half)', espn_std: 'Fantasy (Std)' };

  function keyToDataAttr(k) {
    return (k === 'espn_ppr') ? 'ppr' : (k === 'espn_half') ? 'half' : 'std';
  }

  function applyScoring(key) {
    const dataKey = keyToDataAttr(key);

    // header label
    if (HEADER) HEADER.textContent = LABEL[key] || 'Fantasy';

    // swap all fantasy cells
    CELLS.forEach(td => {
      const val = td.dataset[dataKey] || '0.00';
      td.textContent = val;
    });

    // button visual state + Tabler blue theme
    BUTTONS.forEach(btn => {
      const isActive = btn.dataset.scoring === key;
      btn.classList.toggle('active', isActive);
      btn.classList.toggle('btn-primary', isActive);
      btn.classList.toggle('btn-outline-primary', !isActive);
    });

    // if you're using tablesorter or similar, trigger an update
    if (window.jQuery && jQuery('.sortable-table').length) {
      jQuery('.sortable-table').trigger('update');
    }

    try { localStorage.setItem('scoring', key); } catch (e) { }
  }

  // wire buttons
  BUTTONS.forEach(btn => btn.addEventListener('click', () => applyScoring(btn.dataset.scoring)));

  // initial state (restore last choice or default PPR)
  applyScoring(localStorage.getItem('scoring') || 'espn_ppr');
})();

(function () {
  const input = document.getElementById('player-search');
  const menu = document.getElementById('player-suggestions');
  if (!input || !menu) return;

  let index = null;          // fetched player list
  let active = -1;           // highlighted suggestion
  const MAX_SHOW = 10;

  function fetchIndexOnce() {
    if (index !== null) return Promise.resolve(index);
    return fetch('/api/nfl/search-index')
      .then(r => r.json())
      .then(data => (index = data))
      .catch(() => (index = []));
  }

  function tokenize(s) { return String(s || '').toLowerCase(); }

  function score(entry, q) {
    const name = tokenize(entry.name);
    if (name.startsWith(q)) return 3;          // prefix match
    if (name.includes(q)) return 2;          // substring
    const teampos = tokenize(entry.team + ' ' + entry.position);
    return teampos.includes(q) ? 1 : 0;       // weaker match
  }

  function render(list) {
    menu.innerHTML = '';
    active = -1;
    if (!list.length) { menu.style.display = 'none'; return; }
    list.slice(0, MAX_SHOW).forEach((p, i) => {
      const el = document.createElement('div');
      el.className = 'item';
      el.dataset.href = `/nfl/players/${p.espn_id}`;
      el.innerHTML = `
        <div><strong>${p.name}</strong> <span class="meta">(${p.position} • ${p.team})</span></div>
        <div class="ms-auto meta">${p.fantasy_ppr?.toFixed ? p.fantasy_ppr.toFixed(2) : p.fantasy_ppr || ''}</div>
      `;
      el.addEventListener('mousedown', (e) => {
        // mousedown fires before input blur; navigate immediately
        window.location.href = el.dataset.href;
      });
      menu.appendChild(el);
    });
    menu.style.display = 'block';
  }

  function updateActive(newIndex) {
    const items = Array.from(menu.querySelectorAll('.item'));
    items.forEach(i => i.classList.remove('active'));
    if (!items.length) return;
    active = (newIndex + items.length) % items.length;
    items[active].classList.add('active');
    items[active].scrollIntoView({ block: 'nearest' });
  }

  function handleInput() {
    const q = tokenize(input.value);
    if (!q) { menu.style.display = 'none'; return; }
    fetchIndexOnce().then(() => {
      const matches = index
        .map(p => ({ p, s: score(p, q) }))
        .filter(x => x.s > 0)
        .sort((a, b) => b.s - a.s || a.p.name.localeCompare(b.p.name))
        .map(x => x.p);
      render(matches);
    });
  }

  function handleKey(e) {
    const items = menu.querySelectorAll('.item');
    if (!items.length) return;

    if (e.key === 'ArrowDown') { e.preventDefault(); updateActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); updateActive(active - 1); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      if (active >= 0) items[active].dispatchEvent(new Event('mousedown'));
      else if (items[0]) items[0].dispatchEvent(new Event('mousedown'));
    } else if (e.key === 'Escape') {
      menu.style.display = 'none';
      input.blur();
    }
  }

  // Wire events
  input.addEventListener('focus', fetchIndexOnce);
  input.addEventListener('input', handleInput);
  input.addEventListener('keydown', handleKey);

  // Hide menu when clicking outside
  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && e.target !== input) {
      menu.style.display = 'none';
    }
  });
})();