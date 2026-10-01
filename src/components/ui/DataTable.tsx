import type { ReactNode } from "react";
import { EmptyState } from "./EmptyState";

type DataTableProps = {
  columns: string[];
  children?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  footer?: ReactNode;
};

const ALIGN_COLUMNS = /value|diff|amount|source|total|difference/i;

export function DataTable({
  columns,
  children,
  emptyTitle,
  emptyDescription,
  emptyAction,
  footer,
}: DataTableProps) {
  const isEmpty =
    children === undefined ||
    children === null ||
    (Array.isArray(children) && children.length === 0);
  return (
    <>
      <div className="tw">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} scope="col" className={ALIGN_COLUMNS.test(column) ? "r" : ""}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isEmpty ? (
              <tr>
                <td colSpan={columns.length}>
                  {emptyTitle ? (
                    <EmptyState title={emptyTitle} description={emptyDescription ?? ""} action={emptyAction} />
                  ) : null}
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>
      {footer ? <div className="foot-t">{footer}</div> : null}
    </>
  );
}
