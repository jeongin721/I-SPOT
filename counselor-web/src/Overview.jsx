// 첫 화면: 모든 화면을 흐름(행)별로 모아 둔 목차. 디자인 캔버스의 배치를 그대로 따라요.
import { Link } from 'react-router-dom';
import manifest from './pages/manifest.json';

const rows = Object.values(manifest.notes)
  .sort((a, b) => a.y - b.y)
  .map((note, i, all) => {
    const next = all[i + 1];
    const boards = Object.entries(manifest.boards)
      .filter(([, b]) => b.y > note.y && (!next || b.y < next.y))
      .sort((a, b) => a[1].x - b[1].x)
      .map(([file, b]) => ({ name: file.replace('.dc.html', ''), title: b.title }));
    return { title: note.text, boards };
  });

export default function Overview() {
  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '40px 24px 80px', fontFamily: "'IBM Plex Sans KR', sans-serif", color: '#2B2A26' }}>
      <h1 style={{ margin: 0, fontSize: 30 }}>I-SPOT 상담사 웹 · 화면 목록</h1>
      <p style={{ color: '#7A776F', marginTop: 6 }}>아동보호전문기관 상담원용 · 화면을 누르면 실제로 클릭해 볼 수 있어요</p>
      {rows.map((row) => (
        <section key={row.title} style={{ marginTop: 28 }}>
          <h2 style={{ fontSize: 17, margin: '0 0 10px' }}>{row.title}</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
            {row.boards.map((b) => (
              <Link
                key={b.name}
                to={`/${b.name}`}
                style={{ display: 'block', padding: '14px 16px', borderRadius: 14, border: '1px solid #E2DED3', background: '#FFFFFF', textDecoration: 'none', color: '#2B2A26' }}
              >
                <b style={{ display: 'block', fontSize: 15 }}>{b.name}</b>
                <span style={{ fontSize: 12.5, color: '#7A776F' }}>{b.title}</span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
