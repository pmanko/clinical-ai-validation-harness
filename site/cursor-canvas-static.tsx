import * as React from 'react';
import type { Tone } from './cursor-canvas';

export * from './cursor-canvas';

export function BarChart({
  categories,
  series,
}: {
  categories: string[];
  series: Array<{ name: string; data: number[]; tone?: Tone }>;
  height?: number;
}) {
  return (
    <figure className="cv-chart" role="img" aria-label="bar chart (rendered as a data table)">
      <figcaption>Bar chart — values</figcaption>
      <table>
        <thead>
          <tr>
            <th scope="col">Category</th>
            {series.map((s) => (
              <th key={s.name} scope="col">{s.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {categories.map((c, i) => (
            <tr key={c}>
              <th scope="row">{c}</th>
              {series.map((s) => (
                <td key={s.name}>{s.data[i] ?? ''}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
