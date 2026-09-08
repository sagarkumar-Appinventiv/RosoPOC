import React from 'react';

const formatLabel = (key: string) => key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export const StructuredContent: React.FC<{ value: unknown }> = ({ value }) => {
  if (value == null) return <span style={{ color: '#94A3B8' }}>—</span>;
  if (typeof value !== 'object') return <span>{String(value)}</span>;

  if (Array.isArray(value)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {value.map((item, index) => (
          <div key={index} style={{ display: 'grid', gridTemplateColumns: '24px minmax(0, 1fr)', gap: '8px', alignItems: 'start' }}>
            <span style={{ color: '#64748B', fontWeight: 800 }}>{index + 1}.</span>
            <div style={{ minWidth: 0 }}><StructuredContent value={item} /></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
        <div key={key} style={{ borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', marginBottom: '5px' }}>{formatLabel(key)}</div>
          <div style={{ color: '#1E293B', lineHeight: 1.55 }}><StructuredContent value={item} /></div>
        </div>
      ))}
    </div>
  );
};

export default StructuredContent;
