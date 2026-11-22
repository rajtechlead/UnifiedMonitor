interface TableHeadProps {
  headers: string[]
  cellPadding?: string
  background?: string
}

/** Header row for the read-only tables: one column per header string. */
export default function TableHead({ headers, cellPadding = '10px 14px', background = 'var(--color-surface-2)' }: Readonly<TableHeadProps>) {
  return (
    <thead>
      <tr style={{ background, borderBottom: '1px solid var(--color-border)' }}>
        {headers.map(header => (
          <th key={header} style={{
            textAlign: 'left', padding: cellPadding, fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600,
          }}>{header}</th>
        ))}
      </tr>
    </thead>
  )
}
