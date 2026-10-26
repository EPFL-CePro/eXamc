import type DataTable from "datatables.net-bs5";

export type DataTableOptions = NonNullable<ConstructorParameters<typeof DataTable>[1]>;
export type DataTableColumn = NonNullable<DataTableOptions["columns"]>[number];
