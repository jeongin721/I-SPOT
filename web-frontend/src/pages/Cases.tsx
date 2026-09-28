import Header from '../components/Header';
import { mockData } from '../data/mockData';
import { Search, User } from 'lucide-react';
import './Dashboard.css'; // Reusing dashboard styles for layout

export default function Cases() {
  return (
    <div className="dashboard-container">
      <Header />
      <main className="dashboard-main">
        <section className="welcome-section">
          <div className="welcome-text">
            <h1>담당 사례 관리</h1>
            <p className="subtitle">현재 담당하고 있는 아동의 사례 목록입니다.</p>
          </div>
          <div className="search-bar">
            <Search size={18} className="search-icon" />
            <input type="text" placeholder="이름 또는 사례번호 검색" />
          </div>
        </section>

        <div className="card" style={{ padding: '24px', overflowX: 'auto' }}>
          <table style={{ width: '100%', minWidth: '600px', textAlign: 'left', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '16px', color: '#888', fontWeight: 500 }}>아동 이름 (나이)</th>
                <th style={{ padding: '16px', color: '#888', fontWeight: 500 }}>진행 상태</th>
                <th style={{ padding: '16px', color: '#888', fontWeight: 500 }}>회기</th>
                <th style={{ padding: '16px', color: '#888', fontWeight: 500 }}>최근 상담일</th>
                <th style={{ padding: '16px', color: '#888', fontWeight: 500 }}>액션</th>
              </tr>
            </thead>
            <tbody>
              {mockData.cases.map(c => (
                <tr key={c.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '16px', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#f0f4f9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)' }}>
                        <User size={18} />
                      </div>
                      {c.name} ({c.age}세)
                    </div>
                  </td>
                  <td style={{ padding: '16px' }}>
                    <span className={`tag ${c.status.includes('정기') ? 'blue' : 'outline-blue'}`}>{c.status}</span>
                  </td>
                  <td style={{ padding: '16px' }}>{c.session}회기</td>
                  <td style={{ padding: '16px', color: '#666' }}>{c.lastCounseling || '없음'}</td>
                  <td style={{ padding: '16px' }}>
                    <button className="btn-outline btn-sm">상세 보기</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
