$(function () {
    const $tables = $(".sortable-table");

    $tables.each(function () {
        const $table = $(this);

        // Mark first column as unsortable
        $table.find("thead th").eq(0).addClass("sorter-false");

        // Initialize tablesorter
        $table.tablesorter({
            sortList: [[4, 1]], // Default sort
            headers: {
                0: { sorter: false } // Disable sorting for first column
            }
        });

        function updateRowIndices() {
            $table.find("tbody tr").each(function (i) {
                $(this).find("td").eq(0).text(i + 1);
            });
        }

        // Initial index set
        updateRowIndices();

        // Update indices after sort
        $table.on("sortEnd", function () {
            $(".sortable-table td").removeClass("sorted-column");

            const sortList = this.config.sortList;
            sortList.forEach(([colIndex]) => {
                $table.find("tbody tr").each(function () {
                    $(this).find("td").eq(colIndex).addClass("sorted-column");
                });
            });

            updateRowIndices();
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', () => {
      const href = row.getAttribute('data-href');
      if (href) window.location.href = href;
    });
  });
});

(function () {
  const BUTTONS = document.querySelectorAll('.scoring-btn');
  const HEADER  = document.querySelector('.fantasy-col-header');
  const CELLS   = document.querySelectorAll('td.fantasy-col');
  const LABEL   = { espn_ppr: 'Fantasy (PPR)', espn_half: 'Fantasy (Half)', espn_std: 'Fantasy (Standard)' };

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

    try { localStorage.setItem('scoring', key); } catch (e) {}
  }

  // wire buttons
  BUTTONS.forEach(btn => btn.addEventListener('click', () => applyScoring(btn.dataset.scoring)));

  // initial state (restore last choice or default PPR)
  applyScoring(localStorage.getItem('scoring') || 'espn_ppr');
})();