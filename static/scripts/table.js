$(function () {
    const $tables = $(".sortable-table");

    $tables.each(function () {
        const $table = $(this);

        // Mark first column as unsortable
        $table.find("thead th").eq(0).addClass("sorter-false");

        // Initialize tablesorter
        $table.tablesorter({
            sortList: [[3, 1]], // Default sort
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
