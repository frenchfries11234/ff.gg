$(function () {
    const $tables = $(".sortable-table");

    $tables.each(function () {
        const $table = $(this);

        // Initialize tablesorter with default sort on column index 2 (3rd column), descending
        $table.tablesorter({
            sortList: [[2, 1]]  // [columnIndex, sortDirection] => 1 = descending
        });

        // Highlight sorted column(s) after sorting
        $table.bind("sortEnd", function (e, table) {
            $(".sortable-table td").removeClass("sorted-column");

            const sortList = table.config.sortList;
            sortList.forEach(([colIndex]) => {
                $table.find("tbody tr").each(function () {
                    $(this).find("td").eq(colIndex).addClass("sorted-column");
                });
            });
        });
    });
});
