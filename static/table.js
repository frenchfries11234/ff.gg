document.addEventListener("DOMContentLoaded", () => {
    // Helper to highlight sorted column
    function highlightSortedColumn(table, columnIndex) {
        table.querySelectorAll("th, td").forEach(cell => {
            cell.classList.remove("sorted");
        });

        const headerRow = table.querySelector("thead tr");
        if (headerRow) {
            const th = headerRow.children[columnIndex];
            if (th) th.classList.add("sorted");
        }

        table.querySelectorAll("tbody tr").forEach(row => {
            const cell = row.children[columnIndex];
            if (cell) cell.classList.add("sorted");
        });
    }

    function initTablesort(table) {
        if (table.dataset.sorted) return;

        new Tablesort(table);

        table.querySelectorAll("th").forEach((th, index) => {
            th.addEventListener("click", () => {
                highlightSortedColumn(table, index);
            });
        });

        table.dataset.sorted = "true";
    }

    const activeTable = document.querySelector('.tab-pane.show.active table');
    if (activeTable) {
        initTablesort(activeTable);
    }

    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', event => {
            const targetId = event.target.getAttribute('href');
            const pane = document.querySelector(targetId);
            const table = pane?.querySelector('table');
            if (table) {
                initTablesort(table);
            }
        });
    });
});